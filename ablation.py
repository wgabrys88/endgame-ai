"""Phase 0 ablation helpers: task fixtures and run metric summaries."""
from __future__ import annotations

import argparse
from collections import Counter
import glob
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
import log


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

COMMITTED_RUNS_DIR: Path = config.BASE_DIR / "ablation_runs"
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
LMSTUDIO_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
LMSTUDIO_CONTROL_RE = re.compile(
    r"(ERROR|WARN|stop: cancel task|timeout|Timeout|abort|Abort|socket|ECONN|queue|concurrent)",
    re.IGNORECASE,
)
ACTIVE_TASK_RE = re.compile(r"ACTIVE_TASK:\s*(.*)")
TRACE_REQUEST_PATTERNS: dict[str, str] = {
    "placeholder_user_path": r"C:\\Users\\user",
    "fake_workspace_path": r"C:\\endgame-ai",
    "plugins_x": "plugins/x.py",
    "unknown_key": "unknown key:",
}
TRACE_RESPONSE_PATTERNS: dict[str, str] = {
    "pyperclip": "pyperclip",
    "bare_start_call": 'subprocess.run(["start"',
    "desktop_hotkey_plus": "desktop_hotkey(['+'])",
    "desktop_press_plus": "desktop_press('+')",
}


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
    seen: set[Path] = set()
    for pattern in ("events*.jsonl", "events-child-s*.jsonl"):
        for raw in glob.glob(str(session_dir / pattern)):
            path = Path(raw).resolve()
            if path in seen:
                continue
            seen.add(path)
            rows.extend(_read_jsonl(path))
    return rows


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[idx]


def _event_time(ev: dict[str, Any]) -> float:
    return _parse_time(str(ev.get("t", ""))) or 0.0


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda ev: (_event_time(ev), str(ev.get("_source_file", "")), int(ev.get("n", 0) or 0)))


def _short(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text).split())
    return clean[:limit]


def _event_data(ev: dict[str, Any]) -> dict[str, Any]:
    raw = ev.get("d")
    return raw if isinstance(raw, dict) else {}


def _diagnose_session_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    actor_failures: Counter[str] = Counter()
    plugin_errors: Counter[str] = Counter()
    continued_after_failure: list[dict[str, Any]] = []
    failed_actor: dict[str, Any] | None = None
    last_phase = ""

    for ev in _sorted_events(events):
        phase = str(ev.get("phase", ""))
        data = _event_data(ev)
        text = json.dumps(data, ensure_ascii=False)
        last_phase = phase or last_phase

        if phase == "plugin.error":
            counts["plugin_error"] += 1
            plugin_errors[_short(f"{data.get('name', '')}: {data.get('error', '')}")] += 1
        if "unknown key:" in text:
            counts["unknown_key"] += 1
        if "timeout after" in text:
            counts["python_timeout"] += 1
        if "ModuleNotFoundError" in text:
            counts["module_missing"] += 1
        if "SyntaxError" in text:
            counts["syntax_error"] += 1
        if "unicodeescape" in text:
            counts["unicodeescape"] += 1
        if "FileNotFoundError" in text:
            counts["file_not_found"] += 1
        if "no window matching" in text:
            counts["no_window_matching"] += 1
        if "skipped_after_failure" in text or "SKIPPED after failed step" in text:
            counts["skipped_after_failure"] += 1

        if phase == "actor":
            ok = bool(data.get("ok", True))
            if not ok:
                failed_actor = ev
                actor_failures[_short(str(data.get("obs", "")))] += 1
            elif failed_actor is not None:
                continued_after_failure.append({
                    "failed_event": int(failed_actor.get("n", 0) or 0),
                    "continued_event": int(ev.get("n", 0) or 0),
                    "continued_obs": _short(str(data.get("obs", ""))),
                })
        elif phase in {"verify", "reflect", "planner.pending", "plan"}:
            failed_actor = None

    return {
        "last_phase": last_phase,
        "counts": dict(sorted(counts.items())),
        "top_actor_failures": [{"obs": obs, "count": count} for obs, count in actor_failures.most_common(8)],
        "top_plugin_errors": [{"error": err, "count": count} for err, count in plugin_errors.most_common(8)],
        "continued_after_actor_failure_before_verify": continued_after_failure[:12],
    }


def _goal_from_events(events: list[dict[str, Any]]) -> str:
    for ev in _sorted_events(events):
        data = _event_data(ev)
        goal = str(data.get("goal", "")).strip()
        if goal:
            return goal
    return ""


def _diagnose_traces(session_path: Path, goal: str) -> dict[str, Any]:
    trace_dir = session_path / "traces"
    files = sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []
    request_pattern_counts: Counter[str] = Counter()
    response_pattern_counts: Counter[str] = Counter()
    exact_goal_hits = 0
    active_task_lengths: list[int] = []
    active_task_samples: Counter[str] = Counter()
    planner_outputs: Counter[str] = Counter()
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if goal and goal in raw:
            exact_goal_hits += 1
        for name, pattern in TRACE_REQUEST_PATTERNS.items():
            if pattern in raw:
                request_pattern_counts[name] += 1
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        request = data.get("request") if isinstance(data, dict) else {}
        messages = request.get("messages") if isinstance(request, dict) else []
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                content = str(msg.get("content", ""))
                for line in content.splitlines():
                    match = ACTIVE_TASK_RE.match(line)
                    if match:
                        task = match.group(1).strip()
                        active_task_lengths.append(len(task))
                        active_task_samples[_short(task, 320)] += 1
        response = data.get("response") if isinstance(data, dict) else {}
        choices = response.get("choices") if isinstance(response, dict) else []
        if choices and isinstance(choices, list):
            message = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else {}
            content = str((message or {}).get("content", "")).strip()
            for name, pattern in TRACE_RESPONSE_PATTERNS.items():
                if pattern in content:
                    response_pattern_counts[name] += 1
            if "desktop_press" in content or "desktop_hotkey" in content or "desktop_write" in content:
                planner_outputs[_short(content, 320)] += 1
    return {
        "trace_dir": str(trace_dir) if trace_dir.exists() else "",
        "trace_files": len(files),
        "exact_goal_hits": exact_goal_hits,
        "active_task_lengths": {
            "min": min(active_task_lengths) if active_task_lengths else None,
            "max": max(active_task_lengths) if active_task_lengths else None,
            "samples": len(active_task_lengths),
        },
        "active_task_samples": [{"text": text, "count": count} for text, count in active_task_samples.most_common(3)],
        "request_pattern_counts": dict(sorted(request_pattern_counts.items())),
        "response_pattern_counts": dict(sorted(response_pattern_counts.items())),
        "gui_plan_samples": [{"text": text, "count": count} for text, count in planner_outputs.most_common(5)],
    }


def _default_lmstudio_log() -> Path | None:
    root = Path.home() / ".lmstudio" / "server-logs"
    if not root.exists():
        return None
    candidates = [p for p in root.glob("*/*.log") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _parse_lmstudio_ts(line: str) -> float | None:
    m = LMSTUDIO_TS_RE.match(line)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.timestamp()


def _diagnose_lmstudio_log(events: list[dict[str, Any]], lm_log_path: str | Path | None) -> dict[str, Any]:
    if lm_log_path is None:
        return {"enabled": False}
    path = _default_lmstudio_log() if str(lm_log_path) == "auto" else Path(lm_log_path)
    if path is None:
        return {"enabled": True, "log_path": "", "error": "LM Studio log not found"}
    times = [_event_time(ev) for ev in events if _event_time(ev)]
    if not times:
        return {"enabled": True, "log_path": str(path), "error": "session has no timestamps"}
    start = min(times) - 60.0
    end = max(times) + 60.0
    matches: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line_no, line in enumerate(fh, 1):
                ts = _parse_lmstudio_ts(line)
                if ts is None or ts < start or ts > end:
                    continue
                if LMSTUDIO_CONTROL_RE.search(line):
                    matches.append({"line": line_no, "text": line.strip()[:500]})
    except OSError as exc:
        return {"enabled": True, "log_path": str(path), "error": str(exc)}
    return {
        "enabled": True,
        "log_path": str(path),
        "window_local": {
            "start": datetime.fromtimestamp(start).isoformat(timespec="seconds"),
            "end": datetime.fromtimestamp(end).isoformat(timespec="seconds"),
        },
        "control_event_count": len(matches),
        "control_events": matches[-40:],
    }


def summarize_session(
    session_dir: str | Path,
    *,
    run_dir: str | Path | None = None,
    status: str = "running",
    lm_log_path: str | Path | None = "auto",
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

    verify_done = 0
    verify_not_done = 0
    verify_unknown = 0
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
            verdict = str(data.get("verdict", "")).upper()
            if verdict == "DONE":
                verify_done += 1
            elif verdict == "NOT_DONE":
                verify_not_done += 1
            elif verdict == "UNKNOWN":
                verify_unknown += 1
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
    verifier_total = verify_done + verify_not_done + verify_unknown
    internal_success = (verify_done / verifier_total) if verifier_total else None
    solved = max(fissions, 0)
    first_pass = None
    if solved:
        first_pass = 1.0 if verify_not_done == 0 and errors == 0 and mutations == 0 else 0.0
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
            "verify_done": verify_done,
            "verify_not_done": verify_not_done,
            "verify_unknown": verify_unknown,
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
    goal = _goal_from_events(events)
    summary["diagnostics"] = {
        "session": _diagnose_session_events(events),
        "traces": _diagnose_traces(session_path, goal),
        "lmstudio": _diagnose_lmstudio_log(events, lm_log_path),
    }
    if run_dir:
        out_dir = Path(run_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_shell(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(config.BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[:12000],
            "stderr": proc.stderr.strip()[:12000],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:1000], "stdout": "", "stderr": ""}


def _git_snapshot() -> dict[str, Any]:
    return {
        "head": _run_shell(["git", "rev-parse", "--short", "HEAD"]),
        "branch": _run_shell(["git", "branch", "--show-current"]),
        "status": _run_shell(["git", "status", "--short"]),
        "diff_stat": _run_shell(["git", "diff", "--stat"]),
        "diff_name_status": _run_shell(["git", "diff", "--name-status"]),
    }


def _taskkill_tree(pid: int, *, force: bool) -> dict[str, Any]:
    if os.name != "nt":
        return {"ok": False, "reason": "taskkill only used on Windows"}
    cmd = ["taskkill"]
    if force:
        cmd.append("/F")
    cmd += ["/T", "/PID", str(pid)]
    return _run_shell(cmd)


def _stop_process_tree(proc: subprocess.Popen[Any], grace_seconds: float) -> dict[str, Any]:
    if proc.poll() is not None:
        return {"method": "already_exited", "returncode": proc.returncode}
    first = _taskkill_tree(proc.pid, force=False)
    deadline = time.time() + max(0.0, grace_seconds)
    while time.time() < deadline:
        if proc.poll() is not None:
            return {"method": "taskkill_tree", "returncode": proc.returncode, "first": first}
        time.sleep(0.25)
    second = _taskkill_tree(proc.pid, force=True)
    try:
        proc.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        pass
    return {
        "method": "taskkill_tree_force",
        "returncode": proc.poll(),
        "first": first,
        "second": second,
    }


def _newest_dir(parent: Path, before: set[str]) -> Path | None:
    if not parent.exists():
        return None
    candidates = [p for p in parent.iterdir() if p.is_dir() and p.name not in before]
    if not candidates:
        candidates = [p for p in parent.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _copy_logs(session_dir: Path | None, raw_run_dir: Path | None, export_dir: Path) -> None:
    logs_dir = export_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if session_dir and session_dir.exists():
        session_out = logs_dir / "session"
        session_out.mkdir(parents=True, exist_ok=True)
        for path in sorted(session_dir.glob("*.jsonl")):
            shutil.copy2(path, session_out / path.name)
    if raw_run_dir and raw_run_dir.exists():
        raw_out = logs_dir / "runtime_ablation"
        raw_out.mkdir(parents=True, exist_ok=True)
        for path in sorted(raw_run_dir.glob("*.json")):
            shutil.copy2(path, raw_out / path.name)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _trim_trailing_blank_lines(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")


def _load_manifest(raw_run_dir: Path | None) -> dict[str, Any]:
    if not raw_run_dir:
        return {}
    path = raw_run_dir / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _dict_field(container: dict[str, Any], key: str) -> dict[str, Any]:
    value = container.get(key)
    return value if isinstance(value, dict) else {}


def _auto_evaluation(summary: dict[str, Any], stop_reason: str, returncode: int | None) -> dict[str, str]:
    evidence = _dict_field(summary, "evidence")
    done = int(evidence.get("verify_done", 0) or 0)
    not_done = int(evidence.get("verify_not_done", 0) or 0)
    unknown = int(evidence.get("verify_unknown", 0) or 0)
    fissions = int(evidence.get("fissions", 0) or 0)
    errors = int(evidence.get("errors", 0) or 0)
    if done or fissions:
        verdict = "success_evidence_present"
    elif not_done or unknown or errors:
        verdict = "failure_evidence_present"
    elif stop_reason == "timeout":
        verdict = "timeout_no_verified_outcome"
    elif returncode not in (0, None):
        verdict = "process_failed_no_verified_outcome"
    else:
        verdict = "no_verified_outcome"
    return {
        "evaluator": "ablation_runner",
        "verdict": verdict,
        "note": (
            f"stop_reason={stop_reason}; returncode={returncode}; "
            f"DONE={done}; NOT_DONE={not_done}; UNKNOWN={unknown}; fissions={fissions}; errors={errors}"
        ),
    }


def _run_markdown(record: dict[str, Any]) -> str:
    manifest = _dict_field(record, "manifest")
    summary = _dict_field(record, "summary")
    evidence = _dict_field(summary, "evidence")
    evaluation = _dict_field(record, "evaluation")
    cmd = " ".join(record.get("command", []))
    return "\n".join([
        f"# {record.get('run_label', 'ablation run')}",
        "",
        f"- run_id: `{record.get('run_id', '')}`",
        f"- batch_id: `{record.get('batch_id', '')}`",
        f"- sequence: `{record.get('sequence', '')}`",
        f"- mode: `{record.get('mode', '')}`",
        f"- task_id: `{record.get('task_id', '')}`",
        f"- model_profile: `{record.get('model_profile', '')}`",
        f"- timeout_seconds: `{record.get('timeout_seconds', '')}`",
        f"- stop_reason: `{record.get('stop_reason', '')}`",
        f"- returncode: `{record.get('returncode', '')}`",
        f"- evaluator: `{evaluation.get('evaluator', '')}`",
        f"- verdict: `{evaluation.get('verdict', '')}`",
        f"- note: {evaluation.get('note', '')}",
        "",
        "## Goal",
        "",
        str(manifest.get("goal") or record.get("goal", "")),
        "",
        "## Command",
        "",
        f"```powershell\n{cmd}\n```",
        "",
        "## Evidence",
        "",
        f"- events: `{summary.get('events', 0)}`",
        f"- verify_done: `{evidence.get('verify_done', 0)}`",
        f"- verify_not_done: `{evidence.get('verify_not_done', 0)}`",
        f"- verify_unknown: `{evidence.get('verify_unknown', 0)}`",
        f"- fissions: `{evidence.get('fissions', 0)}`",
        f"- errors: `{evidence.get('errors', 0)}`",
        f"- mutations: `{evidence.get('mutations', 0)}`",
        f"- respawns: `{evidence.get('respawns', 0)}`",
        "",
        "## Paths",
        "",
        f"- raw_session_dir: `{record.get('raw_session_dir', '')}`",
        f"- raw_ablation_dir: `{record.get('raw_ablation_dir', '')}`",
    ]) + "\n"


def run_once(
    *,
    mode: str,
    task_id: str = "",
    goal: str = "",
    timeout_seconds: int,
    model_profile: str = "",
    backend: str = "lmstudio",
    unicore_persona: str = config.UNICORE_DEFAULT_PERSONA,
    batch_id: str = "",
    sequence: int = 1,
    records_dir: Path = COMMITTED_RUNS_DIR,
    evaluator: str = "codex",
    evaluator_verdict: str = "unreviewed",
    evaluator_note: str = "",
    grace_seconds: float = 5.0,
) -> dict[str, Any]:
    run_mode = config.normalize_run_mode(mode)
    resolved_profile = model_profile or config.default_model_profile_for_mode(run_mode)
    resolved_goal = task_goal(task_id, goal)
    if not resolved_goal:
        raise ValueError("run requires --task-id or --goal")

    batch = batch_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_label = f"{sequence:03d}_{run_mode}_{_safe_slug(task_id or resolved_goal)}"
    export_dir = records_dir / batch / run_label
    export_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = export_dir / "stdout.txt"
    stderr_path = export_dir / "stderr.txt"
    before_sessions = {p.name for p in (config.BASE_DIR / "sessions").glob("*") if p.is_dir()}
    before_runs = {p.name for p in config.ABLATION_DIR.glob("*") if p.is_dir()} if config.ABLATION_DIR.exists() else set()
    before_git = _git_snapshot()

    log.cleanup_runtime(deep=False)
    env = os.environ.copy()
    env["ENDGAME_BOOTSTRAPPED"] = "1"
    env["ENDGAME_BACKEND"] = backend
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable,
        "reactor.py",
        "--mode",
        run_mode,
        "--model-profile",
        resolved_profile,
    ]
    if task_id:
        cmd += ["--ablation-task-id", task_id]
    if goal:
        cmd += ["--goal", goal]
    if run_mode == "unicore":
        cmd += ["--unicore-persona", unicore_persona]

    started = time.time()
    stop_reason = "completed"
    stop_detail: dict[str, Any] = {}
    with stdout_path.open("w", encoding="utf-8", newline="\n") as stdout, stderr_path.open("w", encoding="utf-8", newline="\n") as stderr:
        proc = subprocess.Popen(
            cmd,
            cwd=str(config.BASE_DIR),
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            returncode = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            stop_reason = "timeout"
            stop_detail = _stop_process_tree(proc, grace_seconds)
            returncode = proc.poll()
    _trim_trailing_blank_lines(stdout_path)
    _trim_trailing_blank_lines(stderr_path)
    finished = time.time()

    raw_session_dir = _newest_dir(config.BASE_DIR / "sessions", before_sessions)
    raw_run_dir = _newest_dir(config.ABLATION_DIR, before_runs)
    summary = summarize_session(raw_session_dir, run_dir=raw_run_dir, status=stop_reason) if raw_session_dir else {
        "v": 1,
        "status": "no_session",
        "events": 0,
        "evidence": {},
        "core_metrics": {},
    }
    manifest = _load_manifest(raw_run_dir)
    auto_eval = _auto_evaluation(summary, stop_reason, returncode)
    human_or_agent_eval = {
        "evaluator": evaluator,
        "verdict": evaluator_verdict,
        "note": evaluator_note,
    }
    after_git = _git_snapshot()
    record: dict[str, Any] = {
        "v": 1,
        "batch_id": batch,
        "run_label": run_label,
        "sequence": sequence,
        "run_id": manifest.get("run_id", ""),
        "started_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(timespec="seconds"),
        "finished_utc": datetime.fromtimestamp(finished, timezone.utc).isoformat(timespec="seconds"),
        "elapsed_seconds": round(finished - started, 3),
        "mode": run_mode,
        "task_id": task_id,
        "goal": resolved_goal,
        "model_profile": resolved_profile,
        "backend": backend,
        "unicore_persona": unicore_persona if run_mode == "unicore" else "",
        "timeout_seconds": timeout_seconds,
        "grace_seconds": grace_seconds,
        "command": cmd,
        "returncode": returncode,
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "raw_session_dir": str(raw_session_dir) if raw_session_dir else "",
        "raw_ablation_dir": str(raw_run_dir) if raw_run_dir else "",
        "manifest": manifest,
        "summary": summary,
        "evaluation": auto_eval,
        "submitted_evaluation": human_or_agent_eval,
        "git_before": before_git,
        "git_after": after_git,
    }
    _copy_logs(raw_session_dir, raw_run_dir, export_dir)
    _write_json(export_dir / "record.json", record)
    _write_json(export_dir / "summary.json", summary)
    _write_json(export_dir / "evaluation.json", {"automatic": auto_eval, "submitted": human_or_agent_eval})
    _write_text(export_dir / "RUN.md", _run_markdown(record))
    return record


def run_repeated(args: argparse.Namespace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    batch = args.batch_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    records_dir = Path(args.records_dir).resolve() if args.records_dir else COMMITTED_RUNS_DIR
    for idx in range(1, args.repeat + 1):
        record = run_once(
            mode=args.mode,
            task_id=args.task_id,
            goal=args.goal,
            timeout_seconds=args.timeout,
            model_profile=args.model_profile,
            backend=args.backend,
            unicore_persona=args.unicore_persona,
            batch_id=batch,
            sequence=idx,
            records_dir=records_dir,
            evaluator=args.evaluator,
            evaluator_verdict=args.verdict,
            evaluator_note=args.note,
            grace_seconds=args.grace_seconds,
        )
        records.append(record)
        evaluation = _dict_field(record, "evaluation")
        print(f"{idx}/{args.repeat} {record['run_label']} {record['stop_reason']} {evaluation.get('verdict', '')}")
    batch_dir = records_dir / batch
    _write_json(batch_dir / "batch.json", {"v": 1, "batch_id": batch, "runs": records})
    _write_text(batch_dir / "README.md", _batch_markdown(batch, records))
    return records


def _batch_markdown(batch_id: str, records: list[dict[str, Any]]) -> str:
    lines = [f"# Ablation Batch {batch_id}", ""]
    for record in records:
        evaluation = _dict_field(record, "evaluation")
        summary = _dict_field(record, "summary")
        evidence = _dict_field(summary, "evidence")
        lines.append(
            f"- `{record.get('run_label')}` mode=`{record.get('mode')}` task=`{record.get('task_id')}` "
            f"stop=`{record.get('stop_reason')}` verdict=`{evaluation.get('verdict')}` "
            f"DONE=`{evidence.get('verify_done', 0)}` NOT_DONE=`{evidence.get('verify_not_done', 0)}` UNKNOWN=`{evidence.get('verify_unknown', 0)}` "
            f"fissions=`{evidence.get('fissions', 0)}` errors=`{evidence.get('errors', 0)}`"
        )
    lines.append("")
    return "\n".join(lines)


def latest_session() -> Path | None:
    sessions = sorted((config.BASE_DIR / "sessions").glob("*"))
    return sessions[-1] if sessions else None


def _resolve_session_arg(value: str) -> Path | None:
    return latest_session() if value == "latest" else Path(value)


def _watch_line(summary: dict[str, Any]) -> str:
    diag = _dict_field(_dict_field(summary, "diagnostics"), "session")
    counts = _dict_field(diag, "counts")
    lmstudio = _dict_field(_dict_field(summary, "diagnostics"), "lmstudio")
    fields = [
        f"events={summary.get('events', 0)}",
        f"last={diag.get('last_phase', '')}",
        f"unknown_key={counts.get('unknown_key', 0)}",
        f"continued_after_failure={len(diag.get('continued_after_actor_failure_before_verify', []) or [])}",
        f"py_timeout={counts.get('python_timeout', 0)}",
        f"no_window={counts.get('no_window_matching', 0)}",
        f"plugin_error={counts.get('plugin_error', 0)}",
        f"lm_control={lmstudio.get('control_event_count', 0)}",
    ]
    return " | ".join(fields)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 ablation helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-tasks")
    p_run = sub.add_parser("run", help="Run a finite reactor ablation and export committed records")
    p_run.add_argument("--mode", choices=config.RUN_MODES, required=True)
    p_run.add_argument("--task-id", default="")
    p_run.add_argument("--goal", default="")
    p_run.add_argument("--timeout", type=int, required=True, help="Seconds before stopping the run; real Phase 0 tests use exactly 1200")
    p_run.add_argument("--repeat", type=int, default=1)
    p_run.add_argument("--model-profile", default="")
    p_run.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    p_run.add_argument("--unicore-persona", default=config.UNICORE_DEFAULT_PERSONA)
    p_run.add_argument("--batch-id", default="")
    p_run.add_argument("--records-dir", default=str(COMMITTED_RUNS_DIR))
    p_run.add_argument("--evaluator", default="codex")
    p_run.add_argument("--verdict", default="unreviewed")
    p_run.add_argument("--note", default="")
    p_run.add_argument("--grace-seconds", type=float, default=5.0)
    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("--session", default="latest")
    p_sum.add_argument("--run-dir", default="")
    p_sum.add_argument("--status", default="manual")
    p_sum.add_argument("--lm-log", default="auto", help="LM Studio server log path, 'auto', or 'none'")
    p_sum.add_argument("--watch", action="store_true", help="Refresh a compact diagnostic line until interrupted")
    p_sum.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    if args.cmd == "list-tasks":
        for task in PHASE0_TASKS:
            print(f"{task['id']}: {task['text']}")
        return
    if args.cmd == "summarize":
        lm_log_path = None if args.lm_log == "none" else args.lm_log
        if args.watch:
            try:
                while True:
                    session = _resolve_session_arg(args.session)
                    if session is None:
                        print("No sessions found")
                    else:
                        summary = summarize_session(session, run_dir=args.run_dir or None, status=args.status, lm_log_path=lm_log_path)
                        print(f"{datetime.now().isoformat(timespec='seconds')} | {session.name} | {_watch_line(summary)}", flush=True)
                    time.sleep(max(1.0, float(args.interval)))
            except KeyboardInterrupt:
                return
        session = _resolve_session_arg(args.session)
        if session is None:
            raise SystemExit("No sessions found")
        summary = summarize_session(session, run_dir=args.run_dir or None, status=args.status, lm_log_path=lm_log_path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.cmd == "run":
        if args.repeat < 1:
            raise SystemExit("--repeat must be >= 1")
        if not args.task_id and not args.goal:
            raise SystemExit("run requires --task-id or --goal")
        run_repeated(args)
        return


if __name__ == "__main__":
    main()
