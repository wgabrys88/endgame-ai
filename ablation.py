"""Phase 0 ablation helpers: task fixtures and run metric summaries."""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


PHASE0_TASKS: list[dict[str, str]] = [
    {
        "id": "phase0_calc_notepad",
        "family": "desktop",
        "text": "open calculator, add two numbers, and get the result copied from the calculator into the notepad, save file on desktop.",
    },
    {
        "id": "phase0_youtube_waka_waka",
        "family": "browser",
        "text": "open chrome and play on youtube shakira waka waka",
    },
    {
        "id": "phase0_grok_code_review",
        "family": "external_ai",
        "text": "open chrome and use grok.com ai to provide to him the single source code file of the endgame-ai workspace and asking what endgame is why it is asking and asking for code review, then when the grok instructions are provided, the endgame-ai system must validate if they can be implemented and the implementation must happen and then system must find a way, to validate the changes, that the entire system will benefit from them, this actually must be explained via multiturn conversation with grok, so endgame-ai asks grok for review of file and then follows the grok suggestion and asks grok if needed for clarifications and treat grok as an persona that the endgame-ai system must be aware of , its a large remote ai model that can act as part of the system on demand of the system, the realization of that by the endgame-ai itself will be a succes",
    },
    {
        "id": "phase0_social_updates",
        "family": "browser",
        "text": "post on x.com and linkedin.com usin chrome an updates about endgame-ai evolution process and self maintenance on behalf of owners account",
    },
]


CORE_METRIC_FIELDS: tuple[str, ...] = (
    "task_success_rate",
    "first_pass_success",
    "external_verifier_agreement",
    "median_latency_ms",
    "p95_latency_ms",
    "tokens_per_solved_task",
    "bus_overhead_ratio",
    "solution_diversity",
    "mutation_uplift",
    "regression_rate",
    "crash_recovery_rate",
)


def task_by_id(task_id: str) -> dict[str, str] | None:
    wanted = task_id.strip()
    return next((task for task in PHASE0_TASKS if task["id"] == wanted), None)


def task_goal(task_id: str, fallback: str = "") -> str:
    task = task_by_id(task_id)
    return task["text"] if task else fallback


def _safe_slug(text: str, limit: int = 40) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    slug = "".join(out).strip("-")
    return (slug or "run")[:limit].strip("-")


def start_run(
    *,
    mode: str,
    goal: str,
    model_profile: str,
    session_dir: str,
    persona: str = "",
    task_id: str = "",
    slots_expected: int = 0,
) -> dict[str, Any]:
    run_mode = config.normalize_run_mode(mode)
    task = task_by_id(task_id) if task_id else None
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"{ts}_{run_mode}_{_safe_slug(task_id or goal or persona)}"
    run_dir = config.ABLATION_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "v": 1,
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": run_mode,
        "goal": goal,
        "task_id": task_id,
        "task": task,
        "model_profile": model_profile,
        "persona": persona,
        "slots_expected": slots_expected,
        "session_dir": session_dir,
        "phase0_tasks": PHASE0_TASKS,
        "core_metric_fields": list(CORE_METRIC_FIELDS),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"run_id": run_id, "run_dir": str(run_dir), "manifest": manifest}


def _parse_time(value: str) -> float | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                item["_source_file"] = path.name
                rows.append(item)
    except OSError:
        pass
    return rows


def _session_events(session_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in ("events*.jsonl", "events-child-s*.jsonl"):
        for raw in glob.glob(str(session_dir / pattern)):
            rows.extend(_read_jsonl(Path(raw)))
    return rows


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[idx]


def summarize_session(
    session_dir: str | Path,
    *,
    run_dir: str | Path | None = None,
    status: str = "running",
) -> dict[str, Any]:
    session_path = Path(session_dir)
    events = _session_events(session_path)
    phases: dict[str, int] = {}
    times: list[float] = []
    for ev in events:
        phase = str(ev.get("phase", ""))
        phases[phase] = phases.get(phase, 0) + 1
        ts = _parse_time(str(ev.get("t", "")))
        if ts is not None:
            times.append(ts)

    verify_confirmed = 0
    verify_denied = 0
    fissions = 0
    errors = 0
    mutations = 0
    respawns = phases.get("reactor.respawn", 0)
    llm_completion_tokens = 0
    llm_output_chars = 0
    llm_latencies: list[int] = []

    for ev in events:
        phase = str(ev.get("phase", ""))
        raw_data = ev.get("d")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        if phase == "verify":
            verdict = str(data.get("verdict", ""))
            if verdict == "confirmed":
                verify_confirmed += 1
            elif verdict == "denied":
                verify_denied += 1
        if phase == "fission":
            fissions += 1
        if phase in {"planner.error", "actor.error", "verifier.error", "fission.deny", "llm_fail"}:
            errors += 1
        if phase == "mutate" and str(data.get("action", "none")) != "none":
            mutations += 1
        if phase == "llm.response":
            llm_completion_tokens += int(data.get("completion_tokens", 0) or 0)
            llm_output_chars += int(data.get("output_chars", 0) or 0)
            if data.get("latency_ms") is not None:
                llm_latencies.append(int(data.get("latency_ms") or 0))

    bus_entries = []
    bus_chars = 0
    try:
        import comms
        bus_entries = comms.read_chat(config.BUS_CHAT_MAX)
        bus_chars = len(json.dumps(bus_entries, ensure_ascii=False))
    except Exception:
        bus_entries = []

    elapsed_ms = int((max(times) - min(times)) * 1000) if len(times) >= 2 else None
    verifier_total = verify_confirmed + verify_denied
    internal_success = (verify_confirmed / verifier_total) if verifier_total else None
    solved = max(fissions, 0)
    first_pass = None
    if solved:
        first_pass = 1.0 if verify_denied == 0 and errors == 0 and mutations == 0 else 0.0
    bus_denom = bus_chars + llm_output_chars

    core_metrics: dict[str, Any] = {
        "task_success_rate": internal_success,
        "first_pass_success": first_pass,
        "external_verifier_agreement": None,
        "median_latency_ms": int(statistics.median(llm_latencies)) if llm_latencies else elapsed_ms,
        "p95_latency_ms": _percentile(llm_latencies, 0.95) if llm_latencies else elapsed_ms,
        "tokens_per_solved_task": (llm_completion_tokens / solved) if solved else None,
        "bus_overhead_ratio": (bus_chars / bus_denom) if bus_denom else None,
        "solution_diversity": None,
        "mutation_uplift": None,
        "regression_rate": None,
        "crash_recovery_rate": None if respawns == 0 else 1.0,
    }
    missing = [name for name in CORE_METRIC_FIELDS if core_metrics.get(name) is None]
    summary: dict[str, Any] = {
        "v": 1,
        "status": status,
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_dir": str(session_path),
        "events": len(events),
        "phases": phases,
        "evidence": {
            "verify_confirmed": verify_confirmed,
            "verify_denied": verify_denied,
            "fissions": fissions,
            "errors": errors,
            "mutations": mutations,
            "respawns": respawns,
            "llm_completion_tokens": llm_completion_tokens,
            "llm_output_chars": llm_output_chars,
            "bus_entries": len(bus_entries),
            "bus_chars": bus_chars,
            "elapsed_ms": elapsed_ms,
        },
        "core_metrics": core_metrics,
        "manual_or_external_metrics_needed": missing,
    }
    if run_dir:
        out_dir = Path(run_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def latest_session() -> Path | None:
    sessions = sorted((config.BASE_DIR / "sessions").glob("*"))
    return sessions[-1] if sessions else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 ablation helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-tasks")
    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("--session", default="latest")
    p_sum.add_argument("--run-dir", default="")
    p_sum.add_argument("--status", default="manual")
    args = parser.parse_args()

    if args.cmd == "list-tasks":
        for task in PHASE0_TASKS:
            print(f"{task['id']}: {task['text']}")
        return
    if args.cmd == "summarize":
        session = latest_session() if args.session == "latest" else Path(args.session)
        if session is None:
            raise SystemExit("No sessions found")
        summary = summarize_session(session, run_dir=args.run_dir or None, status=args.status)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
