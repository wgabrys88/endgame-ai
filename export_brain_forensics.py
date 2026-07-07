#!/usr/bin/env python3
"""Export LLM request/response pairs from JSONL logs into phased markdown files.

Generic, field-agnostic: recursively pretty-expands any JSON embedded in strings
and unescapes transport newline/tab sequences. No truncation, no redaction.

Supported inputs (auto-detected):
  - endgame-ai runtime_events.jsonl  (brain_request / brain_response by seq)
  - xAI console / SERVER-REQUESTS-RAW.jsonl  (one request+response per line)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.resolve()

MAX_EMBED_DEPTH = 64
JSON_PREFIXES = "{["


@dataclass(frozen=True)
class Pair:
    index: int
    request: dict[str, Any]
    response: dict[str, Any]
    label: str = ""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object per line")
        records.append(obj)
    return records


def unescape_transport_string(value: str) -> str:
    """Expand common transport escape sequences without mangling arbitrary text."""
    if not value:
        return value
    if "\\n" in value and "\n" not in value:
        try:
            return value.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass
    return (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\'", "'")
    )


def try_parse_json_string(value: str) -> Any | None:
    candidate = value.strip()
    if not candidate or candidate[0] not in JSON_PREFIXES:
        return None
    # Parse JSON escapes first so outer wrappers like message.content stay valid.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    expanded = unescape_transport_string(value).strip()
    if expanded != candidate:
        try:
            return json.loads(expanded)
        except json.JSONDecodeError:
            pass
    return None


def deep_expand(value: Any, depth: int = 0) -> Any:
    """Recursively inline JSON-in-JSON strings and unescape text strings."""
    if depth >= MAX_EMBED_DEPTH:
        return value
    if isinstance(value, dict):
        return {key: deep_expand(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [deep_expand(item, depth + 1) for item in value]
    if isinstance(value, str):
        parsed = try_parse_json_string(value)
        if parsed is not None:
            return deep_expand(parsed, depth + 1)
        return unescape_transport_string(value)
    return value


def _is_multiline_string(value: str) -> bool:
    return "\n" in value or "\r" in value


def _escape_string_content(text: str) -> str:
    """Escape one line of JSON string content (no surrounding quotes)."""
    parts: list[str] = []
    for char in text:
        if char == '"':
            parts.append('\\"')
        elif char == "\\":
            parts.append("\\\\")
        elif char == "\t":
            parts.append("\t")
        elif ord(char) < 32:
            parts.append(f"\\u{ord(char):04x}")
        else:
            parts.append(char)
    return "".join(parts)


def _quote_string(value: str) -> str:
    """Quote a single-line string for inline JSON emission."""
    return json.dumps(value, ensure_ascii=False)


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _indent_of(prefix: str) -> str:
    """Leading whitespace for a key/value line — reused for string continuations."""
    return prefix[: len(prefix) - len(prefix.lstrip())]


def _append_multiline_string_entry(
    lines: list[str],
    prefix: str,
    value: str,
    comma: str,
) -> None:
    """Emit a multiline string with every content line indented under its key.

    Original leading spaces on each line (e.g. tree hierarchy) are preserved.
    """
    cont_indent = _indent_of(prefix) + " "
    content_lines = _normalize_newlines(value).split("\n")
    lines.append(prefix + '"')
    for index, line in enumerate(content_lines):
        escaped = _escape_string_content(line)
        if index == len(content_lines) - 1:
            lines.append(cont_indent + escaped + '"' + comma)
        else:
            lines.append(cont_indent + escaped)


def _append_structural_entry(
    lines: list[str],
    prefix: str,
    rendered: str,
    comma: str,
) -> None:
    rendered_lines = rendered.split("\n")
    if len(rendered_lines) == 1:
        lines.append(prefix + rendered_lines[0] + comma)
        return
    lines.append(prefix + rendered_lines[0])
    lines.extend(rendered_lines[1:-1])
    lines.append(rendered_lines[-1] + comma)


def human_json_dumps(value: Any, indent: int = 0, step: int = 2) -> str:
    """Pretty-print JSON with literal newlines inside any multiline string value."""
    pad = " " * indent
    pad_inner = " " * (indent + step)

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    if isinstance(value, str):
        return _quote_string(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        lines = ["["]
        for index, item in enumerate(value):
            comma = "," if index < len(value) - 1 else ""
            rendered = human_json_dumps(item, indent + step, step)
            if isinstance(item, str) and _is_multiline_string(item):
                _append_multiline_string_entry(lines, pad_inner, item, comma)
            else:
                _append_structural_entry(lines, pad_inner, rendered, comma)
        lines.append(pad + "]")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        items = list(value.items())
        for index, (key, item) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            key_json = json.dumps(str(key), ensure_ascii=False)
            rendered = human_json_dumps(item, indent + step, step)
            prefix = f"{pad_inner}{key_json}: "
            if isinstance(item, str) and _is_multiline_string(item):
                _append_multiline_string_entry(lines, prefix, item, comma)
            else:
                _append_structural_entry(lines, prefix, rendered, comma)
        lines.append(pad + "}")
        return "\n".join(lines)
    return json.dumps(value, ensure_ascii=False)


def dumps_pretty(obj: Any) -> str:
    return human_json_dumps(deep_expand(obj))


def detect_format(records: list[dict[str, Any]]) -> str:
    if not records:
        raise ValueError("input file is empty")
    sample = records[0]
    if sample.get("event") in {"brain_request", "brain_response"}:
        return "runtime_events"
    if "logged" in sample or "meta" in sample:
        return "xai_console"
    if any(r.get("event") == "brain_request" for r in records):
        return "runtime_events"
    raise ValueError(
        "unrecognized JSONL format: expected runtime brain events or xAI console logs"
    )


def seq_to_node(records: list[dict[str, Any]]) -> dict[int, str]:
    node = ""
    mapping: dict[int, str] = {}
    for record in records:
        if record.get("event") == "node_start":
            node = str(record.get("node") or "")
        if record.get("event") == "brain_request":
            mapping[int(record["seq"])] = node
    return mapping


def pair_runtime_events(records: list[dict[str, Any]]) -> list[Pair]:
    requests = {
        int(record["seq"]): record
        for record in records
        if record.get("event") == "brain_request"
    }
    responses = {
        int(record["seq"]): record
        for record in records
        if record.get("event") == "brain_response"
    }
    nodes = seq_to_node(records)
    pairs: list[Pair] = []
    for seq in sorted(requests):
        pairs.append(
            Pair(
                index=seq,
                request=requests[seq],
                response=responses.get(seq, {}),
                label=nodes.get(seq, ""),
            )
        )
    return pairs


def split_xai_console_record(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preserve the full console row; only split request vs response under logged.chat."""
    meta = record.get("meta")
    logged = record.get("logged") if isinstance(record.get("logged"), dict) else {}
    chat = logged.get("chat") if isinstance(logged.get("chat"), dict) else {}
    other_logged = {key: value for key, value in logged.items() if key != "chat"}
    request = {
        key: value for key, value in record.items() if key not in {"logged"}
    }
    response = {
        key: value for key, value in record.items() if key not in {"logged"}
    }
    request["logged"] = {
        **other_logged,
        "chat": {"request": chat.get("request", {})},
    }
    response["logged"] = {
        **other_logged,
        "chat": {"response": chat.get("response", {})},
    }
    return request, response


def pair_xai_console(records: list[dict[str, Any]]) -> list[Pair]:
    pairs: list[Pair] = []
    for index, record in enumerate(records, 1):
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        request, response = split_xai_console_record(record)
        label = str(meta.get("requestId") or meta.get("conversationId") or "")
        pairs.append(Pair(index=index, request=request, response=response, label=label))
    return pairs


def extract_pairs(records: list[dict[str, Any]], fmt: str) -> list[Pair]:
    if fmt == "runtime_events":
        return pair_runtime_events(records)
    if fmt == "xai_console":
        return pair_xai_console(records)
    raise ValueError(f"unsupported format: {fmt}")


def render_pair(pair: Pair, fmt: str) -> list[str]:
    if fmt == "runtime_events":
        header = f"## Seq {pair.index}"
        if pair.label:
            header += f" — `{pair.label}`"
    else:
        header = f"## Pair {pair.index}"
        if pair.label:
            header += f" — `{pair.label}`"

    lines = [header, ""]
    if fmt == "runtime_events" and pair.response:
        elapsed = pair.response.get("elapsed_s")
        if elapsed is not None:
            lines.extend([f"- **elapsed_s:** {elapsed}", ""])

    lines.extend(
        [
            "### Request",
            "",
            "```json",
            dumps_pretty(pair.request),
            "```",
            "",
            "### Response",
            "",
            "```json",
            dumps_pretty(pair.response),
            "```",
            "",
        ]
    )
    return lines


def write_phases(
    pairs: list[Pair],
    out_dir: Path,
    source: Path,
    fmt: str,
    per_phase: int,
) -> list[Path]:
    written: list[Path] = []
    for phase_idx in range(0, len(pairs), per_phase):
        chunk = pairs[phase_idx : phase_idx + per_phase]
        phase_no = phase_idx // per_phase + 1
        indices = [pair.index for pair in chunk]

        header = [
            f"# Phase {phase_no}",
            "",
            f"Source: `{source.name}`",
            f"Format: `{fmt}`",
            f"Pairs: {', '.join(map(str, indices))}",
            "",
            "Full records below. Embedded JSON strings are inlined; escape sequences expanded.",
            "Multiline strings use literal newlines for readability.",
            "No fields removed or redacted.",
            "",
        ]
        body: list[str] = []
        for pair in chunk:
            body.extend(["---", ""])
            body.extend(render_pair(pair, fmt))

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"phase{phase_no}.md"
        path.write_text("\n".join(header + body), encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export LLM request/response pairs from JSONL into phased markdown files"
    )
    ap.add_argument(
        "--input",
        "--events",
        dest="input_path",
        type=Path,
        default=None,
        help="JSONL input (runtime_events.jsonl or xAI console export)",
    )
    ap.add_argument("--out-dir", type=Path, default=ROOT)
    ap.add_argument("--per-phase", type=int, default=4)
    ap.add_argument(
        "--format",
        choices=("auto", "runtime_events", "xai_console"),
        default="auto",
        help="Input format (default: auto-detect)",
    )
    args = ap.parse_args()

    input_path = args.input_path
    if input_path is None:
        for candidate in (ROOT / "runtime_events.jsonl", ROOT / "SERVER-REQUESTS-RAW.jsonl"):
            if candidate.exists():
                input_path = candidate
                break
    if input_path is None or not input_path.exists():
        raise SystemExit("no input file found; pass --input PATH")

    records = load_jsonl(input_path)
    fmt = detect_format(records) if args.format == "auto" else args.format
    pairs = extract_pairs(records, fmt)
    written = write_phases(pairs, args.out_dir, input_path, fmt, args.per_phase)

    print(f"format={fmt}")
    print(f"pairs={len(pairs)}")
    for path in written:
        print(path, path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())