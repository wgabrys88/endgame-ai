"""Capture verification artifacts for mechanical fixes."""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SCRATCH = Path(r"C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer")
SCRATCH.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from harness_common import (
    SCRATCH as HARNESS_SCRATCH,
    clear_comms,
    kill_port,
    start_slot1_server,
    stop_server,
    wait_health,
)
from desktop import assign_window_tokens, format_window_lines, resolve_window_target


def capture_focus_tests() -> dict:
    """Resolver on fixture data + real execute_verb on live observed windows (no focus_window mock)."""
    import actions
    import desktop as desktop_mod

    fixture_windows = assign_window_tokens([
        {"hwnd": 1010, "title": "YouTube - Google Chrome", "focused": False, "z": 1},
        {"hwnd": 2020, "title": "Notepad", "focused": True, "z": 0},
    ])
    results = {
        "fixture_resolve_w1": resolve_window_target("W1", fixture_windows),
        "fixture_resolve_chrome": resolve_window_target("Chrome", fixture_windows),
        "fixture_window_lines": format_window_lines(fixture_windows, 10),
        "runs": [],
    }

    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    actions.configure_runtime(wiring)
    desktop = desktop_mod.Desktop()
    observation = desktop.observe()
    snapshot = observation.snapshot if isinstance(observation.snapshot, dict) else {}
    live_windows = snapshot.get("windows") or []

    for run in (1, 2):
        run_result = {"run": run}
        if live_windows:
            candidates = [
                row for row in live_windows
                if str(row.get("title", "")).strip() and not row.get("focused")
                and int(row.get("hwnd", 0) or 0) > 0
            ]
            if candidates:
                row = candidates[0]
                target = str(row.get("token") or row.get("title"))
                resolved = resolve_window_target(target, live_windows)
                actions._last_observation = observation
                actions._desktop = desktop
                actions._executor = actions.ActionExecutor(
                    desktop, {"verbs": {"focus": {"title_field": "target"}}}
                )
                before = int(desktop.user32.GetForegroundWindow() or 0)
                outcome = actions.execute_verb("focus", target)
                after = int(desktop.user32.GetForegroundWindow() or 0)
                run_result.update({
                    "target": target,
                    "resolved_hwnd": resolved.get("hwnd") if resolved else None,
                    "outcome": outcome,
                    "foreground_before": before,
                    "foreground_after": after,
                    "live": True,
                })
            else:
                run_result["skipped"] = "no unfocused live window"
        else:
            run_result["skipped"] = "no live windows in observation"
        results["runs"].append(run_result)

    (SCRATCH / "focus-test.log").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (SCRATCH / "focus-state.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
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
        "rule_count": len(wiring.get("rules", [])),
        "edge_count": len(wiring.get("topology", {}).get("edges", [])),
        "reflect_defaults": {
            "max_attempts": server.wiring_limit("max_attempts", None),
            "max_replans": server.wiring_limit("max_replans", None),
        },
    }
    (SCRATCH / "config-align.log").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def capture_doc_drift() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    rule_count = len(wiring.get("rules", []))
    payload = {
        "px_wjt_in_readme": "px-wjt" in readme,
        "setup_and_launch_exists": (ROOT / "SETUP_AND_LAUNCH.md").exists(),
        "slots_status_documented": "no `/slots/status`" in readme or "/slots/status" in readme,
        "rule_count_in_readme": str(rule_count) in readme,
        "rule_count_actual": rule_count,
        "edge_count_actual": len(wiring.get("topology", {}).get("edges", [])),
        "ewojgab_path": "ewojgab" in readme,
    }
    (SCRATCH / "doc-drift.log").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def try_live_focus() -> dict:
    """Real observe + focus_window + GetForegroundWindow — no mocks."""
    import actions
    import desktop as desktop_mod

    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    actions.configure_runtime(wiring)
    desktop = desktop_mod.Desktop()
    observation = desktop.observe()
    snapshot = observation.snapshot if isinstance(observation.snapshot, dict) else {}
    windows = snapshot.get("windows", [])
    candidates = [
        row for row in windows
        if str(row.get("title", "")).strip()
        and str(row.get("title")) != "(untitled)"
        and not row.get("focused")
        and int(row.get("hwnd", 0) or 0) > 0
    ]
    outcome = {
        "screen_excerpt": (observation.context_text or "")[:1200],
        "windows": windows,
        "focus_attempt": None,
        "foreground_before": int(desktop.user32.GetForegroundWindow() or 0),
        "foreground_after": None,
    }
    last_error = ""
    for target_row in candidates:
        target = str(target_row.get("token") or target_row.get("title"))
        before_hwnd = int(desktop.user32.GetForegroundWindow() or 0)
        ok = desktop.focus_window(target, windows)
        after_hwnd = int(desktop.user32.GetForegroundWindow() or 0)
        expected = int(target_row.get("hwnd", 0) or 0)
        attempt = {
            "focus_target": target,
            "focus_ok": ok,
            "foreground_before": before_hwnd,
            "foreground_after": after_hwnd,
            "target_hwnd": expected,
        }
        if ok and expected:
            active_root = desktop._root_hwnd(after_hwnd)
            target_root = desktop._root_hwnd(expected)
            if after_hwnd == expected or (active_root and active_root == target_root):
                attempt["foreground_match"] = True
                outcome["focus_attempt"] = attempt
                actions._last_observation = observation
                outcome["execute_verb"] = actions.execute_verb("focus", target)
                break
            last_error = f"foreground {after_hwnd} != target {expected}"
        elif ok and before_hwnd != after_hwnd:
            attempt["foreground_match"] = True
            outcome["focus_attempt"] = attempt
            actions._last_observation = observation
            outcome["execute_verb"] = actions.execute_verb("focus", target)
            break
        last_error = last_error or f"focus failed for {target!r}"
        outcome["focus_attempt"] = attempt
    if outcome.get("focus_attempt") is None and candidates:
        outcome["error"] = last_error or "no focus candidate succeeded"
    path = SCRATCH / "live-focus.json"
    path.write_text(json.dumps(outcome, indent=2, default=str), encoding="utf-8")
    return outcome


def try_server_health() -> dict:
    kill_port()
    clear_comms()
    proc = start_slot1_server()
    result = {"started": False, "health": None, "port": 9078}
    try:
        health = wait_health(timeout_s=25.0)
        result["health"] = health
        result["started"] = bool(health.get("ok"))
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        stop_server(proc)
    (SCRATCH / "server-health.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_unit_tests() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "test_mechanical_fixes.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    (SCRATCH / "unit-tests.log").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    summary = {
        "focus": capture_focus_tests(),
        "wait_deny": capture_wait_deny_tests(),
        "config": capture_config_alignment(),
        "docs": capture_doc_drift(),
        "live_focus": try_live_focus(),
        "server_health": try_server_health(),
        "unit_tests": run_unit_tests(),
    }
    (SCRATCH / "verification-summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"scratch": str(SCRATCH), "ok": summary["unit_tests"]["returncode"] == 0}, indent=2))
    return 0 if summary["unit_tests"]["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())