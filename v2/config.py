from __future__ import annotations
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
COMMS_DIR: pathlib.Path = BASE_DIR / "comms"
INBOX_PATH: pathlib.Path = COMMS_DIR / "inbox.json"
SCREEN_LOCK_PATH: pathlib.Path = COMMS_DIR / "screen_lock.json"
SNAPSHOT_PATH: pathlib.Path = BASE_DIR / "snapshot.json"

LMS_HOSTS: list[str] = ["http://localhost:1234", "http://192.168.16.31:1234"]
ACP_TIMEOUT: float = 360.0
LMS_TIMEOUT: int = 300

BUDGET_PLANNER_IN: int = 8000
BUDGET_PLANNER_OUT: int = 4000
BUDGET_ACTOR_IN: int = 8000
BUDGET_ACTOR_OUT: int = 4000
BUDGET_VERIFIER_IN: int = 8000
BUDGET_VERIFIER_OUT: int = 4000
BUDGET_REFLECTOR_IN: int = 16000
BUDGET_REFLECTOR_OUT: int = 8000

MAX_CYCLES_DEFAULT: int = 10
DELAY_STARTUP: float = 5.0
DELAY_BETWEEN_CYCLES: float = 3.0
CONSECUTIVE_FAILURES_FOR_REFLECT: int = 2
REFLECT_EVERY_N_CYCLES: int = 5
DISTILL_EVERY_N_CYCLES: int = 10

DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0

TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 70

ARTIFACT_THRESHOLD: int = 4096
COMPACT_THRESHOLD: int = 512_000

LLM_TEMPERATURE: float = 0.22
LLM_TOP_P: float = 0.92
LLM_MAX_TOKENS: int = 200000

_TRACE_HANDLE = None
_TRACE_PATH: pathlib.Path | None = None


def init_trace(execution_id: str) -> None:
    global _TRACE_HANDLE, _TRACE_PATH
    _TRACE_PATH = BASE_DIR / f"trace-{execution_id}.txt"
    _TRACE_HANDLE = open(_TRACE_PATH, "a", encoding="utf-8")


def trace(section: str, data: str) -> None:
    if _TRACE_HANDLE is None:
        return
    import time
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    _TRACE_HANDLE.write(f"[{ts}] [{section}] {data}\n")
    _TRACE_HANDLE.flush()


def close_trace() -> None:
    global _TRACE_HANDLE
    if _TRACE_HANDLE:
        _TRACE_HANDLE.close()
        _TRACE_HANDLE = None