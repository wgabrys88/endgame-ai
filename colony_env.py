"""Runtime environment injected into every agent Python script."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE_DIR: Path = Path(__file__).parent.resolve()
COMMS_DIR: Path = BASE_DIR / "runtime" / "comms"
PLUGINS_DIR: Path = BASE_DIR / "plugins"
COMMS_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)

from comms import (  # noqa: E402
    post as _post,
    agent_id as _agent_id,
    request as _request,
    route as _route,
)


def _merge_data(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    data = kwargs.pop("data", None)
    if not isinstance(data, dict):
        data = {}
    for key in ("evidence", "deadline", "target", "ok", "goal"):
        if key in kwargs:
            data[key] = kwargs.pop(key)
    return data or None


def _normalize_priority(kwargs: dict[str, Any]) -> int | None:
    for alias in ("priorit", "prio", "pri"):
        if alias in kwargs:
            kwargs["priority"] = kwargs.pop(alias)
            break
    pri = kwargs.pop("priority", None)
    return int(pri) if pri is not None else None


def bus_id(*_args: Any, **_kwargs: Any) -> str:
    """Persona id for bus from_id — ignores mistaken LLM args like bus_id('colony')."""
    return _agent_id()


def bus_post(from_id: Any = None, role: str = "colony", text: str = "",
             *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Forgiving wrapper around comms.post for generated actor code."""
    if isinstance(from_id, str) and from_id.startswith("@") and not text:
        text, from_id = from_id, _agent_id()
    elif from_id is None:
        from_id = _agent_id()
    if isinstance(role, str) and role.startswith("@"):
        if not text:
            text = role
        role = "colony"
    if args and not text:
        text = str(args[0])
    target = kwargs.pop("target", None)
    if target and not text:
        text = f"@{target}"
    priority = _normalize_priority(kwargs)
    data = _merge_data(kwargs)
    return _post(str(from_id), str(role), str(text), priority=priority, data=data)


def bus_request(from_id: Any = None, to: str = "", text: str = "",
                *args: Any, **kwargs: Any) -> dict[str, Any]:
    if from_id is None:
        from_id = _agent_id()
    if args:
        if not to:
            to = str(args[0])
        elif not text:
            text = str(args[0])
    target = kwargs.pop("target", None)
    if target:
        to = str(target)
    priority = _normalize_priority(kwargs) or 1
    goal = str(kwargs.pop("goal", "") or "")
    return _request(str(from_id), str(to), str(text), priority=priority, goal=goal)


def bus_route(from_id: Any = None, to: str = "", reason: str = "",
              *args: Any, **kwargs: Any) -> dict[str, Any]:
    if from_id is None:
        from_id = _agent_id()
    kw_reason = kwargs.pop("reason", None)
    if kw_reason and not reason:
        reason = str(kw_reason)
    if args:
        if not to:
            to = str(args[0])
        elif not reason:
            reason = str(args[0])
    target = kwargs.pop("target", None)
    if target:
        to = str(target)
    priority = _normalize_priority(kwargs) or 1
    scores = kwargs.pop("scores", None)
    goal = str(kwargs.pop("goal", "") or "")
    return _route(str(from_id), str(to), str(reason), priority=priority,
                  scores=scores, goal=goal)


def enable_gui() -> None:
    import config
    config.GUI_MODE_PATH.write_text("1", encoding="utf-8")


def disable_gui() -> None:
    import config
    try:
        config.GUI_MODE_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def pause_reactor() -> None:
    import log
    log.set_paused(True)


def spawn_main(goal: str = "", budget: int = 20) -> int:
    child_events = f"events-child-{os.getpid()}.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal or "print('spawned')", "--backend", "lmstudio",
         "--event-budget", str(budget), "--events-path", child_events],
        cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    return proc.pid