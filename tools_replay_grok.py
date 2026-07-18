"""tools_replay_grok.py — replay and MUTATE a logged brain moment to prove behavioral hypotheses.

The GROKAPI request-log stores each moment's FULL body (bodyAvailability=AVAILABLE): the
whole system prompt (shared prefix + node prompt + downstream contract), the whole user tail
(deed, focus, observation, and the living word), and the exact responseFormat schema. This
tool reconstructs the EXACT messages of a chosen log line and re-sends them through the LIVE
transport, so a past decision can be re-run and A/B tested against a prompt we believe is
better — the empirical seam for every deduction about the organism's soul (its prompts).

Statelessness: the organism's transport already sends store=false to /v1/responses, so no
conversation is carried server-side; each replay is an independent waking. There is no
conversation id to rotate — store=false IS the rotation. Nothing from one replay leaks
into the next.

The record is what proves behavior: the executor's authored [intent]+[code], the
verifier's [goal_interpretation]+probe [code]. Replaying original vs mutated and diffing
these fields shows whether a soul-level (prompt) change moves behavior — without ever
touching the body (the .py) or running on the real desktop.

Usage (run on Windows via powershell so XAI_API_KEY is in env):
  python .\tools_replay_grok.py GROKAPI-server-logs.jsonl --line 1
  python .\tools_replay_grok.py GROKAPI-server-logs.jsonl --line 1 --system-file mut_system.txt
  python .\tools_replay_grok.py GROKAPI-server-logs.jsonl --line 1 --sub "OLD LITERAL::NEW LITERAL"
  python .\tools_replay_grok.py GROKAPI-server-logs.jsonl --line 1 --user-file  mut_user.txt
  python .\tools_replay_grok.py GROKAPI-server-logs.jsonl --line 1 --field-only   # print record fields, no resend
"""
from __future__ import annotations

import argparse
import argparse
import json
from typing import Any

import core_brain as brain
import core_wiring as wiring
import transport_xai as transport
import tools_parse_requests as parse

# record_type -> the node that emits it (for response_format emergent-signal resolution)
_EMITTING_NODE = {"execution": "node_execute", "verification": "node_verify", "recovery": "node_recover"}
_ROLE = {"ROLE_SYSTEM": "system", "ROLE_USER": "user", "ROLE_ASSISTANT": "assistant", "system": "system", "user": "user", "assistant": "assistant"}


def _line(path: str, n: int) -> dict[str, Any]:
    for i, obj in parse.load(path):
        if i == n:
            return obj
    raise SystemExit(f"line {n} not found in {path}")


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return str(content or "")


def _messages(obj: dict[str, Any]) -> list[dict[str, str]]:
    raw = parse._dig(parse._request(obj), "messages", "input") or []
    out = []
    for m in raw:
        role = _ROLE.get(m.get("role", ""), "user")
        out.append({"role": role, "content": _text(m.get("content"))})
    return out


def _record_type(obj: dict[str, Any]) -> str:
    return parse._rtype(obj) if parse._rtype(obj) != "?" else ""


def _committed_record(content: str) -> dict[str, Any]:
    rec = brain.extract_json_object(content)
    return rec if isinstance(rec, dict) else {"_unparsed": content[:400]}


def _apply_mutations(messages: list[dict[str, str]], args) -> list[dict[str, str]]:
    msgs = [dict(m) for m in messages]
    sys_idx = next((i for i, m in enumerate(msgs) if m["role"] == "system"), None)
    usr_idx = next((i for i, m in enumerate(msgs) if m["role"] == "user"), None)
    if args.system_file is not None and sys_idx is not None:
        msgs[sys_idx]["content"] = open(args.system_file, encoding="utf-8").read()
    if args.user_file is not None and usr_idx is not None:
        msgs[usr_idx]["content"] = open(args.user_file, encoding="utf-8").read()
    if args.sub and sys_idx is not None:
        old, _, new = args.sub.partition("::")
        if old not in msgs[sys_idx]["content"]:
            raise SystemExit(f"--sub literal not found in system prompt: {old!r}")
        msgs[sys_idx]["content"] = msgs[sys_idx]["content"].replace(old, new)
    return msgs


def _send(messages: list[dict[str, str]], w: dict[str, Any], record_type: str) -> dict[str, Any]:
    _, cfg = wiring.get_transport_config(w)
    node = _EMITTING_NODE.get(record_type)
    response_format = brain._record_response_format(w, record_type, node) if record_type else None
    result = transport.call(messages, cfg, response_format=response_format)
    return _committed_record(result["content"])


def _show(tag: str, record_type: str, rec: dict[str, Any]) -> None:
    data = rec.get("data", {}) if isinstance(rec, dict) else {}
    print(f"\n===== {tag} [{record_type or rec.get('record_type')}] =====")
    for field in ("goal_interpretation", "intent", "lesson", "target", "strategy", "perceived"):
        v = data.get(field)
        if v:
            print(f"--- {field}:\n{str(v).strip()}")
    code = data.get("code")
    if code:
        print(f"--- code ({len(code)} chars):\n{code}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", nargs="?", default=None, help="log path; omit to autodetect newest *.jsonl")
    ap.add_argument("--line", type=int, required=True)
    ap.add_argument("--system-file", default=None, help="replace the system prompt with this file's text")
    ap.add_argument("--user-file", default=None, help="replace the user tail with this file's text")
    ap.add_argument("--sub", default=None, help="literal 'OLD::NEW' substring swap in the system prompt")
    ap.add_argument("--field-only", action="store_true", help="print the logged record's fields; do not resend")
    args = ap.parse_args(argv)

    path = parse.autodetect(args.log)
    obj = _line(path, args.line)
    record_type = _record_type(obj)
    messages = _messages(obj)

    logged_content = parse._content(obj)
    _show("LOGGED (as it happened)", record_type, _committed_record(logged_content))
    if args.field_only:
        return 0

    w = wiring.load_wiring()

    original = _send(messages, w, record_type)
    _show("REPLAY original prompt (stateless re-run)", record_type, original)

    if args.system_file or args.user_file or args.sub:
        mutated_msgs = _apply_mutations(messages, args)
        mutated = _send(mutated_msgs, w, record_type)
        _show("REPLAY MUTATED prompt (hypothesis under test)", record_type, mutated)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
