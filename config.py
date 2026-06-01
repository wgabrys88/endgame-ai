from __future__ import annotations
import io
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
COMMS_DIR: pathlib.Path = BASE_DIR / "comms"
INBOX_PATH: pathlib.Path = COMMS_DIR / "inbox.json"
SCREEN_LOCK_PATH: pathlib.Path = COMMS_DIR / "screen_lock.json"

LMS_HOSTS: list[str] = ["http://localhost:1234", "http://192.168.16.31:1234"]
ACP_TIMEOUT: float = 90.0
LMS_TIMEOUT: int = 120

BUDGET_PLANNER_IN: int = 8000
BUDGET_PLANNER_OUT: int = 4000
BUDGET_ACTOR_IN: int = 8000
BUDGET_ACTOR_OUT: int = 4000
BUDGET_VERIFIER_IN: int = 8000
BUDGET_VERIFIER_OUT: int = 4000
BUDGET_REFLECTOR_IN: int = 16000
BUDGET_REFLECTOR_OUT: int = 8000

DELAY_STARTUP: float = 5.0
DELAY_BETWEEN_ITERATIONS: float = 3.0
CONSECUTIVE_FAILURES_FOR_REFLECT: int = 2
REFLECT_EVERY_N_ITERATIONS: int = 5
DISTILL_EVERY_N_ITERATIONS: int = 10

CONSOLE_VERBOSITY: str = "normal"
ENABLE_FILE_TRACING: bool = False

DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0

TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 70

MAX_HISTORY_ENTRIES: int = 200
MAX_SIGNATURES: int = 100
MAX_LESSONS: int = 50
MAX_LEDGER_ENTRIES: int = 200
CONTEXT_HISTORY_LIMIT: int = 10

CHAOS_HALT_THRESHOLD: float = 0.95
CHAOS_HALT_SUSTAINED_ITERATIONS: int = 5

LLM_TEMPERATURE: float = 0.22
LLM_TOP_P: float = 0.92
LLM_MAX_TOKENS: int = 200000

_trace_handle: io.TextIOWrapper | None = None
_trace_path: pathlib.Path | None = None


def init_trace(execution_id: str) -> None:
    global _trace_handle, _trace_path
    if not ENABLE_FILE_TRACING:
        return
    _trace_path = BASE_DIR / f"trace-{execution_id}.txt"
    _trace_handle = open(_trace_path, "a", encoding="utf-8")


def trace(section: str, data: str) -> None:
    if _trace_handle is None:
        return
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    _trace_handle.write(f"[{ts}] [{section}] {data}\n")
    _trace_handle.flush()


def close_trace() -> None:
    global _trace_handle
    if _trace_handle:
        _trace_handle.close()
        _trace_handle = None
