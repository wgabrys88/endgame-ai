"""Colony configuration — flat, no dead constants."""
from __future__ import annotations
from pathlib import Path
import os

# --- Paths ---
BASE_DIR: Path = Path(os.path.dirname(os.path.abspath(__file__)))
BUS_DIR: Path = BASE_DIR / "runtime" / "comms"
BUS_CHAT_PATH: Path = BUS_DIR / "messages.json"
BUS_EVENTS_PATH: Path = BUS_DIR / "events_bus.jsonl"
BUS_INJECT_PATH: Path = BUS_DIR / "inject.jsonl"
EVENTS_PATH: Path = BASE_DIR / "events.jsonl"
SNAPSHOT_PATH: Path = BASE_DIR / "snapshot.json"
LESSONS_PATH: Path = BASE_DIR / "lessons.jsonl"
GOAL_PATH: Path = BASE_DIR / "goal.txt"
PAUSE_PATH: Path = BASE_DIR / "pause"
GUI_MODE_PATH: Path = BASE_DIR / "gui_mode"
LOG_LOCK_PATH: Path = BASE_DIR / ".endgame.lock"
RESPAWN_PATH: Path = BASE_DIR / "respawn.json"
PROMPTS_DIR: Path = BASE_DIR / "prompts"
SCHEMAS_DIR: Path = BASE_DIR / "schemas"
PLUGINS_DIR: Path = BASE_DIR / "plugins"

# --- Reactor ---
REACTOR_SLOTS: int = 6
ROSTER: dict[int, str] = {
    1: "architect",
    2: "implementor",
    3: "reviewer",
    4: "comms_operator",
    5: "devops",
    6: "quality_critic",
}

# --- LM Studio ---
# --- LM Studio hosts ---
# Load .env if present (ENDGAME_LMS_HOSTS=http://host:port,...)
_dotenv = BASE_DIR / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

_env_hosts = os.environ.get("ENDGAME_LMS_HOSTS", "").strip()
_env_host = os.environ.get("ENDGAME_LMS_HOST", "").strip()
LMS_CANDIDATE_HOSTS: tuple[str, ...] = tuple(h.strip() for h in _env_hosts.split(",") if h.strip()) if _env_hosts else ("http://localhost:1234",)
LMS_HOSTS: list[str] = [_env_host] if _env_host else list(LMS_CANDIDATE_HOSTS)
LMS_PREFERRED_MODEL: str = ""
LMS_TIMEOUT: int = 180
LMS_MODEL_LIST_TIMEOUT: int = 8
LMS_REQUEST_ATTEMPTS: int = 2
LMS_RETRY_DELAY: float = 3.0
LMS_MAX_SLOTS_PER_HOST: int = 6

# --- LLM generation ---
LLM_TEMPERATURE: float = 0.7
LLM_TOP_P: float = 0.9
LLM_TOP_K: int = 40
LLM_MAX_TOKENS: int = 2048
LLM_STOP: list[str] = []
LLM_PRESENCE_PENALTY: float = 0.0
LLM_FREQUENCY_PENALTY: float = 0.0
LLM_LOGIT_BIAS: dict[str, float] = {}
LLM_REPEAT_PENALTY: float = 1.05
LLM_SEED: int = -1

BUDGET: dict[str, int] = {
    "planner": 2048,
    "verifier": 512,
    "reflector": 1024,
    "fission_judge": 1024,
    "mutator": 2048,
}

# --- ACP ---
ACP_TIMEOUT: int = 120
ACP_WORKSPACE_BASE: str = "/tmp/endgame-acp"
ACP_PROTOCOL_VERSION: int = 1
ACP_DEFAULT_TIMEOUT: float = 120.0
ACP_REQUEST_TIMEOUT: float = 30.0
ACP_CLOSE_TIMEOUT: float = 5.0
ACP_WSL_MKDIR_TIMEOUT: float = 10.0
ACP_SETTINGS_TIMEOUT: float = 15.0
ACP_SETUP_ATTEMPTS: int = 3
ACP_SETUP_RETRY_DELAY: float = 2.0
ACP_STOP_POLL_SECONDS: float = 1.0
ACP_READ_CHUNK_SIZE: int = 4096
JSONRPC_METHOD_NOT_FOUND: int = -32601

# --- Timing (tuned for slow local LLM — 20-60s per response) ---
MATH_INTERVAL: float = 12.0           # was 8 — give LLM time to respond before next math tick
DELAY_BETWEEN_CYCLES: float = 3.0     # was 2 — breathing room between agent chains
SNAPSHOT_INTERVAL_SEC: float = 10.0
PLAN_REJECT_COOLDOWN_SEC: float = 45.0  # was 30 — longer cooldown for slow models

# --- Stagnation (tuned: slow responses = fewer cycles before progress, so lower sensitivity) ---
STAGNATION_CYCLES_WINDOW: int = 8      # was 6 — wider window to absorb slow LLM latency
STAGNATION_FAILURE_WEIGHT: float = 0.12  # was 0.15 — less aggressive per-failure spike
STAGNATION_FAILURE_CAP: float = 0.6     # was 0.7 — cap lower so one timeout doesn't max stagnation

# --- Lorenz ---
LORENZ_SIGMA: float = 10.0
LORENZ_RHO: float = 28.0
LORENZ_BETA: float = 8.0 / 3.0
LORENZ_DT: float = 0.005
LORENZ_STAG_STEPS_SCALE: int = 12
LORENZ_MAG_CAP: float = 60.0
LORENZ_WING_STAG_MIN: float = 0.5
LORENZ_EQUILIBRIUM_OFFSET: float = 1.0

# --- PID (tuned: lower gains so slow responses don't spike PID output) ---
PID_KP: float = 1.2     # was 1.5
PID_KI: float = 0.3     # was 0.4
PID_KD: float = 0.4     # was 0.5
PID_DEAD_ZONE: float = 0.08
PID_INTEGRAL_DECAY: float = 0.1
PID_INTEGRAL_MAX: float = 4.0   # was 5.0

# --- Scheduler thresholds (raised: need more signal before escalation with slow LLM) ---
REFLECT_MIN_INTERVAL_SEC: float = 90.0    # was 60 — reflections are expensive LLM calls
REFLECT_THRESHOLD: float = 2.0            # was 1.5
REFLECT_STAG_THRESHOLD: float = 0.55      # was 0.5
REFLECT_FAILURE_MIN: int = 3              # was 2
CHAOS_ENERGY_THRESHOLD: float = 2.0
PLAN_REJECT_FAILURE_MIN: int = 4          # was 3
MUTATOR_MIN_INTERVAL_SEC: float = 120.0   # was 90
MUTATOR_ERROR_MIN_FAILURES: int = 3       # was 2
MUTATOR_ESCALATION_FAILURES: int = 6      # was 5
MUTATOR_MATH_STAG_MIN: float = 0.6       # was 0.5
MUTATOR_PID_MIN: float = 2.5             # was 2.0
MUTATOR_ENERGY_MIN: float = 2.0          # was 1.5

# --- Plans ---
MAX_PLAN_STEPS: int = 6
MAX_HISTORY: int = 12

# --- Context rendering ---
# --- Bus ---
BUS_CHAT_MAX: int = 200
BUS_EVENTS_MAX: int = 500

# --- Context rendering ---
CONTEXT_GOAL_MAX: int = 600
CONTEXT_PLAN_CODE_MAX: int = 400
CONTEXT_HISTORY_LINES: int = 6
CONTEXT_OBS_MAX: int = 600
CONTEXT_COMPLETED_MAX: int = 10
CONTEXT_BUS_MAX: int = 8

# --- Self-evolution ---
PROMPT_MAX_RULES: int = 6
PERSONALITY_MAX_EVOLUTIONS: int = 4

# --- Execution ---
EXEC_TIMEOUT: int = 60
EXEC_OUTPUT_LIMIT: int = 2000
EVENT_BUDGET: int = 999999
MATH_TRACE_LEN: int = 60

# --- Desktop (kept for gui_operator) ---
DELAY_FOCUS: float = 0.15
DELAY_CURSOR_SETTLE: float = 0.08
DELAY_MOUSE_HOLD: float = 0.03
DELAY_CHAR_SEND: float = 0.008
DELAY_KEY_INTER: float = 0.02
MAX_WAIT_SECONDS: float = 30.0

# --- Win32 ---
PROCESS_DPI_AWARENESS_CONTEXT: int = -4
SIGINT_EXIT_CODE: int = 130
READ_TEXT_MAX_LENGTH: int = -1
SCREEN_ELEMENT_VALUE_LIMIT: int = -1
TERMINAL_CONTEXT_TAIL_LINES: int = -1
