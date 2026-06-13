from __future__ import annotations
import os as _os
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
PLUGINS_DIR: pathlib.Path = BASE_DIR / "plugins"
EVENTS_PATH: pathlib.Path = BASE_DIR / "events.jsonl"
CHILD_EVENTS_PATH: pathlib.Path = BASE_DIR / "events-child.jsonl"
SNAPSHOT_PATH: pathlib.Path = BASE_DIR / "snapshot.json"
LESSONS_PATH: pathlib.Path = BASE_DIR / "lessons.jsonl"
GUI_MODE_PATH: pathlib.Path = BASE_DIR / "gui_mode"
GOAL_PATH: pathlib.Path = BASE_DIR / "goal.txt"
PAUSE_PATH: pathlib.Path = BASE_DIR / "pause"
RESPAWN_PATH: pathlib.Path = BASE_DIR / "respawn.json"
LOG_LOCK_PATH: pathlib.Path = BASE_DIR / ".endgame.lock"

EVENT_BUDGET: int = 200
EVENT_ROLLING_MAX_LINES: int = 0  # 0 = unlimited, no trimming
SNAPSHOT_INTERVAL_SEC: float = 2.5

# --- LM Studio ---
def _normalize_lms_host(url: str) -> str:
    u = url.strip().rstrip("/")
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    return u

def _parse_lms_host_list(raw: str) -> list[str]:
    hosts: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        host = _normalize_lms_host(part)
        if host and host not in seen:
            hosts.append(host)
            seen.add(host)
    return hosts

_preferred_host = _normalize_lms_host(_os.environ.get("ENDGAME_LMS_HOST", ""))
_hosts_env = _os.environ.get("ENDGAME_LMS_HOSTS", "")
_candidate_hosts = _parse_lms_host_list(_hosts_env) if _hosts_env else [
    "http://localhost:1234",
    "http://192.168.16.31:1234",
]
if _preferred_host:
    LMS_HOSTS = [_preferred_host] + [h for h in _candidate_hosts if h != _preferred_host]
else:
    LMS_HOSTS = list(_candidate_hosts)
LMS_CANDIDATE_HOSTS: list[str] = list(_candidate_hosts)
LMS_PREFERRED_MODEL: str = _os.environ.get("ENDGAME_LMS_MODEL", "gemma")
LMS_TIMEOUT: float = 90.0
LMS_MODEL_LIST_TIMEOUT: float = 10.0
LMS_REQUEST_ATTEMPTS: int = 3
LMS_RETRY_DELAY: float = 2.0
LMS_ERROR_RETRY_DELAY: float = 3.0
LMS_MAX_SLOTS_PER_HOST: int = 3

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

BUDGET_PLANNER_OUT: int = 1200
BUDGET_ACTOR_OUT: int = 1800
BUDGET_VERIFIER_OUT: int = 700
BUDGET_REFLECTOR_OUT: int = 900
BUDGET_FISSION_JUDGE_OUT: int = 700
BUDGET_MUTATOR_OUT: int = 8000

LOG_TOKEN_USAGE: bool = True

# --- Timing ---
DELAY_BETWEEN_CYCLES: float = 0.08
MATH_INTERVAL: float = 5.0
DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0
EXEC_TIMEOUT: float = 30.0
EXEC_OUTPUT_LIMIT: int = 8000

# --- Math / reactor dynamics ---
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

STAGNATION_CYCLES_WINDOW: int = 5
STAGNATION_FAILURE_WEIGHT: float = 0.08
STAGNATION_FAILURE_CAP: float = 0.35
PLAN_REJECT_COOLDOWN_SEC: float = 10.0
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
COMPLETED_SIMILARITY_THRESHOLD: float = 0.15
PROMPT_MAX_RULES: int = 8
PERSONALITY_MAX_EVOLUTIONS: int = 6

REACTOR_SLOTS: int = 6
MAX_HISTORY: int = 16
MAX_PLAN_STEPS: int = 12

# --- Desktop / observer ---
TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 90
PROBE_FOREGROUND_DELAY: float = 0.3
PROBE_SAMPLE_DELAY: float = 0.001
PROBE_SINE_AMPLITUDE_RATIO: float = 0.4
PROBE_SINE_PERIOD_STEPS: float = 6.0
READ_TEXT_MAX_LENGTH: int = -1
SCREEN_ELEMENT_VALUE_LIMIT: int = -1
TERMINAL_CONTEXT_TAIL_LINES: int = -1
PROCESS_DPI_AWARENESS_CONTEXT: int = -4
OBSERVER_TIMEOUT: int = 30

# --- Bus context for planner ---
CONTEXT_BUS_MAX: int = 10
BUS_CHAT_MAX: int = 120
BUS_EVENTS_MAX_LINES: int = 200
CONTEXT_LESSONS_MAX: int = 3

SIGINT_EXIT_CODE: int = 130

CONTEXT_POLICY: dict[str, list[str]] = {
    "planner": ["goal", "plan", "last_observation", "history", "completed", "desktop", "hints", "bus", "denied_goals"],
    "actor": ["instruction", "history"],
    "verifier": ["goal", "done_when", "last_observation", "completed", "desktop"],
    "reflector": ["goal", "last_observation", "history", "failures", "trigger", "desktop"],
    "fission_judge": ["goal", "done_when", "last_observation", "history", "completed", "similarity"],
    "mutator": ["goal", "last_observation", "history", "failures", "completed", "trigger"],
}
