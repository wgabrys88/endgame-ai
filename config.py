"""Unified colony configuration. Single source of truth."""
from __future__ import annotations
import os
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
PLUGINS_DIR: pathlib.Path = BASE_DIR / "plugins"
EVENTS_PATH: pathlib.Path = BASE_DIR / "events.jsonl"
SNAPSHOT_PATH: pathlib.Path = BASE_DIR / "snapshot.json"
LESSONS_PATH: pathlib.Path = BASE_DIR / "lessons.jsonl"
GOAL_PATH: pathlib.Path = BASE_DIR / "goal.txt"
PAUSE_PATH: pathlib.Path = BASE_DIR / "pause"
RESPAWN_PATH: pathlib.Path = BASE_DIR / "respawn.json"
LOG_LOCK_PATH: pathlib.Path = BASE_DIR / ".endgame.lock"
GUI_MODE_PATH: pathlib.Path = BASE_DIR / "gui_mode"
DISABLED_PATH: pathlib.Path = BASE_DIR / "disabled.json"

# --- Bus ---
BUS_DIR: pathlib.Path = BASE_DIR / "runtime" / "comms"
BUS_CHAT_PATH: pathlib.Path = BUS_DIR / "messages.json"
BUS_EVENTS_PATH: pathlib.Path = BUS_DIR / "events_bus.jsonl"
BUS_INJECT_PATH: pathlib.Path = BUS_DIR / "inject.jsonl"
BUS_CHAT_MAX: int = 120
BUS_EVENTS_MAX: int = 200

# --- LM Studio ---
def _norm(url: str) -> str:
    u = url.strip().rstrip("/")
    return ("http://" + u) if u and not u.startswith(("http://", "https://")) else u

def _hosts(raw: str) -> list[str]:
    seen: set[str] = set()
    return [h for part in raw.split(",") if (h := _norm(part)) and h not in seen and not seen.add(h)]

_env_host = _norm(os.environ.get("ENDGAME_LMS_HOST", ""))
_env_hosts = os.environ.get("ENDGAME_LMS_HOSTS", "")
LMS_CANDIDATE_HOSTS: list[str] = _hosts(_env_hosts) if _env_hosts else ["http://localhost:1234", "http://192.168.16.31:1234"]
LMS_HOSTS: list[str] = ([_env_host] + [h for h in LMS_CANDIDATE_HOSTS if h != _env_host]) if _env_host else list(LMS_CANDIDATE_HOSTS)
LMS_PREFERRED_MODEL: str = os.environ.get("ENDGAME_LMS_MODEL", "gemma")
LMS_TIMEOUT: float = 90.0
LMS_MODEL_LIST_TIMEOUT: float = 10.0
LMS_REQUEST_ATTEMPTS: int = 3
LMS_RETRY_DELAY: float = 2.0
LMS_ERROR_RETRY_DELAY: float = 3.0
LMS_MAX_SLOTS_PER_HOST: int = 3

# --- ACP ---
ACP_TIMEOUT: float = 90.0

# --- LLM generation ---
LLM_TEMPERATURE: float = 0.60
LLM_TOP_P: float = 0.90
LLM_TOP_K: int = 40
LLM_REPEAT_PENALTY: float = 1.07
LLM_PRESENCE_PENALTY: float = 0.0
LLM_FREQUENCY_PENALTY: float = 0.0
LLM_SEED: int | None = 3407
LLM_MAX_TOKENS: int = 128000
LLM_STOP: list[str] = []
LLM_LOGIT_BIAS: dict[str, float] = {}

# --- Budget per role ---
BUDGET: dict[str, int] = {
    "planner": 1200, "verifier": 700, "reflector": 900,
    "fission_judge": 700, "mutator": 8000,
}

# --- Timing ---
DELAY_BETWEEN_CYCLES: float = 0.08
MATH_INTERVAL: float = 5.0
EXEC_TIMEOUT: float = 30.0
EXEC_OUTPUT_LIMIT: int = 8000
SNAPSHOT_INTERVAL_SEC: float = 2.5
PLAN_REJECT_COOLDOWN_SEC: float = 10.0

# --- Desktop ---
DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0

# --- Observer ---
TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 90
PROBE_FOREGROUND_DELAY: float = 0.3
PROBE_SAMPLE_DELAY: float = 0.001
PROBE_SINE_AMPLITUDE_RATIO: float = 0.4
PROBE_SINE_PERIOD_STEPS: float = 6.0

# --- Math engine ---
LORENZ_SIGMA: float = 10.0
LORENZ_RHO: float = 28.0
LORENZ_BETA: float = 8.0 / 3.0
LORENZ_DT: float = 0.04
LORENZ_MAG_CAP: float = 60.0
LORENZ_EQUILIBRIUM_OFFSET: float = 1.0
LORENZ_WING_STAG_MIN: float = 0.35
LORENZ_STAG_STEPS_SCALE: int = 8
PID_KP: float = 0.75
PID_KI: float = 0.22
PID_KD: float = 0.45
PID_INTEGRAL_MAX: float = 4.0
PID_INTEGRAL_DECAY: float = 0.35
PID_DEAD_ZONE: float = 0.08

# --- Scheduler thresholds ---
STAGNATION_CYCLES_WINDOW: int = 5
STAGNATION_FAILURE_WEIGHT: float = 0.08
STAGNATION_FAILURE_CAP: float = 0.35
PLAN_REJECT_FAILURE_MIN: int = 2
REFLECT_THRESHOLD: float = 0.55
REFLECT_MIN_INTERVAL_SEC: float = 12.0
REFLECT_STAG_THRESHOLD: float = 0.45
REFLECT_FAILURE_MIN: int = 2
CHAOS_ENERGY_THRESHOLD: float = 2.5
MUTATOR_ESCALATION_FAILURES: int = 2
MUTATOR_ERROR_MIN_FAILURES: int = 1
MUTATOR_MATH_STAG_MIN: float = 0.30
MUTATOR_PID_MIN: float = 0.35
MUTATOR_ENERGY_MIN: float = 1.8
MUTATOR_MIN_INTERVAL_SEC: float = 8.0
MATH_TRACE_LEN: int = 18
PROMPT_MAX_RULES: int = 8
PERSONALITY_MAX_EVOLUTIONS: int = 6
COMPLETED_SIMILARITY_THRESHOLD: float = 0.15

# --- Reactor ---
REACTOR_SLOTS: int = 6
ROSTER: dict[int, str] = {
    1: "git_expert", 2: "implementor", 3: "doc_inspector",
    4: "comms_operator", 5: "quality_critic", 6: "gui_operator",
}

# --- Misc ---
EVENT_BUDGET: int = 200
MAX_HISTORY: int = 16
MAX_PLAN_STEPS: int = 12
CONTEXT_HISTORY_LINES: int = 8
CONTEXT_OBS_MAX: int = 420
CONTEXT_GOAL_MAX: int = 480
CONTEXT_COMPLETED_MAX: int = 6
CONTEXT_BUS_MAX: int = 10
CONTEXT_PLAN_CODE_MAX: int = 120
PROCESS_DPI_AWARENESS_CONTEXT: int = -4
SIGINT_EXIT_CODE: int = 130
READ_TEXT_MAX_LENGTH: int = -1
SCREEN_ELEMENT_VALUE_LIMIT: int = -1
TERMINAL_CONTEXT_TAIL_LINES: int = -1
