from __future__ import annotations
import pathlib

BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent.resolve()
PROMPTS_DIR: pathlib.Path = BASE_DIR / "prompts"
SCHEMAS_DIR: pathlib.Path = BASE_DIR / "schemas"
EVENTS_PATH: pathlib.Path = BASE_DIR / "events.jsonl"
SNAPSHOT_PATH: pathlib.Path = BASE_DIR / "snapshot.json"
LESSONS_PATH: pathlib.Path = BASE_DIR / "lessons.txt"

EVENT_BUDGET: int = 100

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

DELAY_BETWEEN_CYCLES: float = 1.0
DELAY_FOCUS: float = 0.5
DELAY_CURSOR_SETTLE: float = 0.05
DELAY_MOUSE_HOLD: float = 0.05
DELAY_KEY_INTER: float = 0.03
DELAY_CHAR_SEND: float = 0.03
MAX_WAIT_SECONDS: float = 10.0
COMMAND_TIMEOUT_SECONDS: float = 30.0
COMMAND_EXECUTABLE: str = "cmd.exe"
COMMAND_SHELL: str = "/c"

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
LORENZ_DT: float = 0.02
LORENZ_MAG_CAP: float = 80.0
LORENZ_RHO_SENSITIVITY: float = 1.5
LORENZ_BETA_SENSITIVITY: float = 0.3
LORENZ_BETA_MIN: float = 0.5
LORENZ_EQUILIBRIUM_OFFSET: float = 1.0

PID_KP: float = 1.0
PID_KI: float = 0.3
PID_KD: float = 0.8
PID_INTEGRAL_MAX: float = 5.0
PID_DEAD_ZONE: float = 0.05

STAGNATION_WEIGHT_FAILURES: float = 5.0
STAGNATION_WEIGHT_REPETITION: float = 12.0
STAGNATION_WEIGHT_SCREEN: float = 6.0
STAGNATION_NORMALIZER: float = 24.0
STAGNATION_HALT_THRESHOLD: float = 0.95
STAGNATION_HALT_SUSTAINED: int = 5

REFLECT_THRESHOLD: float = 0.3
REFLECT_BUDGET_GATE: float = 0.75
REFLECT_MIN_INTERVAL: int = 4
REFLECT_MIN_FAILURES: int = 2

REPETITION_WINDOW: int = 12
REPETITION_MIN_WINDOW: int = 4
SCREEN_STAGNATION_LOOKBACK: int = 4
SCREEN_HASH_HISTORY_LIMIT: int = 8
MAX_HISTORY: int = 100

PROCESS_DPI_AWARENESS_CONTEXT: int = -4
SIGINT_EXIT_CODE: int = 130

MOUSEEVENTF_LEFTDOWN: int = 0x0002
MOUSEEVENTF_LEFTUP: int = 0x0004
MOUSEEVENTF_WHEEL: int = 0x0800
WHEEL_DELTA: int = 120
INPUT_KEYBOARD: int = 1
KEYEVENTF_EXTENDEDKEY: int = 0x0001
KEYEVENTF_KEYUP: int = 0x0002
KEYEVENTF_UNICODE: int = 0x0004
KEYEVENTF_UNICODE_KEYUP: int = 0x0006
DEFAULT_SCROLL_AMOUNT: int = 3

STD_OUTPUT_HANDLE: int = -11
TUI_ALT_SCREEN_ON: str = "\x1b[?1049h"
TUI_ALT_SCREEN_OFF: str = "\x1b[?1049l"
TUI_HIDE_CURSOR: str = "\x1b[?25l"
TUI_SHOW_CURSOR: str = "\x1b[?25h"
TUI_HOME_CLEAR: str = "\x1b[H\x1b[2J"

VIRTUAL_KEY_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "page_up": 0x21, "pagedown": 0x22, "page_down": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "space": 0x20,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
} | {chr(ord("a") + i): ord("A") + i for i in range(26)} | {chr(ord("0") + i): ord("0") + i for i in range(10)}
EXTENDED_VK_CODES: frozenset[int] = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E})

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

CONTEXT_POLICY: dict[str, list[str]] = {
    "planner": ["goal", "desktop", "screen", "plan", "history", "budget", "diverge", "failures", "lessons", "roles"],
    "actor": ["instruction", "screen", "history", "lessons", "roles"],
    "verifier": ["goal", "desktop", "screen", "history", "plan", "evidence", "roles"],
    "reflector": ["goal", "desktop", "screen", "plan", "history", "math", "roles"],
}

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
