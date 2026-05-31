from __future__ import annotations
import json
import msvcrt
import os
from datetime import datetime, timezone
from pathlib import Path

from config import BASE_DIR

BB_PATH = BASE_DIR / "blackboard" / "blackboard_state.json"
EVOLUTION_LEDGER_PATH = BASE_DIR / "evolution_ledger.json"


def _locked_read() -> dict:
    with open(BB_PATH, "r", encoding="utf-8") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        data = json.load(f)
    return data


def _locked_write(data: dict) -> None:
    with open(BB_PATH, "w", encoding="utf-8") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        json.dump(data, f, indent=2, ensure_ascii=False)


def _ensure_bb() -> None:
    BB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BB_PATH.exists():
        BB_PATH.write_text(json.dumps({
            "state": {},
            "events": [],
            "agents": {},
            "meta": {"created": datetime.now(timezone.utc).isoformat(), "last_updated": None}
        }, indent=2), encoding="utf-8")


def save_snapshot(board_data: dict) -> None:
    _ensure_bb()
    bb = _locked_read()
    bb["state"] = board_data
    bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _locked_write(bb)


def load_snapshot() -> dict | None:
    _ensure_bb()
    bb = _locked_read()
    state = bb.get("state")
    if not state or not state.get("goal"):
        return None
    return state


def post_event(verb: str, source: str, target: str, payload=None) -> None:
    from blackboard.event_schema import create_event
    _ensure_bb()
    bb = _locked_read()
    evt = create_event(verb, source, target, payload)
    bb["events"].append(evt)
    bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _locked_write(bb)


def poll_events(target: str) -> list[dict]:
    _ensure_bb()
    bb = _locked_read()
    pending = [e for e in bb["events"] if e.get("target") == target and e.get("status") == "pending"]
    if pending:
        for e in pending:
            e["status"] = "done"
        bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        _locked_write(bb)
    return pending


def register_agent(agent_id: str, pid: int) -> None:
    _ensure_bb()
    bb = _locked_read()
    bb["agents"][agent_id] = {"pid": pid, "started": datetime.now(timezone.utc).isoformat()}
    bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _locked_write(bb)


def unregister_agent(agent_id: str) -> None:
    _ensure_bb()
    bb = _locked_read()
    bb["agents"].pop(agent_id, None)
    bb["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _locked_write(bb)


def get_registered_agents() -> dict:
    _ensure_bb()
    bb = _locked_read()
    return bb.get("agents", {})


def append_to_evolution_ledger(entry: str, source_run: str = "") -> None:
    data = {"entries": []}
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
        data = json.loads(EVOLUTION_LEDGER_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        if not entries:
            return ""
        lines = ["LONG-TERM EVOLUTIONARY LEDGER (distilled by the organism itself):"]
        for e in entries:
            lines.append(f"- [{e.get('ts','')}] {e.get('entry','')}")
        return "\n".join(lines)
    except Exception:
        return ""
