from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import uuid

VERBS = (
    "post_event",
    "read_events",
    "cleanup",
    "spawn_child",
    "stop_child",
    "goal_rewrite",
    "hint",
    "kill",
    "child_done",
    "child_failed",
    "inject_lesson",
    "set_chaos",
)


@dataclass(slots=True)
class Event:
    id: str
    verb: str
    source: str
    target: str
    payload: Any
    timestamp: str
    status: str = "pending"


def create_event(verb: str, source: str, target: str, payload: Any = None, status: str = "pending") -> dict:
    if verb not in VERBS:
        raise ValueError(f"Invalid verb '{verb}'. Must be one of {VERBS}")
    e = Event(
        id=str(uuid.uuid4()),
        verb=verb,
        source=source,
        target=target,
        payload=payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=status,
    )
    return asdict(e)


def validate_event(evt: dict) -> bool:
    required = {"id", "verb", "source", "target", "payload", "timestamp", "status"}
    if not required.issubset(evt.keys()):
        return False
    return evt.get("verb") in VERBS
