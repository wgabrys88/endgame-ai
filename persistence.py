from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT
import json
import msvcrt
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, cast

from config import BASE_DIR, BLACKBOARD_EVENTS_PATH, PERSISTENCE_REPLACE_ATTEMPTS, PERSISTENCE_REPLACE_RETRY_DELAY, MAX_BLACKBOARD_EVENT_RECORDS

BB_PATH = BASE_DIR / "blackboard_state.json"
BB_LOCK_PATH = BASE_DIR / "blackboard_state.lock"
EVOLUTION_LEDGER_PATH = BASE_DIR / "evolution_ledger.json"


def _default_bb() -> dict[str, Any]:
    return {
        "states": {},
        "events": [],
        "agents": {},
        "meta": {"created": datetime.now(timezone.utc).isoformat(), "last_updated": None},
    }


def _parse_bb_text(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        repaired = raw.replace('}interrupted"', "}")
        if repaired != raw:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        if err.pos and err.pos > ZERO_INT:
            try:
                return json.loads(raw[: err.pos])
            except json.JSONDecodeError:
                pass
        try:
            obj, _end = json.JSONDecoder().raw_decode(raw)
            return obj
        except json.JSONDecodeError:
            pass
        raise


def _backup_corrupt(raw: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = BB_PATH.with_name(f"blackboard_state.corrupt_{stamp}.json")
    backup.write_text(raw, encoding="utf-8")


@contextmanager
def _bb_file_lock():
    BB_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(BB_LOCK_PATH), os.O_CREAT | os.O_RDWR)
    try:
        msvcrt.locking(fd, msvcrt.LK_LOCK, ONE_INT)
        yield
    finally:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, ONE_INT)
        os.close(fd)


def _atomic_write_bb(data: dict[str, Any]) -> None:
    tmp = BB_PATH.with_name(f"{BB_PATH.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, indent=TWO_INT, ensure_ascii=False), encoding="utf-8")
    try:
        for attempt in range(PERSISTENCE_REPLACE_ATTEMPTS):
            try:
                os.replace(str(tmp), str(BB_PATH))
                return
            except PermissionError:
                if attempt == PERSISTENCE_REPLACE_ATTEMPTS - ONE_INT:
                    raise
                time.sleep(PERSISTENCE_REPLACE_RETRY_DELAY)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _read_bb_locked() -> dict[str, Any]:
    if not BB_PATH.exists():
        return _default_bb()
    raw = BB_PATH.read_text(encoding="utf-8")
    try:
        return _parse_bb_text(raw)
    except json.JSONDecodeError:
        _backup_corrupt(raw)
        data = _default_bb()
        _atomic_write_bb(data)
        return data


def _mutate_bb(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    with _bb_file_lock():
        bb = _read_bb_locked()
        mutator(bb)
        bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_bb(bb)
        return bb


def _ensure_bb() -> None:
    BB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BB_PATH.exists():
        _atomic_write_bb(_default_bb())


def save_snapshot(board_data: dict[str, Any]) -> None:
    _ensure_bb()

    def _apply(bb: dict[str, Any]) -> None:
        agent_id = str(board_data.get("agent_id", "main"))
        states = bb.setdefault("states", {})
        if isinstance(states, dict):
            states[agent_id] = board_data
        bb.pop("state", None)

    _mutate_bb(_apply)


def load_snapshot(agent_id: str = "main") -> dict[str, Any] | None:
    _ensure_bb()
    with _bb_file_lock():
        bb = _read_bb_locked()
    states_raw = bb.get("states", {})
    if not isinstance(states_raw, dict):
        return None
    states = cast(dict[str, Any], states_raw)
    state_raw = states.get(agent_id)
    if not isinstance(state_raw, dict):
        return None
    state = cast(dict[str, Any], state_raw)
    if not state or not state.get("goal"):
        return None
    return state


def post_event(verb: str, source: str, target: str, payload: Any = None) -> None:
    from event_schema import create_event

    _ensure_bb()

    def _apply(bb: dict[str, Any]) -> None:
        evt: dict[str, Any] = create_event(verb, source, target, payload)
        bb["events"].append(evt)

    _mutate_bb(_apply)


def poll_events(target: str, verbs: set[str] | None = None) -> list[dict[str, Any]]:
    _ensure_bb()
    collected: list[dict[str, Any]] = []

    def _apply(bb: dict[str, Any]) -> None:
        pending: list[dict[str, Any]] = [
            e for e in bb["events"] if e.get("target") == target and e.get("status") == "pending" and (verbs is None or str(e.get("verb", "")) in verbs)
        ]
        if pending:
            for e in pending:
                e["status"] = "done"
            collected.extend(pending)

    _mutate_bb(_apply)
    return collected


def register_agent(agent_id: str, pid: int) -> None:
    _ensure_bb()

    def _apply(bb: dict[str, Any]) -> None:
        bb["agents"][agent_id] = {"pid": pid, "started": datetime.now(timezone.utc).isoformat()}

    _mutate_bb(_apply)


def append_to_evolution_ledger(entry: str, source_run: str = "") -> None:
    data: dict[str, Any] = {"entries": []}
    if EVOLUTION_LEDGER_PATH.exists():
        try:
            data = json.loads(EVOLUTION_LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    data.setdefault("entries", []).append({"ts": datetime.now().isoformat(), "source_run": source_run, "entry": entry})
    from config import MAX_LEDGER_ENTRIES
    if len(data["entries"]) > MAX_LEDGER_ENTRIES:
        data["entries"] = data["entries"][-MAX_LEDGER_ENTRIES:]
    tmp = EVOLUTION_LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=TWO_INT, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(EVOLUTION_LEDGER_PATH))


def append_runtime_event(record: dict[str, Any]) -> None:
    BLACKBOARD_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with _bb_file_lock():
        with BLACKBOARD_EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        _trim_runtime_events()


def _trim_runtime_events() -> None:
    if not BLACKBOARD_EVENTS_PATH.exists():
        return
    raw = BLACKBOARD_EVENTS_PATH.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) <= MAX_BLACKBOARD_EVENT_RECORDS:
        return
    kept = lines[-MAX_BLACKBOARD_EVENT_RECORDS:]
    BLACKBOARD_EVENTS_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")


def get_evolution_ledger_context() -> str:
    if not EVOLUTION_LEDGER_PATH.exists():
        return ""
    try:
        data: dict[str, Any] = json.loads(EVOLUTION_LEDGER_PATH.read_text(encoding="utf-8"))
        entries: list[dict[str, Any]] = data.get("entries", [])
        if not entries:
            return ""
        lines = ["LONG-TERM EVOLUTIONARY LEDGER (distilled by the organism itself):"]
        for e in entries:
            lines.append(f"- [{e.get('ts','')}] {e.get('entry','')}")
        return "\n".join(lines)
    except Exception:
        return ""
