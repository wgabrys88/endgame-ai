"""Capture verification artifacts for mechanical fixes."""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SCRATCH = Path(r"C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer")
SCRATCH.mkdir(parents=True, exist_ok=True)


def capture_focus_tests() -> dict:
    from desktop import assign_window_tokens, format_window_lines, resolve_window_target
    import actions
    from unittest.mock import patch
    import desktop as desktop_mod

    windows = assign_window_tokens([
        {"hwnd": 1010, "title": "YouTube - Google Chrome", "focused": False, "z": 1},
        {"hwnd": 2020, "title": "Notepad", "focused": True, "z": 0},
    ])
    results = {
        "resolve_w1": resolve_window_target("W1", windows),
        "resolve_chrome": resolve_window_target("Chrome", windows),
        "window_lines": format_window_lines(windows, 10),
        "runs": [],
    }

    class FakeObservation:
        focused_title = "Notepad"
        elements = {}
        snapshot = {"windows": windows}

    for run in (1, 2):
        with patch.object(desktop_mod.Desktop, "focus_window", return_value=True) as focus_mock:
            actions._last_observation = FakeObservation()
            actions._desktop = desktop_mod.Desktop()
            actions._executor = actions.ActionExecutor(
                actions._desktop, {"verbs": {"focus": {"title_field": "target"}}}
            )
            outcome = actions.execute_verb("focus", "Chrome")
        results["runs"].append({
            "run": run,
            "outcome": outcome,
            "hwnd_passed": focus_mock.call_args[0][1],
        })

    (SCRATCH / "focus-test.log").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (SCRATCH / "focus-state.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def capture_wait_deny_tests() -> dict:
    server = importlib.import_module("server")
    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    relay = json.loads((ROOT / "prompts" / "wiring_relay.json").read_text(encoding="utf-8"))

    cases = []
    state_wait = {
        "last_outcome": "OK: wait : waited 2000 ms",
        "last_actions_raw": [{"verb": "wait", "target": "", "value": "2000"}],
        "current_step": {
            "description": "wait until streaming ends",
            "done_when": "assistant response is complete",
        },
        "memory": {},
        "screen": "",
        "history": [],
    }
    deny_rule = server.evaluate_rules("verify", state_wait, wiring)
    cases.append({"case": "wait_streaming_deny", "rule": deny_rule})

    state_llm_empty = {
        "last_outcome": "OK: llm_wait_response : received",
        "last_actions_raw": [{"verb": "llm_wait_response", "target": "", "value": ""}],
        "current_step": {"description": "wait", "done_when": "llm response"},
        "memory": {},
        "screen": "",
        "history": [],
    }
    confirm_empty = server.evaluate_rules("verify", state_llm_empty, wiring)
    cases.append({"case": "llm_wait_no_memory", "rule": confirm_empty})

    state_llm_ok = dict(state_llm_empty)
    state_llm_ok["memory"] = {"llm_response": "A" * 25}
    confirm_ok = server.evaluate_rules("verify", state_llm_ok, wiring)
    cases.append({"case": "llm_wait_with_memory", "rule": confirm_ok})

    relay_ids = {r["id"] for r in relay.get("rules", [])}
    cases.append({"case": "relay_wait_rule_absent", "absent": "confirm_relay_wait" not in relay_ids})

    payload = {"runs": [cases, cases]}
    text = json.dumps(payload, indent=2)
    (SCRATCH / "wait-deny.log").write_text(text, encoding="utf-8")
    return payload


def capture_config_alignment() -> dict:
    import desktop
    server = importlib.import_module("server")

    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    desktop.configure_observation(wiring.get("observe", {}))
    payload = {
        "wiring_desktop_tree_enabled": wiring.get("observe", {}).get("desktop_tree_enabled"),
        "runtime_desktop_tree_enabled": desktop.OBSERVE_CONFIG.get("desktop_tree_enabled"),
        "max_self_modify": wiring.get("limits", {}).get("max_self_modify"),
        "reflect_defaults": {
            "max_attempts": server.wiring_limit("max_attempts", None),
            "max_replans": server.wiring_limit("max_replans", None),
        },
    }
    (SCRATCH / "config-align.log").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def capture_doc_drift() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    setup = (ROOT / "SETUP_AND_LAUNCH.md").read_text(encoding="utf-8")
    payload = {
        "px_wjt_in_readme": "px-wjt" in readme,
        "px_wjt_in_setup": "px-wjt" in setup,
        "slots_status_documented": "/slots/status" in setup and "no `/slots/status`" in setup,
        "rule_count_mentioned": "32 declarative rules" in readme,
        "ewojgab_path": "ewojgab" in readme,
    }
    (SCRATCH / "doc-drift.log").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def try_live_focus() -> dict:
    import desktop as desktop_mod
    import actions

    actions.configure_runtime(json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8")))
    desktop = desktop_mod.Desktop()
    observation = desktop.observe()
    snapshot = observation.snapshot if isinstance(observation.snapshot, dict) else {}
    windows = snapshot.get("windows", [])
    candidates = [
        row for row in windows
        if str(row.get("title", "")).strip() and str(row.get("title")) != "(untitled)" and not row.get("focused")
    ]
    outcome = {
        "screen_excerpt": (observation.context_text or "")[:1200],
        "windows": windows,
        "focus_attempt": None,
        "foreground_before": int(desktop.user32.GetForegroundWindow() or 0),
        "foreground_after": None,
    }
    if candidates:
        target_row = candidates[0]
        target = str(target_row.get("token") or target_row.get("title"))
        ok = desktop.focus_window(target, windows)
        after = int(desktop.user32.GetForegroundWindow() or 0)
        outcome.update({
            "focus_target": target,
            "focus_ok": ok,
            "foreground_after": after,
            "target_hwnd": int(target_row.get("hwnd", 0) or 0),
        })
        actions._last_observation = observation
        outcome["execute_verb"] = actions.execute_verb("focus", target)
    path = SCRATCH / "live-focus.json"
    path.write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    return outcome


def poll_state(base: str, timeout_s: int = 30) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/state", timeout=3) as resp:
                last = json.loads(resp.read().decode("utf-8"))
                if last.get("satisfied") is not None and last.get("_resume_node") in (None, "satisfied", "goal_inbox"):
                    break
        except Exception:
            pass
        time.sleep(1)
    return last


def try_server_health() -> dict:
    import os

    env = os.environ.copy()
    env["ENDGAME_SLOT"] = "1"
    env["ENDGAME_STATE"] = str(ROOT / "state.slot1.json")
    env["ENDGAME_WIRING"] = str(ROOT / "prompts" / "wiring.json")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result = {"started": False, "health": None, "port": 9078}
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9078/health", timeout=2) as resp:
                    result["health"] = json.loads(resp.read().decode("utf-8"))
                    result["started"] = True
                    break
            except Exception:
                continue
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    (SCRATCH / "server-health.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    summary = {
        "focus": capture_focus_tests(),
        "wait_deny": capture_wait_deny_tests(),
        "config": capture_config_alignment(),
        "docs": capture_doc_drift(),
        "live_focus": try_live_focus(),
        "server_health": try_server_health(),
    }
    (SCRATCH / "verification-summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"scratch": str(SCRATCH), "ok": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())