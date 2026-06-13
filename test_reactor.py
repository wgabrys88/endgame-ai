"""Autonomous reactor test harness.

Spawns a limited number of endgame-ai agents (default 2) on localhost,
observes their logs/events for a fixed duration, then kills the tree and
writes a report. Designed to never block forever.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import config
import log

BASE = config.BASE_DIR
REPORT_PATH = BASE / "runtime" / "comms" / "test_report.md"
SUMMARY_PATH = BASE / "runtime" / "comms" / "test_summary.json"
DEFAULT_DURATION = 60.0


def _kill_tree(pid: int) -> None:
    """Kill a Windows process tree by PID."""
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _running(pid: int) -> bool:
    """Return True if the process is still alive."""
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return str(pid) in proc.stdout
    except Exception:
        return False


def _collect_events() -> dict[str, list[dict[str, Any]]]:
    """Read all events-child-*.jsonl files."""
    result: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(BASE.glob("events-child-*.jsonl")):
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
        result[path.name] = rows
    return result


def _summarize(events: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    per_agent: dict[str, Any] = {}
    total_fissions = 0
    total_errors = 0
    total_actor = 0
    total_actor_ok = 0
    for name, rows in events.items():
        fissions = sum(1 for r in rows if r.get("phase") == "fission")
        errors = sum(1 for r in rows if isinstance(r.get("phase"), str) and r["phase"].endswith(".error"))
        actor_rows = [r for r in rows if r.get("phase") == "actor"]
        actor_ok = sum(1 for r in actor_rows if (r.get("d") or {}).get("ok"))
        total_fissions += fissions
        total_errors += errors
        total_actor += len(actor_rows)
        total_actor_ok += actor_ok
        phases: dict[str, int] = {}
        for r in rows:
            ph = str(r.get("phase", "?"))
            phases[ph] = phases.get(ph, 0) + 1
        per_agent[name] = {
            "events": len(rows),
            "fissions": fissions,
            "errors": errors,
            "actor_ok": actor_ok,
            "actor_total": len(actor_rows),
            "phases": phases,
        }
    return {
        "agents": per_agent,
        "total_fissions": total_fissions,
        "total_errors": total_errors,
        "total_actor": total_actor,
        "total_actor_ok": total_actor_ok,
        "success_rate": round(total_actor_ok / max(total_actor, 1), 3),
    }


def _drain_stdout(stdout, output: list[str]) -> None:
    """Daemon thread: read stdout line-by-line until EOF."""
    try:
        for line in iter(stdout.readline, ""):
            output.append(line)
    except Exception:
        pass


def _write_report(summary: dict[str, Any], duration: float, alive: bool) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Reactor Test Report",
        "",
        f"**Duration:** {duration:.1f}s",
        f"**Reactor alive at end:** {alive}",
        f"**Total fissions:** {summary['total_fissions']}",
        f"**Total errors:** {summary['total_errors']}",
        f"**Actor success rate:** {summary['success_rate']:.1%} ({summary['total_actor_ok']}/{summary['total_actor']})",
        "",
        "## Per-agent summary",
        "",
        "| Agent | Events | Fissions | Errors | Actor OK | Phases |",
        "|-------|--------|----------|--------|----------|--------|",
    ]
    for name, s in summary["agents"].items():
        phase_summary = ", ".join(f"{k}={v}" for k, v in sorted(s["phases"].items())[:6])
        lines.append(
            f"| {name} | {s['events']} | {s['fissions']} | {s['errors']} | "
            f"{s['actor_ok']}/{s['actor_total']} | {phase_summary} |"
        )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION
    print(f"[test_reactor] Cleaning runtime and starting 2-slot localhost test for {duration:.0f}s")

    log.cleanup_runtime(kill_reactor=True)

    env = os.environ.copy()
    env["ENDGAME_REACTOR_SLOTS"] = "2"
    env["ENDGAME_LMS_MAX_SLOTS_PER_HOST"] = "2"
    env["ENDGAME_LMS_HOSTS"] = "http://localhost:1234"
    env["ENDGAME_ROSTER"] = json.dumps({1: "test_alpha", 2: "test_beta"})
    env["ENDGAME_BOOTSTRAPPED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "reactor.py"],
        cwd=str(BASE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
    )

    print(f"[test_reactor] Reactor PID {proc.pid}")
    start = time.time()
    output_chunks: list[str] = []
    drainer = threading.Thread(
        target=_drain_stdout,
        args=(proc.stdout, output_chunks),
        daemon=True,
    )
    drainer.start()

    try:
        while time.time() - start < duration:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[test_reactor] Interrupted by user")

    alive = _running(proc.pid)
    print(f"[test_reactor] Test window ended. Alive={alive}. Killing tree...")
    _kill_tree(proc.pid)
    proc.wait(timeout=10)
    drainer.join(timeout=2)

    events = _collect_events()
    summary = _summarize(events)
    _write_report(summary, time.time() - start, alive)

    stdout_log = BASE / "runtime" / "comms" / "test_reactor_stdout.txt"
    stdout_log.write_text("".join(output_chunks), encoding="utf-8")

    print(f"[test_reactor] Report: {REPORT_PATH}")
    print(f"[test_reactor] Summary: {SUMMARY_PATH}")
    print(f"[test_reactor] Stdout: {stdout_log}")
    print(f"[test_reactor] Fissions={summary['total_fissions']} Errors={summary['total_errors']} Success={summary['success_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
