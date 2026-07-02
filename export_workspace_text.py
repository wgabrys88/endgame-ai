"""Export the current workspace into one NotebookLM-ready text bundle.

The exporter is intentionally local-only. It reads files from the checked-out
workspace, including ignored runtime logs/state when present, and writes a
single .txt file under notebooklm_exports/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import os
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Iterable


ROOT = pathlib.Path(__file__).parent.resolve()
DEFAULT_OUTPUT_DIR = ROOT / "notebooklm_exports"
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".vscode",
    ".idea",
    "__pycache__",
    "notebooklm_exports",
}
SECRET_PATTERNS = {
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
}
TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".css",
    ".csv",
    ".gitattributes",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".ndjson",
    ".ps1",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class FileRecord:
    path: pathlib.Path
    rel: str
    size: int
    sha256: str
    text: str | None
    note: str


def _git(args: list[str]) -> str:
    cp = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp.stdout.strip()


def _is_secret(rel: str) -> bool:
    name = pathlib.PurePosixPath(rel).name
    return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern) for pattern in SECRET_PATTERNS)


def _should_skip_dir(path: pathlib.Path) -> bool:
    return path.name in SKIP_DIRS


def iter_workspace_files(include_secrets: bool = False) -> Iterable[pathlib.Path]:
    for current, dirs, files in os.walk(ROOT):
        base = pathlib.Path(current)
        dirs[:] = sorted(d for d in dirs if not _should_skip_dir(base / d))
        for name in sorted(files):
            path = base / name
            rel = path.relative_to(ROOT).as_posix()
            if not include_secrets and _is_secret(rel):
                continue
            yield path


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decode_text(raw: bytes, suffix: str) -> tuple[str | None, str]:
    if b"\x00" in raw[:4096] and suffix not in TEXT_SUFFIXES:
        return None, "binary_or_null_bytes"
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding), f"text:{encoding}"
        except UnicodeDecodeError:
            continue
    return None, "binary_or_unknown_encoding"


def read_file_record(path: pathlib.Path) -> FileRecord:
    raw = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()
    text, note = _decode_text(raw, path.suffix.lower() or path.name)
    return FileRecord(
        path=path,
        rel=rel,
        size=len(raw),
        sha256=_sha256(raw),
        text=text,
        note=note,
    )


def render_bundle(records: list[FileRecord], include_secrets: bool) -> str:
    now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    head = _git(["rev-parse", "HEAD"])
    branch = _git(["branch", "--show-current"])
    status = _git(["status", "--short"]) or "clean"
    lines: list[str] = [
        "ENDGAME-AI WORKSPACE TEXT EXPORT",
        f"generated_at: {now}",
        f"repo_root: {ROOT}",
        f"branch: {branch}",
        f"commit: {head}",
        f"git_status: {status}",
        f"include_secrets: {include_secrets}",
        f"file_count: {len(records)}",
        "",
        "MANIFEST",
    ]
    for record in records:
        lines.append(f"- {record.rel} | bytes={record.size} | sha256={record.sha256} | {record.note}")
    lines.append("")
    lines.append("FILES")

    for record in records:
        lines.append("")
        lines.append(f"===== BEGIN FILE: {record.rel} =====")
        lines.append(f"bytes: {record.size}")
        lines.append(f"sha256: {record.sha256}")
        lines.append(f"classification: {record.note}")
        lines.append("")
        if record.text is None:
            lines.append("[binary or unknown encoding: content omitted; manifest keeps size and sha256]")
        else:
            lines.append(record.text)
            if record.text and not record.text.endswith("\n"):
                lines.append("")
        lines.append(f"===== END FILE: {record.rel} =====")
    return "\n".join(lines)


def default_output_path(output_dir: pathlib.Path) -> pathlib.Path:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    return output_dir / f"endgame-ai-workspace-{stamp}.txt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export workspace files into one NotebookLM-ready .txt bundle.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Folder for generated .txt bundles.")
    parser.add_argument("--output", default="", help="Exact output .txt path. Overrides --output-dir.")
    parser.add_argument("--include-secrets", action="store_true", help="Include .env/key/certificate-like files.")
    args = parser.parse_args(argv)

    output_dir = pathlib.Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output = pathlib.Path(args.output).expanduser() if args.output else default_output_path(output_dir)
    if not output.is_absolute():
        output = ROOT / output

    output.parent.mkdir(parents=True, exist_ok=True)
    records = [read_file_record(path) for path in iter_workspace_files(include_secrets=args.include_secrets)]
    bundle = render_bundle(records, include_secrets=args.include_secrets)
    output.write_text(bundle, encoding="utf-8", newline="\n")
    print(output)
    print(f"files={len(records)} bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
