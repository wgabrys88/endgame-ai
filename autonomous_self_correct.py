from __future__ import annotations
import json
import pathlib
from datetime import datetime

from prompt_sections import (
    section_goal, section_actor_history, section_interaction_log,
    section_verified_state, section_current_prompts, section_current_schemas,
    section_lessons, section_run_outcome, assemble_prompt, load_prompt, call_llm,
)
from log import log

BASE_PATH = pathlib.Path(__file__).parent
PROMPTS_DIR = BASE_PATH / "prompts"
BACKUP_DIR = BASE_PATH / "prompt_backups"
LESSONS_PATH = BASE_PATH / "lessons.txt"


def create_detailed_backup(prompt_name: str, old_content: str, new_content: str) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / timestamp
    backup_subdir.mkdir(exist_ok=True)
    (backup_subdir / f"{prompt_name}_OLD.txt").write_text(old_content, encoding="utf-8")
    (backup_subdir / f"{prompt_name}_NEW.txt").write_text(new_content, encoding="utf-8")
    (backup_subdir / "backup_metadata.json").write_text(json.dumps({
        "timestamp": timestamp, "prompt_name": prompt_name,
        "old_length": len(old_content), "new_length": len(new_content),
        "changed": old_content.strip() != new_content.strip(),
    }, indent=2), encoding="utf-8")


def extract_lessons(goal: str, backend: str) -> dict:
    user_prompt = assemble_prompt(
        section_goal(goal), section_actor_history(), section_interaction_log(),
        section_verified_state(), section_current_prompts(), section_current_schemas(),
        section_lessons(), section_run_outcome(),
    )
    try:
        return call_llm(load_prompt("self_reflection_system_prompt.txt"), user_prompt, backend, "reflect")
    except Exception as e:
        log(f"ERROR: LLM call failed: {e}")
        return {"outcome": "error", "lessons": ["LLM call failed"],
                "actor_prompt_rewrite": "", "planner_prompt_rewrite": ""}


def apply_prompt_rewrites(analysis: dict) -> list[str]:
    pending: list[tuple[pathlib.Path, str, str, str]] = []

    for key, filename in [("actor_prompt_rewrite", "actor_system_prompt.txt"),
                          ("planner_prompt_rewrite", "planner_system_prompt.txt")]:
        new_content = analysis.get(key, "").strip()
        if not new_content:
            continue
        target = PROMPTS_DIR / filename
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        if old_content and len(new_content) > len(old_content) * 1.1:
            return []
        pending.append((target, filename, old_content, new_content))

    for key, filename in [("actor_schema_rewrite", "actor_schema.json"),
                          ("planner_schema_rewrite", "planner_schema.json")]:
        new_content = analysis.get(key, "").strip()
        if not new_content:
            continue
        try:
            parsed = json.loads(new_content)
        except json.JSONDecodeError:
            return []
        props = parsed.get("json_schema", {}).get("schema", {}).get("properties", {})
        if "actor" in filename and "actions" not in props:
            return []
        if "planner" in filename and "expand_hwnds" not in props:
            return []
        target = PROMPTS_DIR / filename
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        pending.append((target, filename, old_content, new_content))

    if not pending:
        return []

    changed: list[str] = []
    for target, filename, old_content, new_content in pending:
        create_detailed_backup(filename.replace(".txt", "").replace(".json", ""), old_content, new_content)
        target.write_text(new_content, encoding="utf-8")
        changed.append(filename)
    return changed


def append_lessons(analysis: dict, goal: str) -> None:
    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "goal": goal,
            "outcome": analysis.get("outcome", "unknown"),
            "cycles_used": analysis.get("cycles_used", 0),
            "lessons": analysis.get("lessons", []),
            "patterns_that_worked": analysis.get("patterns_that_worked", []),
            "patterns_that_failed": analysis.get("patterns_that_failed", []),
        }) + "\n")


def run(goal: str, backend: str, apply: bool = False) -> dict:
    analysis = extract_lessons(goal, backend)
    append_lessons(analysis, goal)

    if apply:
        has_proposals = any(analysis.get(k, "").strip() for k in (
            "actor_prompt_rewrite", "planner_prompt_rewrite",
            "actor_schema_rewrite", "planner_schema_rewrite"))
        evolution_ok = False
        if has_proposals:
            changed = apply_prompt_rewrites(analysis)
            evolution_ok = bool(changed)
        else:
            evolution_ok = True

        if evolution_ok:
            archive_path = BASE_PATH / "lessons_archive.txt"
            if LESSONS_PATH.exists() and LESSONS_PATH.read_text(encoding="utf-8").strip():
                archive_path.open("a", encoding="utf-8").write(LESSONS_PATH.read_text(encoding="utf-8"))
                LESSONS_PATH.write_text("", encoding="utf-8")
    return analysis
