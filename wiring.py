"""Load endgame topology from prompts/wiring.json — hot-reload + suite runner."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from topology import export_mermaid, write_mermaid

_CACHE: dict[str, Any] | None = None
_MTIME: float = 0.0
WIRING_FILE = "wiring.json"


def wiring_path(prompts_dir: Path) -> Path:
    return prompts_dir / WIRING_FILE


def load_wiring(prompts_dir: Path, *, force: bool = False) -> dict[str, Any]:
    global _CACHE, _MTIME
    path = wiring_path(prompts_dir)
    if not path.exists():
        raise FileNotFoundError(f"Required config missing: {path}")
    mtime = path.stat().st_mtime
    if not force and _CACHE is not None and mtime == _MTIME:
        return _CACHE
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate(data)
    _resolve_context_templates(data)
    _CACHE = data
    _MTIME = mtime
    return data


def _resolve_context_templates(data: dict[str, Any]) -> None:
    ctx = data.get("context", {})
    blocks = data.get("request", {}).get("unified", {}).get("user", {}).get("blocks", [])
    for block in blocks:
        if block.get("id") == "screen" and block.get("empty_template") == "{screen_empty}":
            block["empty_template"] = ctx.get("screen_empty", "")


def _validate(data: dict[str, Any]) -> None:
    if data.get("schema") != "endgame-topology/v1":
        raise ValueError("wiring.json schema must be endgame-topology/v1")
    for key in ("instance", "startup", "limits", "slots", "circuits", "transitions",
                "verbs", "topology", "request", "response", "feedback", "runtime"):
        if key not in data:
            raise ValueError(f"wiring.json missing section: {key}")
    if data["instance"]["role"] not in ("manager", "student"):
        raise ValueError("instance.role must be manager or student")
    slot = str(data["startup"].get("slot", ""))
    enabled = {n for n, c in data["slots"].items() if c.get("enabled", True)}
    if slot not in enabled:
        raise ValueError(f"startup.slot '{slot}' not enabled")
    if "default" not in data["transitions"]:
        raise ValueError("transitions.default required")
    valid = set(data["circuits"]) | {"idle"}
    for event, target in data["transitions"].items():
        if event != "default" and target not in valid:
            raise ValueError(f"invalid transition {event} -> {target}")
    if "unified" not in data["response"]:
        raise ValueError("response.unified required")
    if "unified" not in data["request"]:
        raise ValueError("request.unified required")
    topo = data["topology"]
    if not topo.get("nodes") or not topo.get("edges"):
        raise ValueError("topology.nodes and topology.edges required")


def parse_tui_log(text: str) -> dict[str, str]:
    m_sys = re.search(r"SYSTEM:\s*\n(.*?)\n\nUSER:\s*\n", text, re.S)
    m_user = re.search(r"\nUSER:\s*\n(.*?)\n20\d\d-\d\d-\d\d .*?RESPONSE", text, re.S)
    m_content = re.search(r"RESPONSE \[.*?\]\s*\nCONTENT:\s*\n(.*?)(?:\n\nREASONING:|\Z)", text, re.S)
    m_reason = re.search(r"REASONING:\s*\n(.*?)(?:\n20\d\d-\d\d-\d\d .*?\[|\Z)", text, re.S)
    return {
        "system": (m_sys.group(1) if m_sys else "").rstrip(),
        "user": (m_user.group(1) if m_user else "").rstrip(),
        "content": (m_content.group(1) if m_content else "").rstrip(),
        "reasoning": (m_reason.group(1) if m_reason else "").rstrip(),
    }


def _latest_log_after(logs_dir: Path, before: set[str]) -> Path:
    logs_dir.mkdir(exist_ok=True)
    new_logs = [p for p in logs_dir.glob("*.txt") if p.name not in before]
    pool = new_logs or list(logs_dir.glob("*.txt"))
    if not pool:
        raise FileNotFoundError("No tui log files found")
    return max(pool, key=lambda p: p.stat().st_mtime)


def run_suite(
    suite_name: str,
    *,
    prompts_dir: Path,
    workspace: Path,
    scenario_id: str | None = None,
    response_limit: int | None = None,
    no_desktop: bool | None = None,
) -> Path:
    """Run a wiring.suites chain — each step spawns tui.py then collects logs."""
    wiring = load_wiring(prompts_dir, force=True)
    suites = wiring.get("suites", {})
    if suite_name not in suites:
        raise KeyError(f"Unknown suite: {suite_name}")
    suite = suites[suite_name]
    defaults = suite.get("defaults", {})
    chain = suite.get("chain", [])
    if scenario_id:
        chain = [s for s in chain if str(s.get("id", "")).lower() == scenario_id.lower()]
        if not chain:
            raise KeyError(f"Unknown scenario id: {scenario_id}")
    limit = response_limit if response_limit is not None else int(defaults.get("response_limit", 1))
    nd = no_desktop if no_desktop is not None else bool(defaults.get("no_desktop", True))
    logs_dir = workspace / "logs"
    report_rel = str(suite.get("report", f"prompts/{suite_name}_report.txt"))
    report_path = workspace / report_rel
    log_dir = workspace / str(suite.get("log_dir", f"logs/{suite_name}"))
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sections: list[str] = []

    for step in chain:
        before = {p.name for p in logs_dir.glob("*.txt")}
        cmd = [sys.executable, "tui.py", str(step["goal"]), str(limit)]
        if nd:
            cmd.append("--no-desktop")
        proc = subprocess.run(cmd, cwd=workspace)
        log_path = _latest_log_after(logs_dir, before)
        parsed = parse_tui_log(log_path.read_text(encoding="utf-8", errors="replace"))
        sid = str(step.get("id", "?"))
        name = str(step.get("name", sid))
        sections.append("\n".join([
            "=" * 80,
            f"{sid.upper()} — {name}",
            "=" * 80,
            f"GOAL: {step['goal']}",
            f"LOG: {log_path}",
            f"EXIT: {proc.returncode}",
            "",
            "--- SYSTEM PROMPT ---",
            parsed["system"],
            "",
            "--- USER CONTEXT ---",
            parsed["user"],
            "",
            "--- MODEL CONTENT ---",
            parsed["content"],
            "",
            "--- MODEL REASONING ---",
            parsed["reasoning"],
            "",
        ]))

    header = (
        f"endgame-ai {suite_name} suite report\n"
        f"generated: {stamp}\n"
        f"scenarios: {len(chain)}\n"
        f"response_limit: {limit}\n"
        f"no_desktop: {nd}\n"
        "\n"
    )
    body = header + "\n".join(sections)
    stamped = log_dir / f"report_{stamp}.txt"
    stamped.write_text(body, encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(body, encoding="utf-8")
    return report_path


def main() -> int:
    prompts = Path(__file__).parent / "prompts"
    workspace = Path(__file__).parent
    if len(sys.argv) < 2:
        print("Usage: python wiring.py mermaid | suite <name> [--id s01]", file=sys.stderr)
        return 1
    if sys.argv[1] == "mermaid":
        data = load_wiring(prompts, force=True)
        out = prompts / "wiring.mmd"
        write_mermaid(data, out)
        print(f"Wrote {out}")
        return 0
    if sys.argv[1] == "suite":
        if len(sys.argv) < 3:
            print("Usage: python wiring.py suite <name> [--id s01]", file=sys.stderr)
            return 1
        name = sys.argv[2]
        sid = None
        if "--id" in sys.argv:
            sid = sys.argv[sys.argv.index("--id") + 1]
        path = run_suite(name, prompts_dir=prompts, workspace=workspace, scenario_id=sid)
        print(f"Report: {path}")
        return 0
    print(f"Unknown command: {sys.argv[1]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())