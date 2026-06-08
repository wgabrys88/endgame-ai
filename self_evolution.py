from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from config import (
    CHECKLIST_REWRITE_MIN_STEPS,
    MUTABLE_PROMPT_END,
    MUTABLE_PROMPT_START,
    ONE_INT,
    PROMPT_MUTATION_ISSUE_TOKEN_LIMIT,
    PROMPT_MUTATION_ISSUE_TOKEN_MIN_LENGTH,
    PROMPT_MUTATION_LESSON_THRESHOLD,
    PROMPT_MUTATION_LINE_MAX_CHARS,
    PROMPTS_DIR,
    TIER3_PATTERN_LESSON_THRESHOLD,
    TIER3_PROMPT_MUTATION_THRESHOLD,
    ZERO_INT,
)
from lessons import Lessons
from log import log


PROMPT_MUTATION_ROLES: tuple[str, ...] = ("actor", "planner", "verifier", "reflector")

_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "actor": (
        "action", "actions", "actor", "click", "focus", "hotkey", "press",
        "screen", "selector", "type", "verb", "wait", "write",
    ),
    "planner": (
        "advance", "checklist", "child", "decompose", "goal", "parallel",
        "plan", "planner", "sequence", "step",
    ),
    "verifier": (
        "complete", "confirm", "done", "evidence", "failure_type", "verify",
        "verdict", "verifier",
    ),
    "reflector": (
        "diagnosis", "lesson", "reflect", "reflection", "reflector", "stuck",
        "wasteful",
    ),
}

_ISSUE_STOPWORDS: frozenset[str] = frozenset({
    "about", "after", "again", "before", "from", "into", "must", "only",
    "over", "same", "than", "that", "the", "then", "this", "when", "with",
})


@dataclass(frozen=True, slots=True)
class PromptMutationResult:
    applied: bool
    role: str
    reason: str
    old_line: str = ""
    new_line: str = ""


def process_reflection_result(board: Any, result: dict[str, Any], *, prompt_mutations_enabled: bool) -> dict[str, Any]:
    lesson = _reflection_lesson(result)
    diagnosis = str(result.get("diagnosis", "")).strip()
    store = Lessons()
    role = classify_lesson_role(lesson)
    issue_key = issue_key_for_lesson(lesson, role)
    entry = store.add_lesson(
        lesson,
        role=role,
        issue_key=issue_key,
        diagnosis=diagnosis,
        source_iteration=board.iteration,
    )
    if entry:
        store.save()
        log(board.iteration, "reflection.lesson", "stored lesson", {"entry": entry})

    _apply_checklist_rewrite(board, result)

    prompt_result: PromptMutationResult | None = None
    if prompt_mutations_enabled:
        prompt_result = maybe_apply_prompt_mutation(store, role, board.iteration)
    else:
        log(board.iteration, "prompt.mutation.skip", "prompt mutations disabled")

    tier3_switched = maybe_switch_to_code_evolution_goal(board, store)
    store.save()
    return {
        "lesson_added": entry is not None,
        "lesson_role": role,
        "issue_key": issue_key,
        "prompt_mutation": prompt_result,
        "tier3_switched": tier3_switched,
    }


def classify_lesson_role(lesson: str) -> str:
    lower = lesson.lower()
    scores = {
        role: sum(ONE_INT for keyword in keywords if keyword in lower)
        for role, keywords in _ROLE_KEYWORDS.items()
    }
    best_role = max(PROMPT_MUTATION_ROLES, key=lambda role: scores.get(role, ZERO_INT))
    if scores.get(best_role, ZERO_INT) <= ZERO_INT:
        return "planner"
    return best_role


def issue_key_for_lesson(lesson: str, role: str) -> str:
    tokens = [
        token for token in re.findall(r"[a-z0-9_]+", lesson.lower())
        if token not in _ISSUE_STOPWORDS and len(token) > PROMPT_MUTATION_ISSUE_TOKEN_MIN_LENGTH
    ]
    if not tokens:
        return role
    selected: list[str] = []
    for token in tokens:
        if token not in selected:
            selected.append(token)
        if len(selected) >= PROMPT_MUTATION_ISSUE_TOKEN_LIMIT:
            break
    return f"{role}:{'-'.join(selected)}"


def maybe_apply_prompt_mutation(store: Lessons, role: str, iteration: int) -> PromptMutationResult:
    if role not in PROMPT_MUTATION_ROLES:
        result = PromptMutationResult(False, role, "role_not_mutable")
        log(iteration, "prompt.mutation.skip", "role not mutable", result)
        return result
    entries = store.unapplied_prompt_entries(role)
    if len(entries) < PROMPT_MUTATION_LESSON_THRESHOLD:
        result = PromptMutationResult(False, role, "lesson_threshold_not_met")
        log(iteration, "prompt.mutation.skip", "lesson threshold not met", {"role": role, "count": len(entries), "threshold": PROMPT_MUTATION_LESSON_THRESHOLD})
        return result

    batch = entries[-PROMPT_MUTATION_LESSON_THRESHOLD:]
    selected = batch[-ONE_INT]
    lesson = str(selected.get("lesson", ""))
    new_line = lesson_to_prompt_line(lesson)
    result = apply_prompt_line_mutation(role, new_line)
    log(iteration, "prompt.mutation.result", result.reason, result)
    if result.applied or result.reason == "unchanged":
        mutation_id = str(selected.get("id", ""))
        lesson_ids: list[str] = [str(item.get("id", "")) for item in batch]
        mutation: dict[str, Any] = {
            "id": mutation_id,
            "role": role,
            "issue_key": str(selected.get("issue_key", "")),
            "lesson_ids": lesson_ids,
            "old_line": result.old_line,
            "new_line": result.new_line,
        }
        store.mark_prompt_applied(lesson_ids, mutation)
    return result


def apply_prompt_line_mutation(role: str, new_line: str) -> PromptMutationResult:
    path = PROMPTS_DIR / f"{role}.txt"
    if not path.exists():
        return PromptMutationResult(False, role, "prompt_missing")
    original = path.read_text(encoding="utf-8")
    updated, result = mutate_prompt_text(role, original, new_line)
    if result.applied:
        path.write_text(updated, encoding="utf-8")
    return result


def mutate_prompt_text(role: str, original: str, new_line: str) -> tuple[str, PromptMutationResult]:
    lines = original.splitlines()
    if not lines:
        return original, PromptMutationResult(False, role, "empty_prompt")
    first_line = lines[ZERO_INT]
    try:
        start = lines.index(MUTABLE_PROMPT_START)
        end = lines.index(MUTABLE_PROMPT_END)
    except ValueError:
        return original, PromptMutationResult(False, role, "mutable_markers_missing")
    if end <= start + ONE_INT:
        return original, PromptMutationResult(False, role, "mutable_block_empty")
    if lines[ZERO_INT] != first_line:
        return original, PromptMutationResult(False, role, "immutable_first_line_changed")

    target = start + ONE_INT
    old_line = lines[target]
    sanitized = _sanitize_prompt_line(new_line)
    if old_line == sanitized:
        return original, PromptMutationResult(False, role, "unchanged", old_line, sanitized)
    updated_lines = list(lines)
    updated_lines[target] = sanitized
    if updated_lines[ZERO_INT] != first_line:
        return original, PromptMutationResult(False, role, "immutable_first_line_changed", old_line, sanitized)
    mutable_changes = sum(
        ONE_INT
        for old, new in zip(lines[start + ONE_INT:end], updated_lines[start + ONE_INT:end])
        if old != new
    )
    if mutable_changes != ONE_INT:
        return original, PromptMutationResult(False, role, "mutation_not_single_line", old_line, sanitized)
    newline = "\n" if original.endswith("\n") else ""
    return "\n".join(updated_lines) + newline, PromptMutationResult(True, role, "applied", old_line, sanitized)


def lesson_to_prompt_line(lesson: str) -> str:
    cleaned = " ".join(lesson.strip().split())
    if not cleaned:
        cleaned = "Prefer evidence-backed recovery over repeating a failed action."
    if cleaned[-ONE_INT] not in ".!?":
        cleaned += "."
    prefix = "- Learned: "
    limit = PROMPT_MUTATION_LINE_MAX_CHARS - len(prefix)
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip(" .,;:") + "."
    return prefix + cleaned


def maybe_switch_to_code_evolution_goal(board: Any, store: Lessons) -> bool:
    if board.agent_id != "main":
        return False
    if "TIER3 CODE EVOLUTION" in board.goal.upper():
        return False
    counts = store.issue_counts()
    if not counts:
        return False
    issue_key, lesson_count = max(counts.items(), key=lambda item: item[ONE_INT])
    if lesson_count < TIER3_PATTERN_LESSON_THRESHOLD:
        return False
    if store.prompt_mutation_count(issue_key) < TIER3_PROMPT_MUTATION_THRESHOLD:
        return False
    if store.tier3_already_triggered(issue_key):
        return False

    goal = _code_evolution_goal(issue_key, lesson_count)
    board.rewrite_goal(goal)
    board.mode = "direct"
    board.plan_steps = _code_evolution_plan_steps()
    board.plan_step_index = ZERO_INT
    board.notes = [f"Tier3 escalation issue={issue_key} lessons={lesson_count}"]
    board.reset_pid_integral()
    store.mark_tier3_triggered(issue_key, goal)
    log(board.iteration, "tier3.switch", "switched goal to code evolution", {"issue_key": issue_key, "lesson_count": lesson_count, "goal": goal, "steps": board.plan_steps})
    return True


def _apply_checklist_rewrite(board: Any, result: dict[str, Any]) -> None:
    checklist_rewrite = result.get("checklist_rewrite", [])
    if not isinstance(checklist_rewrite, list):
        return
    raw_steps = cast(list[Any], checklist_rewrite)
    steps = [str(item).strip() for item in raw_steps if str(item).strip()]
    if len(steps) >= CHECKLIST_REWRITE_MIN_STEPS:
        board.plan_steps = steps
        board.plan_step_index = ZERO_INT
        log(board.iteration, "checklist.rewrite", "reflector replaced remaining checklist", {"steps": steps})


def _reflection_lesson(result: dict[str, Any]) -> str:
    lesson = str(result.get("lesson", "")).strip()
    if lesson:
        return lesson
    return str(result.get("lesson_1", "")).strip()


def _sanitize_prompt_line(line: str) -> str:
    single_line = " ".join(line.strip().split())
    if not single_line.startswith("- "):
        single_line = "- " + single_line
    if len(single_line) > PROMPT_MUTATION_LINE_MAX_CHARS:
        single_line = single_line[:PROMPT_MUTATION_LINE_MAX_CHARS].rstrip(" .,;:") + "."
    return single_line


def _code_evolution_goal(issue_key: str, lesson_count: int) -> str:
    return (
        "TIER3 CODE EVOLUTION: repeated reflection lessons show "
        f"{issue_key} across {lesson_count} lessons and prior prompt mutations were not enough. "
        "First inspect the lessons store and role prompts. Only after that decide whether reading "
        "source code and patching is worth the time. If code change is justified, patch the "
        "smallest reflection-pipeline source area and validate by spawning a subagent goal that "
        "tests lessons extraction, default-disabled prompt mutation, and guarded enabled mutation."
    )


def _code_evolution_plan_steps() -> list[str]:
    return [
        "Use read_file path=lessons.json to inspect accumulated lessons before any source-code read",
        "Use read_file path=prompts/actor.txt to inspect the actor prompt before any source-code read",
        "Use read_file path=prompts/planner.txt to inspect the planner prompt before any source-code read",
        "Use read_file path=prompts/verifier.txt to inspect the verifier prompt before any source-code read",
        "Use read_file path=prompts/reflector.txt to inspect the reflector prompt before any source-code read",
        "Decide whether the repeated lesson pattern still justifies source-code changes after lesson and prompt review",
        "If source-code changes are justified, read the smallest source files needed for the reflection pipeline",
        "Patch the smallest relevant source area and preserve existing behavior outside reflection evolution",
        "Validate the change by spawning a subagent with a focused reflection-pipeline test goal",
    ]
