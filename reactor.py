"""Reactor — keeps 5 slots alive. Slot 1 = comms_operator (fixed). Slots 2-5 = dynamic."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

import config
import comms
import log

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 5
slots: dict[int, dict[str, Any]] = {}
_model_profile: str = ""
_session_dir: str = ""
_last_evolve_id: int = 0
_breed_scores: dict[str, dict[str, Any]] = {}
_slot_survivors: dict[int, str] = {}
_elite_archive: dict[str, dict[str, Any]] = {}
_evicted_personas: dict[str, dict[str, Any]] = {}
_mutation_trials: dict[str, dict[str, Any]] = {}


def _clear_breed_state() -> None:
    _breed_scores.clear()
    _slot_survivors.clear()
    _elite_archive.clear()
    _evicted_personas.clear()
    _mutation_trials.clear()


def _breed_state_snapshot() -> dict[str, Any]:
    return {
        "archive_path": config.BREED_ARCHIVE_PATH,
        "bus_dir": config.BUS_DIR,
        "bus_chat_path": config.BUS_CHAT_PATH,
        "bus_events_path": config.BUS_EVENTS_PATH,
        "bus_inject_path": config.BUS_INJECT_PATH,
        "bus_control_path": config.BUS_CONTROL_PATH,
        "breed_scores": json.loads(json.dumps(_breed_scores, ensure_ascii=False)),
        "slot_survivors": json.loads(json.dumps(_slot_survivors, ensure_ascii=False)),
        "elite_archive": json.loads(json.dumps(_elite_archive, ensure_ascii=False)),
        "evicted_personas": json.loads(json.dumps(_evicted_personas, ensure_ascii=False)),
        "mutation_trials": json.loads(json.dumps(_mutation_trials, ensure_ascii=False)),
    }


def _restore_breed_state(snapshot: dict[str, Any]) -> None:
    config.BREED_ARCHIVE_PATH = snapshot["archive_path"]
    config.BUS_DIR = snapshot["bus_dir"]
    config.BUS_CHAT_PATH = snapshot["bus_chat_path"]
    config.BUS_EVENTS_PATH = snapshot["bus_events_path"]
    config.BUS_INJECT_PATH = snapshot["bus_inject_path"]
    config.BUS_CONTROL_PATH = snapshot["bus_control_path"]
    _breed_scores.clear()
    _breed_scores.update(snapshot.get("breed_scores", {}))
    _slot_survivors.clear()
    _slot_survivors.update({int(k): v for k, v in snapshot.get("slot_survivors", {}).items()})
    _elite_archive.clear()
    _elite_archive.update(snapshot.get("elite_archive", {}))
    _evicted_personas.clear()
    _evicted_personas.update(snapshot.get("evicted_personas", {}))
    _mutation_trials.clear()
    _mutation_trials.update(snapshot.get("mutation_trials", {}))


def spawn(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_MAINTENANCE) -> int:
    """Spawn a persona in a slot. Returns PID."""
    ef = os.path.join(BASE, f"events-child-s{slot_id}.jsonl")
    for path in (ef, os.path.join(_session_dir, f"events-child-s{slot_id}.jsonl") if _session_dir else ""):
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    if not goal:
        pfile = os.path.join(BASE, "prompts", "personalities", f"{persona}.txt")
        if os.path.exists(pfile):
            goal = open(pfile, encoding="utf-8").read().strip()
    env = os.environ.copy()
    env["ENDGAME_PERSONALITY"] = persona
    env["ENDGAME_SLOT"] = str(slot_id)
    env["ENDGAME_SESSION_DIR"] = _session_dir
    cmd = [sys.executable, "main.py", goal, "--backend", env.get("ENDGAME_BACKEND", "lmstudio"),
           "--event-budget", "999999", "--events-path", ef, "--priority", str(priority)]
    if _model_profile:
        cmd += ["--model-profile", _model_profile]
    proc = subprocess.Popen(cmd, cwd=BASE, env=env, creationflags=0x08000000)
    slots[slot_id] = {"pid": proc.pid, "persona": persona, "goal": goal[:80], "priority": priority}
    return proc.pid


def kill_slot(slot_id: int) -> None:
    """Kill a slot's process."""
    info = slots.pop(slot_id, None)
    if info:
        os.system(f"taskkill /F /T /PID {info['pid']} >nul 2>&1")


_STILL_ACTIVE = 259
_PROCESS_QUERY = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION


def is_alive(slot_id: int) -> bool:
    info = slots.get(slot_id)
    if not info:
        return False
    pid = info["pid"]
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == _STILL_ACTIVE
    except (OSError, AttributeError):
        return False


def reassign(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_NORMAL) -> int:
    """Kill slot and respawn with new persona/goal."""
    kill_slot(slot_id)
    time.sleep(0.5)
    return spawn(slot_id, persona, goal, priority)


def status() -> dict[int, dict[str, Any]]:
    """Current slot status."""
    return {sid: {**info, "alive": is_alive(sid)} for sid, info in slots.items()}


def _candidate_slot(entry: dict[str, Any], payload: dict[str, Any], target: str) -> int:
    try:
        sid = int(payload.get("slot", entry.get("slot", 0)) or 0)
    except (TypeError, ValueError):
        sid = 0
    if 2 <= sid <= config.SLOTS:
        return sid
    for slot_id, info in slots.items():
        if info.get("persona") == target:
            return slot_id
    return int(config.PERSONA_SLOTS.get(target, 0) or 0)


def _candidate_fitness(payload: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(payload.get("fitness", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _archive_slot(value: Any, target: str = "") -> int:
    try:
        slot_id = int(value or 0)
    except (TypeError, ValueError):
        slot_id = 0
    if 2 <= slot_id <= config.SLOTS:
        return slot_id
    return int(config.PERSONA_SLOTS.get(target, 0) or 0)


def _archive_ts(value: Any) -> float:
    try:
        return float(value or time.time())
    except (TypeError, ValueError):
        return time.time()


def _post_archive_status(event: str, detail: dict[str, Any] | None = None) -> None:
    data = {
        "action": "breed.archive",
        "event": event,
        "path": str(config.BREED_ARCHIVE_PATH.relative_to(config.BASE_DIR)),
        "elites": len(_elite_archive),
        "scores": len(_breed_scores),
        "survivors": len(_slot_survivors),
        "evicted": len(_evicted_personas),
    }
    if detail:
        data.update(detail)
    try:
        comms.post(
            "reactor",
            "reactor",
            f"breed archive {event} elites={data['elites']} survivors={data['survivors']}",
            kind=comms.KIND_STATUS,
            data=data,
        )
        log.emit("breed.archive", data)
    except Exception:
        pass


def _archive_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "saved_at": time.time(),
        "elite_archive": _elite_archive,
        "breed_scores": _breed_scores,
        "slot_survivors": {str(slot): persona for slot, persona in _slot_survivors.items()},
        "evicted_personas": _evicted_personas,
    }


def _save_breed_archive(reason: str) -> None:
    path = config.BREED_ARCHIVE_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(_archive_payload(), ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
        _post_archive_status("save", {"reason": reason})
    except Exception as exc:
        _post_archive_status("error", {"reason": reason, "error": str(exc)[:160]})


def _load_breed_archive() -> None:
    path = config.BREED_ARCHIVE_PATH
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _post_archive_status("error", {"reason": "load", "error": str(exc)[:160]})
        return
    try:
        version = int(data.get("version", 0) or 0) if isinstance(data, dict) else 0
    except (TypeError, ValueError):
        version = 0
    if version != 1:
        _post_archive_status("skip", {"reason": "unsupported_version"})
        return

    _elite_archive.clear()
    raw_elites = data.get("elite_archive") if isinstance(data.get("elite_archive"), dict) else {}
    for raw_niche, raw_elite in raw_elites.items():
        if not isinstance(raw_elite, dict):
            continue
        target = comms.canonical(str(raw_elite.get("target", "")))
        if target not in config.WORKER_PERSONAS:
            continue
        niche = str(raw_niche).strip()[:80]
        if not niche:
            continue
        _elite_archive[niche] = {
            "target": target,
            "action": str(raw_elite.get("action", ""))[:40],
            "slot": _archive_slot(raw_elite.get("slot", 0), target),
            "fitness": _candidate_fitness(raw_elite),
            "completed": str(raw_elite.get("completed", ""))[:120],
            "behavior": str(raw_elite.get("behavior", ""))[:60],
            "pressure_band": str(raw_elite.get("pressure_band", ""))[:40],
            "ts": _archive_ts(raw_elite.get("ts")),
        }
    _trim_elite_archive()

    _breed_scores.clear()
    raw_scores = data.get("breed_scores") if isinstance(data.get("breed_scores"), dict) else {}
    for raw_target, raw_score in raw_scores.items():
        if not isinstance(raw_score, dict):
            continue
        target = comms.canonical(str(raw_target))
        if target not in config.WORKER_PERSONAS:
            continue
        fitness = _candidate_fitness(raw_score)
        if fitness <= 0:
            continue
        _breed_scores[target] = {
            "fitness": fitness,
            "slot": _archive_slot(raw_score.get("slot", 0), target),
            "completed": str(raw_score.get("completed", ""))[:120],
            "fissions": int(raw_score.get("fissions", 0) or 0),
            "trial_id": str(raw_score.get("trial_id", ""))[:80],
        }

    _evicted_personas.clear()
    raw_evicted = data.get("evicted_personas") if isinstance(data.get("evicted_personas"), dict) else {}
    for raw_target, raw_record in raw_evicted.items():
        if not isinstance(raw_record, dict):
            continue
        target = comms.canonical(str(raw_target))
        if target not in config.WORKER_PERSONAS:
            continue
        _evicted_personas[target] = {
            "fitness": _candidate_fitness(raw_record),
            "slot": _archive_slot(raw_record.get("slot", 0), target),
            "reason": str(raw_record.get("reason", ""))[:120],
            "ts": _archive_ts(raw_record.get("ts")),
        }
        _evict_elites_for(target)

    _slot_survivors.clear()
    raw_survivors = data.get("slot_survivors") if isinstance(data.get("slot_survivors"), dict) else {}
    for raw_slot, raw_persona in raw_survivors.items():
        target = comms.canonical(str(raw_persona))
        if target not in config.WORKER_PERSONAS or _is_evicted(target):
            continue
        slot_id = _archive_slot(raw_slot, target)
        fitness = float(_breed_scores.get(target, {}).get("fitness", 0.0) or 0.0)
        if 2 <= slot_id <= config.SLOTS and fitness >= config.BREED_RETAIN_MIN:
            _slot_survivors[slot_id] = target

    _post_archive_status("load")


def _post_breed_status(
    action: str,
    target: str,
    slot_id: int,
    fitness: float,
    *,
    niche: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        data = {
            "action": f"breed.{action}",
            "target": target,
            "slot": slot_id,
            "fitness": round(fitness, 4),
        }
        if niche:
            data["niche"] = niche[:80]
            data["elite_count"] = len(_elite_archive)
        if detail:
            data.update(detail)
        comms.post(
            "reactor",
            "reactor",
            f"breed {action} @{target} s{slot_id} fitness={fitness:.3f}"
            + (f" niche={niche[:80]}" if niche else ""),
            kind=comms.KIND_STATUS,
            data=data,
        )
        log.emit(f"breed.{action}", data)
    except Exception:
        pass


def _candidate_niche(payload: dict[str, Any], action: str) -> str:
    niche = str(payload.get("niche", "")).strip()[:80]
    if niche:
        return niche
    behavior = str(payload.get("behavior", "")).strip()
    band = str(payload.get("pressure_band", "")).strip()
    if behavior and band:
        return f"{behavior[:40]}:{band[:30]}"
    if action == "patch_plugin":
        return "plugin_patch:unknown_pressure"
    if action == "evict":
        return "verify_denial:unknown_pressure"
    return "general_task:unknown_pressure"


def _plugin_patch_semantic_regression(payload: dict[str, Any]) -> str:
    diff = str(payload.get("diff", ""))
    if not diff:
        return ""
    removed: list[str] = []
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:].lower())
        elif line.startswith("+"):
            added.append(line[1:].lower())

    telemetry_tokens = (
        "post_telemetry", "'phase'", '"phase"', "'data'", '"data"',
        "plugin.", "kind_telemetry",
    )
    removed_telemetry = any(
        any(token in line for token in telemetry_tokens)
        for line in removed
    )
    added_telemetry = any(
        any(token in line for token in telemetry_tokens)
        for line in added
    )
    added_noop = any("return none" in line or "pass" == line.strip() for line in added)
    if removed_telemetry and (added_noop or not added_telemetry):
        return "telemetry_removed"
    return ""


def _record_semantic_regress(
    target: str,
    slot_id: int,
    fitness: float,
    niche: str,
    payload: dict[str, Any],
    reason: str,
) -> None:
    detail = {
        "source": "semantic_scoring",
        "reason": reason,
        "trial_action": str(payload.get("action", "patch_plugin")),
        "filename": str(payload.get("filename", payload.get("completed", "")))[:120],
    }
    _apply_trial_feedback("regress", target, {
        "slot": slot_id,
        "fitness": fitness,
        "trial_id": f"semantic:{target}:{reason}"[:80],
        "filename": str(payload.get("filename", payload.get("completed", "")))[:120],
    }, detail)
    _post_breed_status("regress", target, slot_id, fitness, niche=niche, detail=detail)
    _save_breed_archive(f"semantic.{reason}")


def _telemetry_for(target: str) -> dict[str, Any]:
    return comms.colony_state().get(comms.canonical(str(target)), {})


def _trim_elite_archive() -> None:
    while len(_elite_archive) > config.BREED_ELITE_MAX_NICHES:
        worst = min(
            _elite_archive,
            key=lambda n: float(_elite_archive[n].get("fitness", 0.0) or 0.0),
        )
        _elite_archive.pop(worst, None)


def _evict_elites_for(target: str) -> None:
    for niche, elite in list(_elite_archive.items()):
        if elite.get("target") == target:
            _elite_archive.pop(niche, None)


def _is_evicted(persona: str) -> bool:
    return comms.canonical(str(persona)) in _evicted_personas


def _update_elite_archive(
    target: str,
    action: str,
    slot_id: int,
    fitness: float,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    niche = _candidate_niche(payload, action)
    previous = _elite_archive.get(niche)
    prev_fit = float(previous.get("fitness", -1.0) or -1.0) if previous else -1.0
    if previous and fitness < prev_fit + config.BREED_ELITE_MIN_DELTA:
        return False, niche
    _elite_archive[niche] = {
        "target": target,
        "action": action,
        "slot": slot_id,
        "fitness": fitness,
        "completed": str(payload.get("completed", ""))[:120],
        "behavior": str(payload.get("behavior", ""))[:60],
        "pressure_band": str(payload.get("pressure_band", ""))[:40],
        "ts": time.time(),
    }
    _trim_elite_archive()
    return True, niche


def _trial_id(entry_id: int, target: str, action: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("trial_id", "")).strip()
    if explicit:
        return explicit[:80]
    seed = entry_id if entry_id else int(time.time() * 1000)
    return f"{seed}:{target}:{action}"[:80]


def _start_selection_trial(
    action: str,
    target: str,
    slot_id: int,
    fitness: float,
    niche: str,
    payload: dict[str, Any],
    *,
    entry_id: int = 0,
) -> None:
    telemetry = _telemetry_for(target)
    trial_id = _trial_id(entry_id, target, action, payload)
    base_stag = float(telemetry.get("stagnation", payload.get("stagnation", 0.0)) or 0.0)
    base_power = float(telemetry.get("power", payload.get("power", 0.0)) or 0.0)
    base_fissions = int(telemetry.get("fissions", payload.get("fissions", 0)) or 0)
    now = time.time()
    _mutation_trials[trial_id] = {
        "trial_id": trial_id,
        "action": action,
        "target": target,
        "slot": slot_id,
        "fitness": fitness,
        "niche": niche,
        "filename": str(payload.get("filename", payload.get("completed", "")))[:120],
        "baseline_stagnation": base_stag,
        "baseline_power": base_power,
        "baseline_fissions": base_fissions,
        "samples": 0,
        "last_eval": now,
        "started": now,
    }
    _post_breed_status(
        "trial",
        target,
        slot_id,
        fitness,
        niche=niche,
        detail={
            "source": "selection_trial",
            "trial_id": trial_id,
            "trial_action": action,
            "filename": str(payload.get("filename", payload.get("completed", "")))[:120],
            "baseline_stagnation": round(base_stag, 4),
            "baseline_power": round(base_power, 4),
            "baseline_fissions": base_fissions,
            "max_samples": int(config.BREED_TRIAL_SAMPLES),
        },
    )


def _apply_trial_feedback(outcome: str, target: str, trial: dict[str, Any], detail: dict[str, Any]) -> None:
    target = comms.canonical(target)
    slot_id = int(trial.get("slot", 0) or 0)
    fitness = float(trial.get("fitness", 0.0) or 0.0)
    previous = _breed_scores.get(target, {})
    prev_fit = float(previous.get("fitness", 0.0) or 0.0)
    changed = False
    if outcome == "improve":
        gain = max(0.0, float(detail.get("power_delta", 0.0) or 0.0))
        gain += max(0.0, float(detail.get("stagnation_delta", 0.0) or 0.0))
        gain += max(0, int(detail.get("fission_delta", 0) or 0)) * 0.05
        next_fit = round(min(1.0, max(prev_fit, fitness) + min(0.08, gain)), 4)
        _breed_scores[target] = {
            "fitness": next_fit,
            "slot": slot_id,
            "completed": str(trial.get("filename") or trial.get("action", ""))[:120],
            "fissions": int(detail.get("current_fissions", 0) or 0),
            "trial_id": str(trial.get("trial_id", "")),
        }
        changed = True
        if 2 <= slot_id <= config.SLOTS and next_fit >= config.BREED_RETAIN_MIN:
            _evicted_personas.pop(target, None)
            _slot_survivors[slot_id] = target
    elif outcome == "regress" and previous:
        next_fit = round(max(0.0, prev_fit - config.BREED_IMPROVE_MIN_DELTA), 4)
        if next_fit > 0:
            previous["fitness"] = next_fit
            _breed_scores[target] = previous
        else:
            _breed_scores.pop(target, None)
        for sid, persona in list(_slot_survivors.items()):
            if persona == target and next_fit < config.BREED_RETAIN_MIN:
                _slot_survivors.pop(sid, None)
        changed = True
    if changed:
        _save_breed_archive(f"trial.{outcome}")


def evaluate_mutation_trials() -> None:
    """Publish repeated selection outcome evidence once telemetry has reacted."""
    now = time.time()
    colony = comms.colony_state()
    for trial_id, trial in list(_mutation_trials.items()):
        if now - float(trial.get("last_eval", trial.get("started", 0.0)) or 0.0) < config.BREED_TRIAL_EVAL_SECONDS:
            continue
        target = comms.canonical(str(trial.get("target", "")))
        current = colony.get(target, {})
        base_stag = float(trial.get("baseline_stagnation", 0.0) or 0.0)
        base_power = float(trial.get("baseline_power", 0.0) or 0.0)
        base_fissions = int(trial.get("baseline_fissions", 0) or 0)
        samples = int(trial.get("samples", 0) or 0) + 1
        if not current:
            _post_breed_status(
                "regress",
                target,
                int(trial.get("slot", 0) or 0),
                float(trial.get("fitness", 0.0) or 0.0),
                niche=str(trial.get("niche", "")),
                detail={
                    "source": "selection_trial",
                    "trial_id": trial_id,
                    "trial_action": str(trial.get("action", "")),
                    "sample": samples,
                    "reason": "telemetry_missing",
                    "filename": str(trial.get("filename", ""))[:120],
                    "baseline_stagnation": round(base_stag, 4),
                    "baseline_power": round(base_power, 4),
                    "baseline_fissions": base_fissions,
                },
            )
            _mutation_trials.pop(trial_id, None)
            continue
        cur_stag = float(current.get("stagnation", 0.0) or 0.0)
        cur_power = float(current.get("power", 0.0) or 0.0)
        cur_fissions = int(current.get("fissions", 0) or 0)
        stag_drop = round(base_stag - cur_stag, 4)
        power_gain = round(cur_power - base_power, 4)
        fission_gain = cur_fissions - base_fissions
        improved = (
            fission_gain > 0
            or stag_drop >= config.BREED_IMPROVE_MIN_DELTA
            or power_gain >= config.BREED_IMPROVE_MIN_DELTA
        )
        regressed = (
            stag_drop <= -config.BREED_IMPROVE_MIN_DELTA
            or power_gain <= -config.BREED_IMPROVE_MIN_DELTA
        )
        outcome = "improve" if improved else "regress" if regressed else "neutral"
        detail = {
            "source": "selection_trial",
            "trial_id": trial_id,
            "trial_action": str(trial.get("action", "")),
            "sample": samples,
            "max_samples": int(config.BREED_TRIAL_SAMPLES),
            "age_seconds": round(now - float(trial.get("started", now) or now), 2),
            "filename": str(trial.get("filename", ""))[:120],
            "baseline_stagnation": round(base_stag, 4),
            "current_stagnation": round(cur_stag, 4),
            "stagnation_delta": stag_drop,
            "baseline_power": round(base_power, 4),
            "current_power": round(cur_power, 4),
            "power_delta": power_gain,
            "baseline_fissions": base_fissions,
            "current_fissions": cur_fissions,
            "fission_delta": fission_gain,
        }
        _apply_trial_feedback(outcome, target, trial, detail)
        _post_breed_status(
            outcome,
            target,
            int(trial.get("slot", current.get("slot", 0)) or 0),
            float(trial.get("fitness", 0.0) or 0.0),
            niche=str(trial.get("niche", "")),
            detail=detail,
        )
        if outcome == "regress" or samples >= int(config.BREED_TRIAL_SAMPLES):
            _mutation_trials.pop(trial_id, None)
        else:
            trial["samples"] = samples
            trial["last_eval"] = now


def _best_elite_persona(slot_id: int) -> tuple[str, float, str]:
    eligible: list[tuple[int, float, str, str]] = []
    for niche, elite in _elite_archive.items():
        target = comms.canonical(str(elite.get("target", "")))
        if target not in config.WORKER_PERSONAS or _is_evicted(target):
            continue
        fitness = _candidate_fitness(elite)
        if fitness < config.BREED_ELITE_RESPAWN_MIN:
            continue
        same_slot = 1 if int(elite.get("slot", 0) or 0) == slot_id else 0
        eligible.append((same_slot, fitness, target, niche))
    if not eligible:
        return "", 0.0, ""
    same_slot, fitness, target, niche = max(eligible, key=lambda item: (item[0], item[1]))
    return target, fitness, niche


def _first_viable_worker(*preferred: str) -> str:
    for persona in preferred:
        target = comms.canonical(str(persona))
        if target in config.WORKER_PERSONAS and not _is_evicted(target):
            return target
    for persona in config.WORKER_PERSONAS:
        if not _is_evicted(persona):
            return persona
    return config.WORKER_PERSONAS[0]


def process_evolve_candidates() -> None:
    """Select retained personas from fission-backed AgentBreeder candidates."""
    global _last_evolve_id
    for entry in comms.evolve_candidates(after_id=_last_evolve_id, limit=50):
        eid = int(entry.get("id", 0) or 0)
        _last_evolve_id = max(_last_evolve_id, eid)
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        target = comms.canonical(str(payload.get("target") or entry.get("to") or entry.get("from", "")))
        if target not in config.WORKER_PERSONAS:
            continue
        action = str(payload.get("action", "")).lower()
        slot_id = _candidate_slot(entry, payload, target)
        fitness = _candidate_fitness(payload)

        if action == "evict":
            _breed_scores.pop(target, None)
            _evicted_personas[target] = {
                "fitness": fitness,
                "slot": slot_id,
                "reason": str(payload.get("reason", ""))[:120],
                "ts": time.time(),
            }
            _evict_elites_for(target)
            for sid, persona in list(_slot_survivors.items()):
                if persona == target:
                    _slot_survivors.pop(sid, None)
            _post_breed_status("evict", target, slot_id, fitness,
                               niche=_candidate_niche(payload, action))
            _save_breed_archive("evict")
            continue
        if action == "patch_plugin":
            semantic_reason = _plugin_patch_semantic_regression(payload)
            if semantic_reason:
                _record_semantic_regress(
                    target,
                    slot_id,
                    fitness,
                    _candidate_niche(payload, action),
                    payload,
                    semantic_reason,
                )
                continue
            is_elite, niche = _update_elite_archive(target, action, slot_id, fitness, payload)
            if is_elite:
                _post_breed_status("elite", target, slot_id, fitness, niche=niche,
                                   detail={"elite_action": action})
                _save_breed_archive("patch_plugin.elite")
            _start_selection_trial(action, target, slot_id, fitness, niche, payload, entry_id=eid)
            continue
        if action != "retain":
            continue

        is_elite, niche = _update_elite_archive(target, action, slot_id, fitness, payload)
        if is_elite:
            _post_breed_status("elite", target, slot_id, fitness, niche=niche,
                               detail={"elite_action": action})
            _save_breed_archive("retain.elite")
        previous = _breed_scores.get(target, {})
        if previous and fitness < float(previous.get("fitness", 0.0) or 0.0):
            continue
        if fitness >= config.BREED_RETAIN_MIN:
            _evicted_personas.pop(target, None)
        _breed_scores[target] = {
            "fitness": fitness,
            "slot": slot_id,
            "completed": str(payload.get("completed", ""))[:120],
            "fissions": int(payload.get("fissions", 0) or 0),
        }
        saved_score = False
        if 2 <= slot_id <= config.SLOTS and fitness >= config.BREED_RETAIN_MIN:
            incumbent = _slot_survivors.get(slot_id, "")
            incumbent_fit = float(_breed_scores.get(incumbent, {}).get("fitness", -1.0) or -1.0)
            if fitness >= incumbent_fit:
                _slot_survivors[slot_id] = target
                print(f"  BREED RETAIN s{slot_id} -> {target} fitness={fitness:.3f}")
                _post_breed_status("retain", target, slot_id, fitness, niche=niche)
                _start_selection_trial(action, target, slot_id, fitness, niche, payload, entry_id=eid)
                _save_breed_archive("retain")
                saved_score = True
        if not saved_score:
            _save_breed_archive("retain.score")


def select_respawn_persona(slot_id: int, fallback: str) -> str:
    """Choose the persona that survives into a worker respawn."""
    if slot_id < 2:
        return fallback
    retained = _slot_survivors.get(slot_id, "")
    if retained in config.WORKER_PERSONAS and not _is_evicted(retained):
        fitness = float(_breed_scores.get(retained, {}).get("fitness", 0.0) or 0.0)
        if fitness >= config.BREED_RETAIN_MIN:
            return retained
    elite, elite_fitness, niche = _best_elite_persona(slot_id)
    if elite:
        previous = _breed_scores.get(elite, {})
        prev_fit = float(previous.get("fitness", 0.0) or 0.0)
        if elite_fitness >= prev_fit:
            _breed_scores[elite] = {
                "fitness": elite_fitness,
                "slot": slot_id,
                "completed": f"elite:{niche}"[:120],
                "fissions": int(previous.get("fissions", 0) or 0),
            }
        _slot_survivors[slot_id] = elite
        _post_breed_status("respawn", elite, slot_id, elite_fitness, niche=niche,
                           detail={"source": "elite_archive", "fallback": fallback})
        _save_breed_archive("elite_respawn")
        return elite
    fallback_persona = comms.canonical(str(fallback))
    default_persona = config.SLOT_DEFAULTS.get(slot_id, fallback_persona)
    selected = _first_viable_worker(fallback_persona, default_persona)
    if fallback_persona != selected:
        _post_breed_status("respawn", selected, slot_id, 0.0,
                           detail={"source": "evict_avoidance", "fallback": fallback_persona})
    return selected


def archive_restart_smoke() -> dict[str, Any]:
    """Deterministically prove archive save/load can drive restart respawn choice."""
    snapshot = _breed_state_snapshot()
    runtime_dir = config.BASE_DIR / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="breed-archive-smoke-", dir=str(runtime_dir)) as tmp:
            smoke_dir = Path(tmp)
            config.BREED_ARCHIVE_PATH = smoke_dir / "breed_archive.json"
            config.BUS_DIR = smoke_dir / "comms"
            config.BUS_CHAT_PATH = config.BUS_DIR / "messages.json"
            config.BUS_EVENTS_PATH = config.BUS_DIR / "events_bus.jsonl"
            config.BUS_INJECT_PATH = config.BUS_DIR / "inject.jsonl"
            config.BUS_CONTROL_PATH = config.BUS_DIR / "control.jsonl"
            _clear_breed_state()

            target = "reviewer"
            fallback = "devops"
            niche = "archive_smoke:low_pressure"
            _elite_archive[niche] = {
                "target": target,
                "action": "retain",
                "slot": 4,
                "fitness": 0.82,
                "completed": "archive smoke retained reviewer",
                "behavior": "archive_smoke",
                "pressure_band": "low_pressure",
                "ts": time.time(),
            }
            _breed_scores[target] = {
                "fitness": 0.82,
                "slot": 4,
                "completed": "archive smoke retained reviewer",
                "fissions": 2,
                "trial_id": "archive-smoke",
            }
            _slot_survivors[4] = target
            _evicted_personas[fallback] = {
                "fitness": 0.1,
                "slot": 5,
                "reason": "archive smoke fallback evicted",
                "ts": time.time(),
            }

            _save_breed_archive("archive_smoke.write")
            archive_exists = config.BREED_ARCHIVE_PATH.is_file()
            saved = json.loads(config.BREED_ARCHIVE_PATH.read_text(encoding="utf-8"))

            _clear_breed_state()
            _load_breed_archive()
            selected = select_respawn_persona(4, fallback)

            ok = (
                archive_exists
                and selected == target
                and _slot_survivors.get(4) == target
                and target in _breed_scores
                and niche in _elite_archive
                and fallback in _evicted_personas
            )
            return {
                "ok": ok,
                "archive_version": saved.get("version"),
                "selected": selected,
                "expected": target,
                "slot_survivor": _slot_survivors.get(4, ""),
                "elite_niches": sorted(_elite_archive.keys()),
                "breed_scores": sorted(_breed_scores.keys()),
                "evicted": sorted(_evicted_personas.keys()),
            }
    finally:
        _restore_breed_state(snapshot)


def breed_improve_smoke() -> dict[str, Any]:
    """Deterministically prove trial telemetry can emit breed.improve and update archive state."""
    snapshot = _breed_state_snapshot()
    old_eval_seconds = config.BREED_TRIAL_EVAL_SECONDS
    runtime_dir = config.BASE_DIR / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="breed-improve-smoke-", dir=str(runtime_dir)) as tmp:
            smoke_dir = Path(tmp)
            config.BREED_ARCHIVE_PATH = smoke_dir / "breed_archive.json"
            config.BUS_DIR = smoke_dir / "comms"
            config.BUS_CHAT_PATH = config.BUS_DIR / "messages.json"
            config.BUS_EVENTS_PATH = config.BUS_DIR / "events_bus.jsonl"
            config.BUS_INJECT_PATH = config.BUS_DIR / "inject.jsonl"
            config.BUS_CONTROL_PATH = config.BUS_DIR / "control.jsonl"
            config.BREED_TRIAL_EVAL_SECONDS = 0.0
            _clear_breed_state()

            target = "reviewer"
            niche = "breed_improve_smoke:low_pressure"
            trial_id = "breed-improve-smoke"
            payload = {
                "trial_id": trial_id,
                "completed": "breed improve smoke retained reviewer",
                "behavior": "breed_improve_smoke",
                "pressure_band": "low_pressure",
                "stagnation": 0.7,
                "power": 0.3,
                "fissions": 0,
            }
            comms.post_telemetry(
                target,
                stagnation=0.7,
                power=0.3,
                velocity=0.0,
                fissions=0,
                phase="baseline",
                cycles=1,
            )
            _start_selection_trial("retain", target, 4, 0.72, niche, payload, entry_id=0)
            comms.post_telemetry(
                target,
                stagnation=0.58,
                power=0.42,
                velocity=0.12,
                fissions=1,
                phase="improved",
                cycles=2,
            )
            evaluate_mutation_trials()

            events = [
                e for e in comms.read_events(config.BUS_EVENTS_MAX)
                if (e.get("payload") or {}).get("action") == "breed.improve"
            ]
            score = _breed_scores.get(target, {})
            archive_exists = config.BREED_ARCHIVE_PATH.is_file()
            ok = (
                bool(events)
                and archive_exists
                and float(score.get("fitness", 0.0) or 0.0) > 0.72
                and _slot_survivors.get(4) == target
            )
            latest = events[-1].get("payload", {}) if events else {}
            return {
                "ok": ok,
                "outcome": latest.get("action", ""),
                "target": target,
                "fitness": score.get("fitness", 0.0),
                "slot_survivor": _slot_survivors.get(4, ""),
                "stagnation_delta": latest.get("stagnation_delta"),
                "power_delta": latest.get("power_delta"),
                "fission_delta": latest.get("fission_delta"),
                "archive_written": archive_exists,
            }
    finally:
        config.BREED_TRIAL_EVAL_SECONDS = old_eval_seconds
        _restore_breed_state(snapshot)


def _enable_unconstrained() -> None:
    config.UNCONSTRAINED_MODE_PATH.write_text("1", encoding="utf-8")
    config.GUI_MODE_PATH.write_text("1", encoding="utf-8")
    os.environ["ENDGAME_UNCONSTRAINED"] = "1"


if __name__ == "__main__":
    # Parse CLI
    run_archive_smoke = False
    run_breed_improve_smoke = False
    _colony_goal = os.environ.get("ENDGAME_COLONY_GOAL", "").strip()
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--model-profile" and i + 1 < len(argv):
            _model_profile = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--model-profile="):
            _model_profile = arg.split("=", 1)[1]
        elif arg == "--archive-smoke":
            run_archive_smoke = True
        elif arg == "--breed-improve-smoke":
            run_breed_improve_smoke = True
        elif arg == "--unconstrained":
            _enable_unconstrained()
        elif arg == "--goal" and i + 1 < len(argv):
            _colony_goal = argv[i + 1].strip()
            i += 2
            continue
        elif arg.startswith("--goal="):
            _colony_goal = arg.split("=", 1)[1].strip()
        i += 1
    if _model_profile:
        config.apply_model_profile(_model_profile)
    if run_archive_smoke:
        result = archive_restart_smoke()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        sys.exit(0 if result.get("ok") else 1)
    if run_breed_improve_smoke:
        result = breed_improve_smoke()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        sys.exit(0 if result.get("ok") else 1)

    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()

    # Create session directory for this run
    _session_dir = str(log.session_dir())
    log.init("events-reactor.jsonl", config.EVENT_BUDGET)
    if _colony_goal:
        comms.set_colony_goal(_colony_goal, source="reactor")
    log.emit("reactor.start", {
        "slots": config.SLOTS,
        "profile": _model_profile or "auto",
        "colony_goal": _colony_goal[:120] if _colony_goal else "",
    })
    _load_breed_archive()
    print(f"REACTOR | {config.SLOTS} slots | profile={_model_profile or 'auto'}")
    if _colony_goal:
        print(f"  goal: {_colony_goal[:100]}")
    print(f"  session: {_session_dir}")

    # Slot 1: comms_operator (always)
    pid = spawn(1, "comms_operator", priority=config.PRI_NORMAL)
    print(f"  s1: comms_operator PID={pid}")

    # Slots 2-5: start with default personas doing maintenance
    defaults = ["architect", "implementor", "reviewer", "devops"]
    for i, persona in enumerate(defaults, 2):
        pid = spawn(i, persona, priority=config.PRI_MAINTENANCE)
        print(f"  s{i}: {persona} PID={pid}")
        time.sleep(1.0)  # stagger — avoid 4 parallel LLM cold-starts

    print(f"\nREACTOR ONLINE. {len(slots)} slots loaded.\n")

    # Control loop: MoE reassign + respawn dead slots
    while True:
        time.sleep(CONTROL_INTERVAL)
        process_evolve_candidates()
        evaluate_mutation_trials()
        for cmd in comms.drain_control():
            action = str(cmd.get("action", ""))
            if action == "reassign":
                sid = int(cmd.get("slot", 0) or 0)
                persona = str(cmd.get("persona", ""))
                if sid < 2 and persona:
                    for s, info in slots.items():
                        if info.get("persona") == str(cmd.get("from_persona", "")):
                            sid = s
                            break
                if sid >= 2 and sid <= config.SLOTS and persona in config.WORKER_PERSONAS:
                    pri = int(cmd.get("priority", config.PRI_NORMAL))
                    print(f"  MOE REASSIGN s{sid} -> {persona} ({cmd.get('reason', '')[:60]})")
                    reassign(sid, persona, priority=pri)
        for sid in list(slots):
            if not is_alive(sid):
                info = slots.pop(sid)
                persona = select_respawn_persona(sid, str(info.get("persona", "")))
                print(f"  RESPAWN s{sid} ({persona})")
                spawn(sid, persona, info.get("goal", ""), info.get("priority", 0))
