from __future__ import annotations
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
COMMS_DIR: pathlib.Path = BASE_DIR / "comms"
INBOX_PATH: pathlib.Path = COMMS_DIR / "inbox.json"
SCREEN_LOCK_PATH: pathlib.Path = COMMS_DIR / "screen_lock.json"
SCREEN_SNAPSHOT_PATH: pathlib.Path = COMMS_DIR / "screen_snapshot.json"
SCREEN_SNAPSHOT_MAX_AGE: float = 20.0

LMS_HOSTS: list[str] = ["http://localhost:1234"]
ACP_TIMEOUT: float = 90.0
LMS_TIMEOUT: int = 1200

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

STAGNATION_HALT_THRESHOLD: float = 0.95
STAGNATION_HALT_SUSTAINED: int = 5

PIPELINE_LORENZ: bool = True
PIPELINE_PID: bool = True
PIPELINE_JACOBIAN: bool = True

LORENZ_SIGMA: float = 10.0
LORENZ_RHO: float = 28.0
LORENZ_BETA: float = 8.0 / 3.0
LORENZ_DT: float = 0.02
LORENZ_MAG_CAP: float = 80.0
LORENZ_RHO_SENSITIVITY: float = 1.5
LORENZ_BETA_SENSITIVITY: float = 0.3

PID_KP: float = 1.0
PID_KI: float = 0.3
PID_KD: float = 0.8
PID_INTEGRAL_MAX: float = 5.0
PID_DEAD_ZONE: float = 0.05

STAGNATION_WEIGHT_FAILURES: float = 5.0
STAGNATION_WEIGHT_MISS: float = 4.0
STAGNATION_WEIGHT_REPETITION: float = 12.0
STAGNATION_WEIGHT_SCREEN: float = 6.0
STAGNATION_NORMALIZER: float = 28.0

REFLECT_THRESHOLD: float = 0.3
DISTILL_THRESHOLD: float = 2.0

LLM_TEMPERATURE: float = 0.30
LLM_TOP_P: float = 0.95
LLM_TOP_K: int = 64
LLM_REPEAT_PENALTY: float = 1.05
LLM_PRESENCE_PENALTY: float = 0.0
LLM_FREQUENCY_PENALTY: float = 0.0
LLM_SEED: int | None = 3407
LLM_MAX_TOKENS: int = 200000
LLM_STOP: list = []
LLM_LOGIT_BIAS: dict = {}

PROMPT_REWRITE_MIN_LENGTH: int = 200

CONTEXT_POLICY: dict[str, list[str]] = {
    "planner": [
        "goal",
        "checklist",
        "notes",
        "screen_elements",
        "actor_observe",
        "actor_conclusion",
        "last_action",
        "last_result",
        "focused_window",
        "learned_insights",
        "recent_history",
        "consecutive_failures",
        "repetition_warning",
    ],
    "actor": [
        "instruction",
        "screen_elements",
        "notes",
        "checklist_current",
        "learned_insights",
        "last_result_on_failure",
    ],
    "verifier": [
        "goal",
        "checklist",
        "full_history",
        "screen_elements",
        "done_claimed",
        "planner_reasoning",
        "focused_window",
        "notes",
    ],
    "reflector": [
        "goal",
        "iteration",
        "checklist",
        "notes",
        "full_history",
        "screen_elements",
        "last_action",
        "last_result",
        "last_expect",
        "actor_observe",
        "planner_reasoning",
        "stagnation_score",
        "consecutive_failures",
        "pid",
        "focused_window",
        "learned_insights",
        "failed_step_index",
        "current_prompts",
    ],
    "distillation": [
        "goal",
        "iteration",
        "stagnation_score",
        "consecutive_failures",
        "evolution_ledger",
        "learned_insights",
        "pid",
        "attractor_energy",
        "repetition_score",
        "lorenz",
    ],
}
