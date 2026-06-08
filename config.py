from __future__ import annotations
import pathlib

ZERO_INT: int = 0
ONE_INT: int = 1
TWO_INT: int = 2
FLOAT_ZERO: float = 0.0
FLOAT_ONE: float = 1.0

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
COMMS_DIR: pathlib.Path = BASE_DIR / "comms"
INBOX_PATH: pathlib.Path = COMMS_DIR / "inbox.json"
SCREEN_LOCK_PATH: pathlib.Path = COMMS_DIR / "screen_lock.json"
SCREEN_SNAPSHOT_PATH: pathlib.Path = COMMS_DIR / "screen_snapshot.json"
BLACKBOARD_EVENTS_PATH: pathlib.Path = BASE_DIR / "blackboard_events.txt"
RUNTIME_LOG_SUFFIX: str = ".txt"
ARTIFACTS_DIR: pathlib.Path = BASE_DIR / "runtime_artifacts"
STOP_SIGNAL_PATH: pathlib.Path = COMMS_DIR / "stop.txt"
SCREEN_SNAPSHOT_MAX_AGE: float = 20.0

LMS_HOSTS: list[str] = ["http://localhost:1234"]
ACP_TIMEOUT: float = 90.0
ACP_PROTOCOL_VERSION: int = 1
ACP_DEFAULT_TIMEOUT: float = 300.0
ACP_REQUEST_TIMEOUT: float = 60.0
ACP_WSL_MKDIR_TIMEOUT: float = 30.0
ACP_SETTINGS_TIMEOUT: float = 30.0
ACP_CLOSE_TIMEOUT: float = 5.0
ACP_STOP_POLL_SECONDS: float = 0.25
ACP_READ_CHUNK_SIZE: int = 65536
JSONRPC_METHOD_NOT_FOUND: int = -32601
ACP_WORKSPACE_BASE: str = "/tmp/poke-acp"
LMS_TIMEOUT: float = 300.0
LMS_MODEL_LIST_TIMEOUT: float = 10.0
LMS_MODEL_RELOAD_TIMEOUT: float = 60.0
LMS_MODEL_RELOAD_DELAY: float = 5.0
LMS_REQUEST_ATTEMPTS: int = 3
LMS_RETRY_DELAY: float = 2.0
LMS_ERROR_RETRY_DELAY: float = 3.0

LOG_SCHEMA_VERSION: int = 1
LOG_NO_ITERATION: int = -1
TUI_WRITE_CHUNK_SIZE: int = 65536
TUI_MODE_AUTO: str = "auto"
TUI_MODE_VISUAL: str = "visual"
TUI_MODE_JSON: str = "json"
TUI_ALT_SCREEN_ON: str = "\x1b[?1049h"
TUI_ALT_SCREEN_OFF: str = "\x1b[?1049l"
TUI_HIDE_CURSOR: str = "\x1b[?25l"
TUI_SHOW_CURSOR: str = "\x1b[?25h"
TUI_HOME_CLEAR: str = "\x1b[H\x1b[2J"
TUI_PORTRAIT_ASPECT_W: int = 9
TUI_PORTRAIT_ASPECT_H: int = 16
TUI_MIN_GRAPH_WIDTH: int = 48
TUI_MIN_GRAPH_HEIGHT: int = 16
TUI_STATUS_ROWS: int = 10
TUI_LORENZ_TRAIL_MAX: int = 160
TUI_TEXT_COLS_MIN: int = 28
TUI_SIXEL_CELL_ASPECT: int = 2
STD_OUTPUT_HANDLE: int = -11
WT_SESSION_ENV: str = "WT_SESSION"
WT_PROFILE_ENV: str = "WT_PROFILE_ID"
COMMAND_TIMEOUT_SECONDS: float = 30.0
COMMAND_EXECUTABLE: str = "wsl.exe"
COMMAND_SHELL: str = "bash"
COMMAND_SHELL_FLAG: str = "-lc"
DURATION_MS_PER_SECOND: int = 1000
SIGINT_EXIT_CODE: int = 130
CHILD_TERMINATE_EXIT_CODE: int = 1
PROCESS_DPI_AWARENESS_CONTEXT: int = -4
PROCESS_TERMINATE_RIGHT: int = 0x0001
HTTP_ERROR_STATUS_MIN: int = 400
DEFAULT_SCROLL_AMOUNT: int = 3
DEFAULT_WAIT_SECONDS: float = 1.0
READ_TEXT_MAX_LENGTH: int = -1
CONTEXT_OBSERVATION_EVIDENCE_LINES: int = 3
PERSISTENCE_REPLACE_ATTEMPTS: int = 5
PERSISTENCE_REPLACE_RETRY_DELAY: float = 0.2
ARTIFACT_INLINE_CHAR_LIMIT: int = 12000
ARTIFACT_CHUNK_CHAR_LIMIT: int = 60000
ARTIFACT_SHA_PREFIX_LENGTH: int = 16
ARTIFACT_PATH_PART_LIMIT: int = 48
READ_FILE_EVIDENCE_MARKER: str = "sha256="
SCREEN_ELEMENT_VALUE_LIMIT: int = 240
TERMINAL_CONTEXT_TAIL_LINES: int = 8
MAX_BLACKBOARD_EVENT_RECORDS: int = 400
MAX_RUNTIME_ARTIFACT_ENTRIES: int = 120
OBSERVER_PROBE_ACTION_MIN: int = 1
OBSERVER_REGION_NAME_INDEX: int = 4

PROBE_FOREGROUND_DELAY: float = 0.3
PROBE_SAMPLE_DELAY: float = 0.001
PROBE_SINE_AMPLITUDE_RATIO: float = 0.4
PROBE_SINE_PERIOD_STEPS: float = 6.0
WINDOW_SORT_FALLBACK_RANK: int = 999
AGENT_ID_HEX_LENGTH: int = 6
STUCKNESS_SLOPE_EPSILON: float = 0.01
DISTILLATION_ITERATION_OFFSET: int = -10
DISTILLATION_ITERATION_INTERVAL: int = 10
MAX_PARALLEL_CHILDREN_EXACT: int = 4
MAX_PARALLEL_CHILDREN_DEFAULT: int = 8
CHECKLIST_REWRITE_MIN_STEPS: int = 2
PID_KP_MIN: float = 0.1
PID_KP_MAX: float = 3.0
PID_KI_MIN: float = 0.05
PID_KI_MAX: float = 1.0
PID_KD_MIN: float = 0.5
PID_KD_MAX: float = 5.0
ACTION_ID_HEX_LENGTH: int = 6
LESSON_ID_HEX_LENGTH: int = 16
PROMPT_MUTATIONS_ENABLED: bool = False
PROMPT_MUTATION_LESSON_THRESHOLD: int = 3
PROMPT_MUTATION_LINE_MAX_CHARS: int = 180
PROMPT_MUTATION_ISSUE_TOKEN_LIMIT: int = 5
PROMPT_MUTATION_ISSUE_TOKEN_MIN_LENGTH: int = 2
TIER3_PATTERN_LESSON_THRESHOLD: int = 6
TIER3_PROMPT_MUTATION_THRESHOLD: int = 2
REFLECT_MIN_ITERATION_INTERVAL: int = 4
REFLECT_MIN_CONSECUTIVE_FAILURES: int = 2
REFLECT_MIN_EXPECTATION_MISSES: int = 2
REFLECT_MIN_REPETITION_SCORE: float = 0.5
MUTABLE_PROMPT_START: str = "### MUTABLE_LESSONS_START"
MUTABLE_PROMPT_END: str = "### MUTABLE_LESSONS_END"
GOAL_WRAPPER_START: str = "ENDGAME_GOAL_WRAPPER_START"
GOAL_WRAPPER_END: str = "ENDGAME_GOAL_WRAPPER_END"
GOAL_WRAPPER_HUMAN_START: str = "HUMAN_GOAL_START"
GOAL_WRAPPER_HUMAN_END: str = "HUMAN_GOAL_END"
GOAL_WRAPPER_PREFIX: str = """ENDGAME_GOAL_WRAPPER_START
SYSTEM_OPERATING_GOAL:
- Work from visible GUI evidence first when a human interface is involved.
- Use the available verbs and backend tools; do not wait for the human to describe system mechanics.
- Build or maintain a checklist for multi-step work.
- Replan when evidence changes, an action repeats, or the current route is blocked.
- Chain actions through observe, plan, act, verify, and reflect instead of treating the goal as one prompt.
- Use child agents only for independent work that can report back.
- Preserve full evidence in logs and use compact role context.
- Learn reusable lessons during reflection; mutate prompts only through guarded Python policy.
- Complete only when verifier evidence proves the human goal.
HUMAN_GOAL_START
"""
GOAL_WRAPPER_SUFFIX: str = """
HUMAN_GOAL_END
ENDGAME_GOAL_WRAPPER_END"""

MOUSEEVENTF_LEFTDOWN: int = 0x0002
MOUSEEVENTF_LEFTUP: int = 0x0004
MOUSEEVENTF_WHEEL: int = 0x0800
WHEEL_DELTA: int = 120
INPUT_KEYBOARD: int = 1
KEYEVENTF_EXTENDEDKEY: int = 0x0001
KEYEVENTF_KEYUP: int = 0x0002
KEYEVENTF_UNICODE: int = 0x0004
KEYEVENTF_UNICODE_KEYUP: int = 0x0006

SIXEL_DEFAULT_PALETTE_SIZE: int = 64
SIXEL_BAND_HEIGHT: int = 6
SIXEL_RLE_MIN_RUN: int = 4
SIXEL_CHAR_OFFSET: int = 63
SIXEL_PERCENT_SCALE: int = 100
SIXEL_RGB_MAX: int = 255
SIXEL_DISTANCE_INITIAL: int = 999999
SIXEL_LORENZ_WIDTH: int = 200
SIXEL_LORENZ_HEIGHT: int = 60
SIXEL_STAGNATION_WIDTH: int = 200
SIXEL_STAGNATION_HEIGHT: int = 40
SIXEL_BACKGROUND_R: int = 10
SIXEL_BACKGROUND_G: int = 10
SIXEL_BACKGROUND_B: int = 20
SIXEL_PALETTE_MIDPOINT: float = 0.5
SIXEL_PALETTE_WARM_G: int = 200
SIXEL_PALETTE_WARM_B: int = 50
SIXEL_PALETTE_COOL_G: int = 100
SIXEL_PALETTE_COOL_B: int = 200
SIXEL_PALETTE_R_ATTENUATION: float = 0.3
SIXEL_TRAIL_INTENSITY_BASE: int = 80
SIXEL_TRAIL_INTENSITY_RANGE: int = 175
SIXEL_TRAIL_COOL_R_RATIO: float = 0.3
SIXEL_TRAIL_COOL_G_RATIO: float = 0.8
SIXEL_TRAIL_WARM_G_RATIO: float = 0.4
SIXEL_TRAIL_WARM_B_RATIO: float = 0.7
SIXEL_CURRENT_R: int = 255
SIXEL_CURRENT_G: int = 255
SIXEL_CURRENT_B: int = 255
STAGNATION_LOW_THRESHOLD: float = 0.3
STAGNATION_MEDIUM_THRESHOLD: float = 0.6
STAGNATION_HALT_LINE: float = 0.95
STAGNATION_LOW_R: int = 50
STAGNATION_LOW_G: int = 200
STAGNATION_LOW_B: int = 80
STAGNATION_MEDIUM_R: int = 220
STAGNATION_MEDIUM_G: int = 180
STAGNATION_MEDIUM_B: int = 30
STAGNATION_HIGH_R: int = 220
STAGNATION_HIGH_G: int = 50
STAGNATION_HIGH_B: int = 50
STAGNATION_HALT_R: int = 100
STAGNATION_HALT_G: int = 30
STAGNATION_HALT_B: int = 30
STAGNATION_REFLECT_R: int = 60
STAGNATION_REFLECT_G: int = 60
STAGNATION_REFLECT_B: int = 100

GUID_DATA1_END: int = 4
GUID_DATA2_END: int = 6
GUID_DATA3_END: int = 8
GUID_DATA4_START: int = 8
GUID_DATA4_END: int = 16
GUID_DATA4_LENGTH: int = 8
RECT_COORDINATE_COUNT: int = 4
INPUT_UNION_PAD_SIZE: int = 32
CLSCTX_INPROC_SERVER: int = 1
IUNKNOWN_RELEASE_INDEX: int = 2
VT_I4: int = 3
VT_BSTR: int = 8
VT_BOOL: int = 11
VT_R8_ARRAY: int = 8197
VARIANT_TRUE_MASK: int = 0xFFFF
DWORD_MASK: int = 0xFFFFFFFF
UIA_BOUNDING_RECTANGLE: int = 30001
UIA_CONTROL_TYPE: int = 30003
UIA_NAME: int = 30005
UIA_IS_ENABLED: int = 30010
UIA_IS_OFFSCREEN: int = 30022
UIA_NATIVE_WINDOW_HANDLE: int = 30020
UIA_LEGACY_IACCESSIBLE_PATTERN: int = 10018
UIA_TEXT_PATTERN: int = 10014
UIA_GET_ROOT_ELEMENT_INDEX: int = 5
UIA_FIND_ALL_INDEX: int = 6
UIA_ELEMENT_FROM_POINT_INDEX: int = 7
UIA_GET_CURRENT_PROPERTY_VALUE_INDEX: int = 10
UIA_GET_CURRENT_PATTERN_AS_INDEX: int = 14
UIA_CREATE_TRUE_CONDITION_INDEX: int = 21
UIA_ELEMENT_ARRAY_LENGTH_INDEX: int = 3
UIA_ELEMENT_ARRAY_GET_INDEX: int = 4
UIA_GET_RUNTIME_ID_INDEX: int = 4
TREE_SCOPE_CHILDREN: int = 0x2
LEGACY_GET_CURRENT_VALUE_INDEX: int = 8
LEGACY_GET_CURRENT_STATE_INDEX: int = 11
TEXT_PATTERN_DOCUMENT_RANGE_INDEX: int = 7
TEXT_RANGE_GET_TEXT_INDEX: int = 12
WIN_CLASS_NAME_BUFFER: int = 256
WIN_WINDOW_TEXT_BUFFER: int = 512
POINT_PACK_SHIFT_BITS: int = 32
UIA_CONTROL_TYPE_MAP: dict[int, str] = {
    50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox",
    50004: "Edit", 50005: "Hyperlink", 50006: "Image", 50007: "ListItem",
    50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
    50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar", 50015: "Slider",
    50016: "Spinner", 50017: "StatusBar", 50018: "Tab", 50019: "TabItem",
    50020: "Text", 50021: "ToolBar", 50022: "ToolTip", 50023: "Tree",
    50024: "TreeItem", 50025: "Custom", 50026: "Group", 50027: "Thumb",
    50028: "DataGrid", 50029: "DataItem", 50030: "Document", 50031: "SplitButton",
    50032: "Window", 50033: "Pane", 50034: "Header", 50035: "HeaderItem",
    50036: "Table", 50037: "TitleBar", 50038: "Separator",
}
VIRTUAL_KEY_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "page_up": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "page_down": 0x22, "pgdn": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "meta": 0x5B, "super": 0x5B, "space": 0x20,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "~": 0xC0,
    "-": 0xBD, "_": 0xBD,
    "=": 0xBB, "+": 0xBB,
    "[": 0xDB, "{": 0xDB,
    "]": 0xDD, "}": 0xDD,
    "\\": 0xDC, "|": 0xDC,
    ";": 0xBA, ":": 0xBA,
    "'": 0xDE, '"': 0xDE,
    ",": 0xBC, "<": 0xBC,
    ".": 0xBE, ">": 0xBE,
    "/": 0xBF, "?": 0xBF,
} | {chr(ord("a") + i): ord("A") + i for i in range(26)} | {chr(ord("0") + i): ord("0") + i for i in range(10)}
EXTENDED_VK_CODES: frozenset[int] = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E})

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
PROBE_STEP_PX: int = 90

MAX_HISTORY_ENTRIES: int = 200
MAX_SIGNATURES: int = 100
MAX_LESSONS: int = 50
MAX_LEDGER_ENTRIES: int = 200
CONTEXT_HISTORY_LIMIT: int = 10
SCREEN_LOCK_STALE_SECONDS: float = 30.0
LORENZ_INITIAL_X: float = 8.485
LORENZ_INITIAL_Y: float = 8.485
LORENZ_INITIAL_Z: float = 27.0
REPETITION_WINDOW: int = 12
REPETITION_MIN_WINDOW: int = 4
STAGNATION_BLOCK_THRESHOLD: float = 0.5
SIGNATURE_BLOCK_EXPIRY_ITERATIONS: int = 5
LORENZ_EQUILIBRIUM_OFFSET: float = 1.0
LORENZ_MAG_EXPONENT: float = 0.5
LORENZ_BETA_MIN: float = 0.5
JACOBIAN_FAILURE_GAIN: float = 0.5
JACOBIAN_FUTURE_STEP_GAIN: float = 0.3
SCREEN_STAGNATION_LOOKBACK: int = 4
SCREEN_HASH_HISTORY_LIMIT: int = 8
HISTORY_REPETITION_LOOKBACK: int = 4
HISTORY_REPETITION_MIN_MATCHES: int = 3

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
LLM_STOP: list[str] = []
LLM_LOGIT_BIAS: dict[str, float] = {}

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
        "recent_history",
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
