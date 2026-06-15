"""Colony configuration — slots, personas, model profiles."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

# --- Paths ---
BASE_DIR: Path = Path(os.path.dirname(os.path.abspath(__file__)))
BUS_DIR: Path = BASE_DIR / "runtime" / "comms"
BUS_CHAT_PATH: Path = BUS_DIR / "messages.json"
BUS_EVENTS_PATH: Path = BUS_DIR / "events_bus.jsonl"
BUS_INJECT_PATH: Path = BUS_DIR / "inject.jsonl"
BUS_CONTROL_PATH: Path = BUS_DIR / "control.jsonl"
BREED_ARCHIVE_PATH: Path = BASE_DIR / "runtime" / "breed_archive.json"
EVENTS_PATH: Path = BASE_DIR / "events.jsonl"
LESSONS_PATH: Path = BASE_DIR / "lessons.jsonl"
PROMPTS_DIR: Path = BASE_DIR / "prompts"

PLUGINS_DIR: Path = BASE_DIR / "plugins"
GUI_MODE_PATH: Path = BASE_DIR / "gui_mode"  # legacy exec target only (write_file gui_mode)
COLONY_GOAL_PATH: Path = BASE_DIR / "runtime" / "colony_goal.txt"
DEFAULT_MODEL_PROFILE: str = "nemotron_parallel"

# --- .env loader ---
_dotenv = BASE_DIR / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# --- Slots ---
SLOTS: int = 5  # total parallel processes (slot 1 = comms_operator, 2-5 = dynamic)

# --- Persona pool (available personalities) ---
PERSONAS: list[str] = [
    "comms_operator", "architect", "implementor", "reviewer",
    "devops", "quality_critic",
]

# Worker pool (slots 2-5) — comms_operator MoE experts
WORKER_PERSONAS: list[str] = ["architect", "implementor", "reviewer", "devops", "quality_critic"]
SLOT_DEFAULTS: dict[int, str] = {2: "architect", 3: "implementor", 4: "reviewer", 5: "devops"}
PERSONA_SLOTS: dict[str, int] = {v: k for k, v in SLOT_DEFAULTS.items()}
@dataclass(frozen=True, slots=True)
class Personality:
    """One endgame-ai slot instance — name, slot, mission (OoO identity object)."""
    name: str
    slot: int
    mission: str

    @classmethod
    def load(cls, name: str, slot: int = 0, mission: str = "") -> Personality:
        text = mission.strip()
        if not text and name:
            pfile = PROMPTS_DIR / "personalities" / f"{name}.txt"
            if pfile.exists():
                text = pfile.read_text(encoding="utf-8").strip()
        return cls(name=name, slot=slot, mission=text)

    @classmethod
    def from_env(cls, mission_override: str = "") -> Personality:
        name = os.environ.get("ENDGAME_PERSONALITY", "").strip()
        slot = int(os.environ.get("ENDGAME_SLOT", "0") or 0)
        return cls.load(name, slot, mission_override)

    @property
    def is_orchestrator(self) -> bool:
        return self.name == "comms_operator"

    @property
    def is_worker(self) -> bool:
        return self.name in WORKER_PERSONAS

    def bus_context_depth(self) -> int:
        return 10 if self.is_orchestrator else 6
# --- Priority levels ---
PRI_MAINTENANCE: int = 0
PRI_NORMAL: int = 1
PRI_CRITICAL: int = 2
PRI_HUMAN: int = 3

# --- LM Studio ---
_env_hosts = os.environ.get("ENDGAME_LMS_HOSTS", "").strip()
_env_host = os.environ.get("ENDGAME_LMS_HOST", "").strip()
LMS_HOSTS: list[str] = [_env_host] if _env_host else ([h.strip() for h in _env_hosts.split(",") if h.strip()] or ["http://localhost:1234"])
LMS_TIMEOUT: int = 300  # per-request HTTP timeout (nemotron profile overrides to 600)
LMS_MODEL_LIST_TIMEOUT: int = 8
LMS_REQUEST_ATTEMPTS: int = 2
LMS_RETRY_DELAY: float = 3.0

# --- LLM generation defaults ---
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
LLM_MAX_CONCURRENT: int = 1  # thread gate; match LM Studio Max Concurrent Predictions
LMS_GLOBAL_LOCK_PATH: Path = BASE_DIR / "runtime" / ".lmstudio.lock"
LMS_USE_GLOBAL_LOCK: bool = True  # False when LM Studio MC>1 and LLM_MAX_CONCURRENT>1
LMS_TRACE_PROMPTS: bool = True
LLM_THINKING_ENABLED: bool = True
LLM_THINKING_BUDGET: int = 4096  # default reasoning cap when role not in THINKING_BUDGET
LLM_REASONING_LOG_MAX: int = 12000  # session log cap for captured reasoning text
LLM_API_SCHEMA: bool = False  # loose JSON hints in prompts; no strict response_format

BUDGET: dict[str, int] = {
    "planner": 2048, "verifier": 512, "reflector": 1024,
    "fission_judge": 1024, "mutator": 2048,
}
THINKING_BUDGET: dict[str, int] = {
    "planner": 1536, "verifier": 256, "reflector": 512,
    "fission_judge": 256, "mutator": 1024,
}

# --- Model profiles ---
MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "nemotron": {
        "LLM_TEMPERATURE": 0.12, "LLM_TOP_P": 0.88, "LLM_TOP_K": 40,
        "LLM_REPEAT_PENALTY": 1.06, "LLM_PRESENCE_PENALTY": 0.0,
        "LLM_FREQUENCY_PENALTY": 0.0, "LLM_SEED": 3407,
        "LLM_MAX_TOKENS": 1536, "LLM_STOP": [], "LLM_LOGIT_BIAS": {},
        "LLM_MAX_CONCURRENT": 1, "LMS_USE_GLOBAL_LOCK": True,
        "LLM_THINKING_ENABLED": True, "LLM_THINKING_BUDGET": 1536,
        "LLM_API_SCHEMA": False,
        "LMS_TIMEOUT": 600,
        "BUDGET": {"planner": 1400, "verifier": 384, "reflector": 640, "fission_judge": 320, "mutator": 1280},
        "THINKING_BUDGET": {"planner": 1536, "verifier": 256, "reflector": 512, "fission_judge": 256, "mutator": 1024},
    },
    "nemotron_parallel": {
        "LLM_TEMPERATURE": 0.12, "LLM_TOP_P": 0.88, "LLM_TOP_K": 40,
        "LLM_REPEAT_PENALTY": 1.06, "LLM_PRESENCE_PENALTY": 0.0,
        "LLM_FREQUENCY_PENALTY": 0.0, "LLM_SEED": 3407,
        "LLM_MAX_TOKENS": 1280, "LLM_STOP": [], "LLM_LOGIT_BIAS": {},
        "LLM_MAX_CONCURRENT": 5, "LMS_USE_GLOBAL_LOCK": False,
        "LLM_THINKING_ENABLED": True, "LLM_THINKING_BUDGET": 768,
        "LLM_API_SCHEMA": True,
        "LMS_TIMEOUT": 600,
        "BUDGET": {"planner": 1152, "verifier": 288, "reflector": 448, "fission_judge": 448, "mutator": 896},
        "THINKING_BUDGET": {"planner": 1536, "verifier": 192, "reflector": 384, "fission_judge": 128, "mutator": 640},
    },
    "gemma": {
        "LLM_TEMPERATURE": 0.60, "LLM_TOP_P": 0.90, "LLM_TOP_K": 40,
        "LLM_REPEAT_PENALTY": 1.07, "LLM_PRESENCE_PENALTY": 0.0,
        "LLM_FREQUENCY_PENALTY": 0.0, "LLM_SEED": 3407,
        "LLM_MAX_TOKENS": 128000, "LLM_STOP": [], "LLM_LOGIT_BIAS": {},
        "LLM_MAX_CONCURRENT": 2, "LLM_THINKING_ENABLED": False, "LLM_THINKING_BUDGET": 0,
        "BUDGET": {"planner": 1200, "verifier": 700, "reflector": 900, "fission_judge": 700, "mutator": 8000},
    },
}

_active_profile: str = ""
def apply_model_profile(profile_or_model: str, *, force: bool = False) -> tuple[str, bool]:
    """Apply a model profile by name or auto-detect from model id."""
    global _active_profile
    normalized = profile_or_model.lower()
    if normalized in MODEL_PROFILES:
        key = normalized
    else:
        key = ""
        matches = [c for c in MODEL_PROFILES if c in normalized]
        if matches:
            key = max(matches, key=len)
    if not key or (key == _active_profile and not force):
        return key or _active_profile, False
    profile = MODEL_PROFILES[key]
    for name, value in profile.items():
        if name in globals():
            globals()[name] = value
    _active_profile = key
    return key, True
def active_model_profile() -> str:
    return _active_profile
# --- Timing ---
DELAY_BETWEEN_CYCLES: float = 2.0
BUS_POLL_INTERVAL: float = 3.0  # check bus for priority interrupts
COMMS_ROUTE_INTERVAL: float = 20.0  # comms_operator MoE routing cadence (seconds)

# --- Pressure / MoE escalation (Rodriguez 2026) ---
STAG_ESCALATE: float = 0.7       # stagnation threshold for band escalation
VEL_STUCK: float = 0.01          # |velocity| below this = no progress
STUCK_TICKS_ESCALATE: int = 5    # consecutive stuck telemetry readings before reassign
MOE_GATE_MIN: float = 0.10       # minimum softmax weight to route maintenance work
PLANNER_ERROR_RAW_MAX: int = 2000  # session log cap for planner.error LLM raw

# --- Breeding / AgentBreeder selection ---
BREED_RETAIN_MIN: float = 0.60   # fission fitness needed for reactor survivor retention
BREED_ELITE_MIN_DELTA: float = 0.01  # fitness gain needed to replace an elite niche
BREED_ELITE_MAX_NICHES: int = 24  # bounded in-memory quality-diversity archive
BREED_ELITE_RESPAWN_MIN: float = 0.60  # elite fitness needed to repopulate a dead slot
BREED_TRIAL_EVAL_SECONDS: float = 60.0  # wait for telemetry after selection before scoring
BREED_TRIAL_SAMPLES: int = 3      # repeated outcome samples before a trial closes
BREED_IMPROVE_MIN_DELTA: float = 0.05  # pressure/power delta needed for mutation improvement evidence
MUTATE_AFTER_FAILURES: int = 2    # failure cycles before mutator may patch a plugin

# --- Bus limits ---
BUS_CHAT_MAX: int = 200
BUS_EVENTS_MAX: int = 500

# --- Context rendering ---
CONTEXT_BUS_MAX: int = 8
CONTEXT_OBS_MAX: int = 600
TERMINAL_CONTEXT_TAIL_LINES: int = -1

# --- ACP (sequential backend via WSL/Kiro) ---
ACP_WORKSPACE_BASE: str = "/tmp/endgame-acp"
ACP_PROTOCOL_VERSION: int = 1
ACP_DEFAULT_TIMEOUT: float = 300.0
ACP_REQUEST_TIMEOUT: float = 60.0
ACP_CLOSE_TIMEOUT: float = 5.0
ACP_WSL_MKDIR_TIMEOUT: float = 10.0
ACP_SETTINGS_TIMEOUT: float = 15.0
ACP_SETUP_ATTEMPTS: int = 3
ACP_SETUP_RETRY_DELAY: float = 2.0
ACP_STOP_POLL_SECONDS: float = 1.0
ACP_READ_CHUNK_SIZE: int = 4096
JSONRPC_METHOD_NOT_FOUND: int = -32601

# --- Plans ---
MAX_PLAN_STEPS: int = 6
MAX_HISTORY: int = 12

# --- Execution ---
EXEC_TIMEOUT: int = 60
EXEC_OUTPUT_LIMIT: int = 2000
MAX_WAIT_SECONDS: float = 30.0

# --- Desktop observer (ported from main) ---
PROCESS_DPI_AWARENESS_CONTEXT: int = -4
DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
TREE_WALK_TIMEOUT: float = 5.0
PROBE_STEP_PX: int = 90
PROBE_FOREGROUND_DELAY: float = 0.3
PROBE_SAMPLE_DELAY: float = 0.001
PROBE_SINE_AMPLITUDE_RATIO: float = 0.4
PROBE_SINE_PERIOD_STEPS: float = 6.0
READ_TEXT_MAX_LENGTH: int = 200
SCREEN_ELEMENT_VALUE_LIMIT: int = 1000
EVENT_BUDGET: int = 999999
