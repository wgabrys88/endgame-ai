"""Drive P0 goals through a clean Slot 1 server with scripted file-proxy cognition."""
from __future__ import annotations

import json
import sys
import time

from harness_common import (
    BASE,
    SCRATCH,
    SLOT_PORT,
    clear_comms,
    ensure_proxy_clear,
    http_json,
    kill_port,
    start_proxy,
    start_slot1_server,
    stop_server,
    wait_health,
    wait_run_idle,
)

GOAL_SCRIPTS = {
    "open notepad and type hello": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Open Notepad", "done_when": "Notepad window is open and focused"},
                    {"description": "Type hello in Notepad", "done_when": "hello text is written in Notepad"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [
                        {"verb": "hotkey", "target": "win+r", "value": ""},
                        {"verb": "write", "target": "", "value": "notepad"},
                        {"verb": "press", "target": "enter", "value": ""},
                    ],
                },
            },
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "write", "target": "", "value": "hello"}],
                },
            },
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
    "navigate to google.com in chrome": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Navigate to google.com in Chrome", "done_when": "google.com page is loaded in Chrome"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "open_url", "target": "chrome", "value": "google.com"}],
                },
            }
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
    "play shakira waka waka on youtube": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Open YouTube and search Shakira Waka Waka", "done_when": "YouTube results for Shakira Waka Waka are visible"},
                    {"description": "Play the Waka Waka video", "done_when": "video is playing on YouTube"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "open_url", "target": "chrome", "value": "youtube.com/results?search_query=Shakira+Waka+Waka"}],
                },
            },
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [
                        {"verb": "wait", "target": "", "value": "2000"},
                        {"verb": "open_url", "target": "chrome", "value": "youtube.com/watch?v=pRpeEdMmmQ0"},
                    ],
                },
            },
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
}


def _history_evidence(state: dict, history: list) -> dict:
    screen = (state.get("screen") or "").lower()
    title = (state.get("post_action_title") or "").lower()
    memory = state.get("memory") or {}
    rules_hit = []
    for entry in history:
        if entry.get("node") == "verify" and entry.get("rule"):
            rules_hit.append(entry.get("rule"))
    return {
        "focus_failed": any(
            "FAILED" in str(h.get("outcome", "")) and "focus" in str(h.get("action", "")).lower()
            for h in history
        ),
        "open_url_ran": any("open_url" in str(h.get("action", "")).lower() for h in history),
        "browser_nav": any(
            "google" in str(h.get("outcome", "")).lower() or "google" in title or "google" in screen
            for h in history
        ) or "confirm_browser" in " ".join(rules_hit),
        "youtube": any(
            "youtube" in screen or "youtube" in title or "waka" in screen
            for _ in [0]
        ) or "confirm_youtube" in " ".join(rules_hit),
        "rules_hit": rules_hit,
        "hello_written": any("hello" in str(h.get("outcome", "")).lower() for h in history),
    }


def run_goal(goal_key: str, run_index: int) -> dict:
    ensure_proxy_clear()
    time.sleep(0.2)

    script = GOAL_SCRIPTS[goal_key]
    responder, thread = start_proxy(script)
    time.sleep(0.35)

    queued = http_json("POST", "/run", {"goal": goal_key})
    state = wait_run_idle(goal_key, timeout_s=360)
    responder.stop()
    thread.join(timeout=2)

    history = state.get("history") or []
    evidence = _history_evidence(state, history)
    payload = {
        "goal": goal_key,
        "run": run_index,
        "port": SLOT_PORT,
        "queued": queued,
        "satisfied": state.get("satisfied"),
        "step": state.get("step"),
        "retries": state.get("retries"),
        "last_outcome": state.get("last_outcome"),
        "last_error": state.get("last_error"),
        "history": history,
        "post_action_title": state.get("post_action_title"),
        "memory": state.get("memory", {}),
        "screen_excerpt": (state.get("screen") or "")[:2500],
        **evidence,
    }
    safe_name = goal_key.replace(" ", "-")
    out = SCRATCH / f"p0-{safe_name}-run{run_index}.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    kill_port(SLOT_PORT)
    clear_comms()
    proc = start_slot1_server()
    try:
        health = wait_health()
        (SCRATCH / "server-health.json").write_text(
            json.dumps({"started": True, "port": SLOT_PORT, "base": BASE, "health": health}, indent=2),
            encoding="utf-8",
        )
        results = []
        for goal in GOAL_SCRIPTS:
            for run in (1, 2):
                results.append(run_goal(goal, run))
                ensure_proxy_clear()
                time.sleep(1.5)
        (SCRATCH / "p0-summary.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"port": SLOT_PORT, "health_ok": health.get("ok"), "runs": len(results)}, indent=2))
    finally:
        stop_server(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())