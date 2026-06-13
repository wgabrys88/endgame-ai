"""Colony configuration — slots, personas, model profiles."""
from __future__ import annotations
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
EVENTS_PATH: Path = BASE_DIR / "events.jsonl"
LESSONS_PATH: Path = BASE_DIR / "lessons.jsonl"
PROMPTS_DIR: Path = BASE_DIR / "prompts"
SCHEMAS_DIR: Path = BASE_DIR / "schemas"
PLUGINS_DIR: Path = BASE_DIR / "plugins"

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

# --- Priority levels ---
PRI_MAINTENANCE: int = 0
PRI_NORMAL: int = 1
PRI_CRITICAL: int = 2
PRI_HUMAN: int = 3

# --- LM Studio ---
_env_hosts = os.environ.get("ENDGAME_LMS_HOSTS", "").strip()
_env_host = os.environ.get("ENDGAME_LMS_HOST", "").strip()
LMS_HOSTS: list[str] = [_env_host] if _env_host else ([h.strip() for h in _env_hosts.split(",") if h.strip()] or ["http://localhost:1234"])
LMS_TIMEOUT: int = 300  # 5min — nemotron is slow with 5 parallel
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
LLM_MAX_CONCURRENT: int = 1  # orchestrator: 1 LLM call at a time (nemotron-safe)
LLM_THINKING_ENABLED: bool = True
LLM_THINKING_BUDGET: int = 4096  # cap reasoning tokens — keeps latency predictable

BUDGET: dict[str, int] = {
    "planner": 2048, "verifier": 512, "reflector": 1024,
    "fission_judge": 1024, "mutator": 2048,
}

# --- Model profiles ---
MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "nemotron": {
        "LLM_TEMPERATURE": 1.0, "LLM_TOP_P": 1.0, "LLM_TOP_K": 20,
        "LLM_REPEAT_PENALTY": 1.0, "LLM_PRESENCE_PENALTY": 0.0,
        "LLM_FREQUENCY_PENALTY": 0.0, "LLM_SEED": -1,
        "LLM_MAX_TOKENS": 128000, "LLM_STOP": [], "LLM_LOGIT_BIAS": {},
        "LLM_MAX_CONCURRENT": 1, "LLM_THINKING_ENABLED": True, "LLM_THINKING_BUDGET": 1024,
        "LMS_TIMEOUT": 600,
        "BUDGET": {"planner": 1024, "verifier": 1024, "reflector": 2048, "fission_judge": 1024, "mutator": 4096},
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


def apply_model_profile(profile_or_model: str) -> tuple[str, bool]:
    """Apply a model profile by name or auto-detect from model id."""
    global _active_profile
    normalized = profile_or_model.lower()
    key = ""
    for candidate in MODEL_PROFILES:
        if candidate == normalized or candidate in normalized:
            key = candidate
            break
    if not key or key == _active_profile:
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
HUMAN_GOAL_MAX_DENIALS: int = 3  # stop replanning human pri=3 goals after N verify denials
PLANNER_ERROR_RAW_MAX: int = 2000  # session log cap for planner.error LLM raw

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
EVENT_BUDGET: int = 999999
