from __future__ import annotations
import json
import msvcrt
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from config import BASE_DIR

BB_PATH = BASE_DIR / "blackboard_state.json"
BB_LOCK_PATH = BASE_DIR / "blackboard_state.lock"
EVOLUTION_LEDGER_PATH = BASE_DIR / "evolution_ledger.json"


def _default_bb() -> dict[str, Any]:
    return {
        "state": {},
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
        if err.pos and err.pos > 0:
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
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        yield
    finally:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)


def _atomic_write_bb(data: dict[str, Any]) -> None:
    tmp = BB_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(BB_PATH))


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
        bb["state"] = board_data

    _mutate_bb(_apply)


def load_snapshot() -> dict[str, Any] | None:
    _ensure_bb()
    with _bb_file_lock():
        bb = _read_bb_locked()
    state: dict[str, Any] | None = bb.get("state")
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


def poll_events(target: str) -> list[dict[str, Any]]:
    _ensure_bb()
    collected: list[dict[str, Any]] = []

    def _apply(bb: dict[str, Any]) -> None:
        pending: list[dict[str, Any]] = [
            e for e in bb["events"] if e.get("target") == target and e.get("status") == "pending"
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
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(EVOLUTION_LEDGER_PATH))


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