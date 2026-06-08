from __future__ import annotations

from config import (
    GOAL_WRAPPER_END,
    GOAL_WRAPPER_HUMAN_END,
    GOAL_WRAPPER_HUMAN_START,
    GOAL_WRAPPER_PREFIX,
    GOAL_WRAPPER_START,
    GOAL_WRAPPER_SUFFIX,
    ONE_INT,
    ZERO_INT,
)


def is_wrapped_goal(goal: str) -> bool:
    text = goal.strip()
    return text.startswith(GOAL_WRAPPER_START) and text.endswith(GOAL_WRAPPER_END)


def wrap_goal(goal: str) -> str:
    cleaned = goal.strip()
    if not cleaned:
        return ""
    if is_wrapped_goal(cleaned):
        return cleaned
    return f"{GOAL_WRAPPER_PREFIX}{cleaned}{GOAL_WRAPPER_SUFFIX}"


def extract_human_goal(goal: str) -> str:
    cleaned = goal.strip()
    if not is_wrapped_goal(cleaned):
        return cleaned
    start = cleaned.find(GOAL_WRAPPER_HUMAN_START)
    end = cleaned.find(GOAL_WRAPPER_HUMAN_END)
    if start < ZERO_INT or end < ZERO_INT or end <= start:
        return cleaned
    start += len(GOAL_WRAPPER_HUMAN_START)
    return cleaned[start:end].strip()


def goal_is_wrapped_once(goal: str) -> bool:
    return goal.count(GOAL_WRAPPER_START) == ONE_INT and goal.count(GOAL_WRAPPER_END) == ONE_INT
