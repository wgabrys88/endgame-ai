"""Full 6-slot reactor test harness.

Spawns the complete default colony roster on localhost:
n1 git_expert, n2 implementor, n3 doc_inspector,
n4 comms_operator, n5 quality_critic, n6 gui_operator.

Observes logs/events for a fixed duration, then kills the tree and writes a report.
Designed to never block forever.
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
DEFAULT_DURATION = 360.0


def _report_paths(model: str) -> tuple[Path, Path]:
    suffix = f"_{model}" if model else ""
    report = BASE / "runtime" / "comms" / f"full_report{suffix}.md"
    summary = BASE / "runtime" / "comms" / f"full_summary{suffix}.json"
    return report, summary


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


def _write_report(summary: dict[str, Any], duration: float, alive: bool, model: str) -> tuple[Path, Path]:
    report_path, summary_path = _report_paths(model)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Full 6-Slot Reactor Test Report",
        "",
        f"**Model:** {model}",
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
    report_path.write_text("\n".join(lines), encoding="utf-8")

    full_summary = dict(summary)
    full_summary["model"] = model or "default"
    full_summary["duration"] = round(duration, 1)
    full_summary["alive_at_end"] = alive
    summary_path.write_text(json.dumps(full_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path, summary_path


def _parse_args(argv: list[str]) -> tuple[float, str]:
    duration = DEFAULT_DURATION
    model = ""
    for arg in argv[1:]:
        if arg.startswith("--model="):
            model = arg.split("=", 1)[1].strip()
        elif arg.startswith("--"):
            continue
        else:
            try:
                duration = float(arg)
            except ValueError:
                pass
    return duration, model


def main() -> int:
    duration, model = _parse_args(sys.argv)
    print(
        f"[test_reactor_full] Cleaning runtime and starting 6-slot full colony test "
        f"for {duration:.0f}s (model={model or 'default'})"
    )

    log.cleanup_runtime(kill_reactor=True)

    env = os.environ.copy()
    env["ENDGAME_REACTOR_SLOTS"] = "6"
    env["ENDGAME_LMS_MAX_SLOTS_PER_HOST"] = "6"
    env["ENDGAME_LMS_HOSTS"] = "http://localhost:1234"
    env["ENDGAME_BOOTSTRAPPED"] = "1"
    if model:
        env["ENDGAME_LMS_MODEL"] = model

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

    print(f"[test_reactor_full] Reactor PID {proc.pid}")
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
        print("[test_reactor_full] Interrupted by user")

    alive = _running(proc.pid)
    print(f"[test_reactor_full] Test window ended. Alive={alive}. Killing tree...")
    _kill_tree(proc.pid)
    proc.wait(timeout=10)
    drainer.join(timeout=2)

    events = _collect_events()
    summary = _summarize(events)
    report_path, summary_path = _write_report(summary, time.time() - start, alive, model or "default")

    stdout_log = BASE / "runtime" / "comms" / f"test_reactor_full_stdout{('_' + model) if model else ''}.txt"
    stdout_log.write_text("".join(output_chunks), encoding="utf-8")

    print(f"[test_reactor_full] Report: {report_path}")
    print(f"[test_reactor_full] Summary: {summary_path}")
    print(f"[test_reactor_full] Stdout: {stdout_log}")
    print(f"[test_reactor_full] Fissions={summary['total_fissions']} Errors={summary['total_errors']} Success={summary['success_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
