"""Cognitive smoke probes — run one-LLM-response scenarios and capture full reasoning."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"
SMOKE_PATH = PROMPTS_DIR / "smoke.txt"
REPORT_PATH = PROMPTS_DIR / "smoke_report.txt"
LOG_DIR = BASE_DIR / "logs" / "smoke"


@dataclass
class Scenario:
    sid: str
    name: str
    goal: str


@dataclass
class ProbeResult:
    scenario: Scenario
    system: str
    user: str
    content: str
    reasoning: str
    log_path: str
    exit_code: int


def _coerce(value: str) -> Any:
    v = value.strip()
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low.isdigit():
        return int(low)
    return v


def load_smoke(path: Path = SMOKE_PATH) -> tuple[dict[str, Any], list[Scenario]]:
    if not path.exists():
        raise FileNotFoundError(f"Smoke config missing: {path}")
    meta: dict[str, Any] = {}
    raw: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            raise ValueError(f"Invalid smoke line: {text}")
        key, value = text.split("=", 1)
        key, value = key.strip(), value.strip()
        parts = key.split(".")
        if parts[0] == "smoke" and len(parts) == 2:
            meta[parts[1]] = _coerce(value)
            continue
        if parts[0] == "scenarios" and len(parts) == 3:
            raw.setdefault(parts[1], {})[parts[2]] = value
            continue
        raise ValueError(f"Unknown smoke key: {key}")
    scenarios = [
        Scenario(sid=sid, name=cfg["name"], goal=cfg["goal"])
        for sid, cfg in sorted(raw.items())
        if cfg.get("name") and cfg.get("goal")
    ]
    if not scenarios:
        raise ValueError("smoke.txt defines no scenarios")
    return meta, scenarios


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


def _latest_log_after(before: set[str]) -> Path:
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    new_logs = [p for p in logs_dir.glob("*.txt") if p.name not in before]
    pool = new_logs or list(logs_dir.glob("*.txt"))
    if not pool:
        raise FileNotFoundError("No tui log files found")
    return max(pool, key=lambda p: p.stat().st_mtime)


def run_scenario(scenario: Scenario, responses: int, no_desktop: bool) -> ProbeResult:
    before = {p.name for p in (BASE_DIR / "logs").glob("*.txt")}
    cmd = [sys.executable, "tui.py", scenario.goal, str(responses)]
    if no_desktop:
        cmd.append("--no-desktop")
    proc = subprocess.run(cmd, cwd=BASE_DIR)
    log_path = _latest_log_after(before)
    parsed = parse_tui_log(log_path.read_text(encoding="utf-8", errors="replace"))
    return ProbeResult(
        scenario=scenario,
        system=parsed["system"],
        user=parsed["user"],
        content=parsed["content"],
        reasoning=parsed["reasoning"],
        log_path=str(log_path),
        exit_code=proc.returncode,
    )


def format_probe(result: ProbeResult) -> str:
    s = result.scenario
    lines = [
        "=" * 80,
        f"{s.sid.upper()} — {s.name}",
        "=" * 80,
        f"GOAL: {s.goal}",
        f"LOG: {result.log_path}",
        f"EXIT: {result.exit_code}",
        "",
        "--- SYSTEM PROMPT ---",
        result.system,
        "",
        "--- USER CONTEXT ---",
        result.user,
        "",
        "--- MODEL CONTENT ---",
        result.content,
        "",
        "--- MODEL REASONING ---",
        result.reasoning,
        "",
    ]
    return "\n".join(lines)


def write_report(results: list[ProbeResult], stamp: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(format_probe(r) for r in results)
    header = (
        f"endgame-ai cognitive smoke report\n"
        f"generated: {stamp}\n"
        f"scenarios: {len(results)}\n"
        f"mode: {results[0].scenario.sid if results else 'n/a'} one-response probes\n"
        "\n"
    )
    stamped = LOG_DIR / f"report_{stamp}.txt"
    stamped.write_text(header + body, encoding="utf-8")
    REPORT_PATH.write_text(header + body, encoding="utf-8")
    return stamped


def load_results_from_logs(scenarios: list[Scenario], log_paths: list[Path]) -> list[ProbeResult]:
    if len(log_paths) != len(scenarios):
        raise ValueError(f"Expected {len(scenarios)} logs, got {len(log_paths)}")
    results: list[ProbeResult] = []
    for scenario, log_path in zip(scenarios, log_paths):
        parsed = parse_tui_log(log_path.read_text(encoding="utf-8", errors="replace"))
        results.append(ProbeResult(
            scenario=scenario,
            system=parsed["system"],
            user=parsed["user"],
            content=parsed["content"],
            reasoning=parsed["reasoning"],
            log_path=str(log_path),
            exit_code=0,
        ))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(prog="smoke", description="Run cognitive smoke probes (full reasoning capture)")
    parser.add_argument("--id", help="Run single scenario id (e.g. s01)")
    parser.add_argument("--responses", type=int, help="LLM responses before exit (default: smoke.responses)")
    parser.add_argument("--desktop", action="store_true", help="Enable desktop observation")
    parser.add_argument("--from-logs", nargs="*", metavar="LOG", help="Rebuild report from existing tui logs (ordered)")
    args = parser.parse_args()

    meta, scenarios = load_smoke()
    if args.id:
        scenarios = [s for s in scenarios if s.sid == args.id.lower()]
        if not scenarios:
            raise SystemExit(f"Unknown scenario id: {args.id}")

    responses = args.responses if args.responses is not None else int(meta.get("responses", 1))
    no_desktop = not args.desktop and bool(meta.get("no_desktop", True))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.from_logs is not None:
        if args.from_logs:
            log_paths = [Path(p) for p in args.from_logs]
        else:
            logs = sorted((BASE_DIR / "logs").glob("202*.txt"), key=lambda p: p.stat().st_mtime)
            log_paths = logs[-len(scenarios):]
        results = load_results_from_logs(scenarios, log_paths)
    else:
        results = [run_scenario(s, responses, no_desktop) for s in scenarios]

    report_path = write_report(results, stamp)
    for result in results:
        print(format_probe(result))
    print(f"\nReport written: {report_path}")
    print(f"Canonical copy: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())