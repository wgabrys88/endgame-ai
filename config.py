from __future__ import annotations
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
EVENTS_PATH: pathlib.Path = BASE_DIR / "events.jsonl"
SNAPSHOT_PATH: pathlib.Path = BASE_DIR / "snapshot.json"
LESSONS_PATH: pathlib.Path = BASE_DIR / "lessons.txt"
DISABLED_PATH: pathlib.Path = BASE_DIR / "disabled.json"
GUI_MODE_PATH: pathlib.Path = BASE_DIR / "gui_mode"
RESPAWN_PATH: pathlib.Path = BASE_DIR / "respawn.json"
LOG_LOCK_PATH: pathlib.Path = BASE_DIR / ".endgame.lock"

EVENT_BUDGET: int = 20

LMS_HOSTS: list[str] = ["http://localhost:1234"]
LMS_TIMEOUT: float = 300.0
LMS_MODEL_LIST_TIMEOUT: float = 10.0
LMS_REQUEST_ATTEMPTS: int = 3
LMS_RETRY_DELAY: float = 2.0
LMS_ERROR_RETRY_DELAY: float = 3.0

ACP_TIMEOUT: float = 90.0
ACP_PROTOCOL_VERSION: int = 1
ACP_DEFAULT_TIMEOUT: float = 300.0
ACP_REQUEST_TIMEOUT: float = 60.0
ACP_WSL_MKDIR_TIMEOUT: float = 30.0
ACP_SETTINGS_TIMEOUT: float = 30.0
ACP_SETUP_ATTEMPTS: int = 2
ACP_SETUP_RETRY_DELAY: float = 2.0
ACP_CLOSE_TIMEOUT: float = 5.0
ACP_STOP_POLL_SECONDS: float = 0.25
ACP_READ_CHUNK_SIZE: int = 65536
JSONRPC_METHOD_NOT_FOUND: int = -32601
ACP_WORKSPACE_BASE: str = "/tmp/poke-acp"

LLM_TEMPERATURE: float = 0.30
LLM_TOP_P: float = 0.95
LLM_TOP_K: int = 64
LLM_REPEAT_PENALTY: float = 1.05
LLM_PRESENCE_PENALTY: float = 0.0
LLM_FREQUENCY_PENALTY: float = 0.0
LLM_SEED: int | None = 3407
LLM_MAX_TOKENS: int = 200000
LLM_STOP: list[str] = []
LLM_LOGIT_BIAS: dict[str, float] = {}

BUDGET_PLANNER_OUT: int = 4000
BUDGET_ACTOR_OUT: int = 4000
BUDGET_VERIFIER_OUT: int = 4000
BUDGET_REFLECTOR_OUT: int = 8000

DELAY_BETWEEN_CYCLES: float = 0.15
MATH_INTERVAL: float = 3.0
DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0
COMMAND_TIMEOUT_SECONDS: float = 30.0

TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 90
PROBE_FOREGROUND_DELAY: float = 0.3
PROBE_SAMPLE_DELAY: float = 0.001
PROBE_SINE_AMPLITUDE_RATIO: float = 0.4
PROBE_SINE_PERIOD_STEPS: float = 6.0
READ_TEXT_MAX_LENGTH: int = -1
SCREEN_ELEMENT_VALUE_LIMIT: int = 500
TERMINAL_CONTEXT_TAIL_LINES: int = 8

LORENZ_SIGMA: float = 10.0
LORENZ_RHO: float = 28.0
LORENZ_BETA: float = 8.0 / 3.0
LORENZ_DT: float = 0.05
LORENZ_MAG_CAP: float = 80.0
LORENZ_EQUILIBRIUM_OFFSET: float = 1.0
LORENZ_WING_STAG_MIN: float = 0.25
LORENZ_STAG_STEPS_SCALE: int = 12

PID_KP: float = 1.2
PID_KI: float = 0.4
PID_KD: float = 0.6
PID_INTEGRAL_MAX: float = 8.0
PID_DEAD_ZONE: float = 0.05

STAGNATION_CYCLES_WINDOW: int = 4
REFLECT_THRESHOLD: float = 0.6
REFLECT_MIN_INTERVAL_SEC: float = 6.0
REFLECT_STAG_THRESHOLD: float = 0.5
MATH_TRACE_LEN: int = 24
PID_ROD_SCALE: float = 4.0
COMPLETED_SIMILARITY_THRESHOLD: float = 0.55
PROMPT_MAX_RULES: int = 8

MAX_HISTORY: int = 100
MAX_PLAN_STEPS: int = 12

PROCESS_DPI_AWARENESS_CONTEXT: int = -4
SIGINT_EXIT_CODE: int = 130

CONTEXT_POLICY: dict[str, list[str]] = {
    "planner": ["goal", "desktop", "plan", "history", "completed", "budget", "failures", "lessons"],
    "actor": ["instruction", "screen", "history", "lessons"],
    "verifier": ["goal", "done_when", "screen", "history", "plan", "completed"],
    "reflector": ["goal", "plan", "history", "math", "trigger", "completed"],
}
