from __future__ import annotations
import json
import pathlib

from llm import call_backend
from log import log

BASE_PATH = pathlib.Path(__file__).parent
INTERACTION_LOG_PATH = BASE_PATH / "interaction_log.jsonl"
ACTOR_HISTORY_PATH = BASE_PATH / "actor_history.jsonl"
VERIFIED_STATE_PATH = BASE_PATH / "verified_state.txt"
LESSONS_PATH = BASE_PATH / "lessons.txt"
PROMPTS_DIR = BASE_PATH / "prompts"


def _read_stripped(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def call_llm(system: str, user: str, backend: str, role: str) -> dict:
    raw = call_backend(system, user, backend, role)
    log(f"[{role.upper()} RAW RESPONSE]\n{raw}")
    start = raw.find("{")
    end = raw.rfind("}")
    assert start != -1 and end != -1, f"Could not parse {role} response as JSON"
    return json.loads(raw[start:end + 1])


def section_goal(goal: str) -> str:
    return f"GOAL: {goal}"


def section_screen(context_text: str) -> str:
    return f"SCREEN:\n{context_text}"


def section_actor_history() -> str:
    text = _read_stripped(ACTOR_HISTORY_PATH)
    return f"ACTOR HISTORY:\n{text}" if text else ""


def section_verified_state() -> str:
    text = _read_stripped(VERIFIED_STATE_PATH)
    return f"VERIFIED ELEMENT STATE:\n{text}" if text else ""


def section_interaction_log() -> str:
    text = _read_stripped(INTERACTION_LOG_PATH)
    return f"INTERACTION LOG:\n{text}" if text else ""


def section_available_windows(raw_lines: list[str]) -> str:
    lines = [
        f"  hwnd={obj['hwnd']} title=\"{obj['title']}\""
        for line in raw_lines
        if (obj := json.loads(line)) and "hwnd" in obj
        and obj.get("depth") == 0 and obj.get("visible") and obj.get("title")
    ]
    return f"AVAILABLE WINDOWS:\n" + "\n".join(lines) if lines else ""


def section_progress(planner_output: dict) -> str:
    return f"PROGRESS: {planner_output['done_so_far']}"


def section_next_step(planner_output: dict) -> str:
    return f"NEXT STEP: {planner_output['next_step']}"


def section_current_prompts() -> str:
    parts: list[str] = []
    for name, label in [("actor_system_prompt.txt", "ACTOR"), ("planner_system_prompt.txt", "PLANNER")]:
        path = PROMPTS_DIR / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            parts.append(f"CURRENT {label} PROMPT ({len(text)} chars — rewrite must not exceed this):\n{text.strip()}")
    return "\n\n".join(parts)


def section_current_schemas() -> str:
    parts = [
        f"CURRENT {name.upper().replace('.JSON', '')}:\n{(PROMPTS_DIR / name).read_text(encoding='utf-8').strip()}"
        for name in ("actor_schema.json", "planner_schema.json")
        if (PROMPTS_DIR / name).exists()
    ]
    return "\n\n".join(parts)


def section_lessons() -> str:
    text = _read_stripped(LESSONS_PATH)
    return f"LESSONS FROM ALL PREVIOUS RUNS (use to inform rewrite priorities):\n{text}" if text else ""


def section_run_outcome() -> str:
    text = _read_stripped(ACTOR_HISTORY_PATH)
    if not text:
        return ""
    last = json.loads(text.splitlines()[-1])
    actions = last.get("actions") or [last.get("action", "")]
    if "done" in actions:
        return "RUN OUTCOME: Actor declared DONE (goal achieved)."
    if last.get("validation_error"):
        return f"RUN OUTCOME: Last action had validation error: {last['validation_error']}"
    return "RUN OUTCOME: Max cycles reached without completing goal."


def assemble_prompt(*sections: str) -> str:
    return "\n\n".join(s for s in sections if s)
