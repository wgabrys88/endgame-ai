"""Regression tests for focus resolution and wait-deny rule evaluation."""
from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from desktop import assign_window_tokens, format_window_lines, resolve_window_target


class FocusResolverTests(unittest.TestCase):
    WINDOWS = assign_window_tokens([
        {"hwnd": 1010, "title": "YouTube - Google Chrome", "focused": False, "z": 1},
        {"hwnd": 2020, "title": "Notepad", "focused": True, "z": 0},
    ])

    def test_token_resolve_prefers_observed_hwnd(self):
        resolved = resolve_window_target("W1", self.WINDOWS)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved["hwnd"], 1010)
        self.assertEqual(resolved["title"], "YouTube - Google Chrome")

    def test_title_substring_resolves_chrome_window(self):
        resolved = resolve_window_target("Chrome", self.WINDOWS)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved["hwnd"], 1010)

    def test_format_window_lines_includes_tokens(self):
        lines = format_window_lines(self.WINDOWS, 10)
        self.assertTrue(any("[W1] YouTube - Google Chrome" in line for line in lines))

    def test_focus_execute_uses_observed_handle(self):
        import actions

        importlib.reload(actions)
        desktop_mod = importlib.import_module("desktop")
        obs_windows = self.WINDOWS

        class FakeObservation:
            focused_title = "Notepad"
            elements = {}
            snapshot = {"windows": obs_windows}

        with patch.object(desktop_mod.Desktop, "focus_window", return_value=True) as focus_mock:
            actions._last_observation = FakeObservation()
            actions._desktop = desktop_mod.Desktop()
            actions._executor = actions.ActionExecutor(actions._desktop, {"verbs": {"focus": {"title_field": "target"}}})
            outcome = actions.execute_verb("focus", "Chrome")
        self.assertNotIn("FAILED", outcome)
        focus_mock.assert_called_once()
        self.assertEqual(focus_mock.call_args[0][0], "Chrome")
        self.assertEqual(focus_mock.call_args[0][1], obs_windows)

    def test_real_focus_changes_foreground_via_observed_hwnd(self):
        """Uses shipped focus_window + observed snapshot — no mock on focus path."""
        import subprocess
        import time

        import desktop as desktop_mod

        subprocess.Popen(["notepad.exe"])
        time.sleep(1.2)

        desktop = desktop_mod.Desktop()
        observation = desktop.observe()
        snapshot = observation.snapshot if isinstance(observation.snapshot, dict) else {}
        windows = snapshot.get("windows") or []
        notepad_rows = [
            row for row in windows
            if "notepad" in str(row.get("title", "")).lower()
            and int(row.get("hwnd", 0) or 0) > 0
        ]
        if not notepad_rows:
            self.skipTest("notepad window not observed after launch")

        last_error = ""
        for target_row in notepad_rows:
            target = str(target_row.get("token") or target_row.get("title"))
            before_hwnd = int(desktop.user32.GetForegroundWindow() or 0)
            ok = desktop.focus_window(target, windows)
            after_hwnd = int(desktop.user32.GetForegroundWindow() or 0)
            if not ok:
                last_error = f"focus_window returned False for {target!r}"
                continue
            expected = int(target_row.get("hwnd", 0) or 0)
            active_root = desktop._root_hwnd(after_hwnd)
            target_root = desktop._root_hwnd(expected)
            matched = (
                after_hwnd == expected
                or (active_root and target_root and active_root == target_root)
                or "notepad" in desktop._get_window_title(after_hwnd).lower()
            )
            if matched:
                return
            last_error = f"foreground {after_hwnd} did not match notepad {expected} (was {before_hwnd})"

        self.fail(last_error or "no notepad window could be focused to foreground")


class WaitDenyRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = importlib.import_module("server")
        cls.wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
        cls.relay_wiring = json.loads((ROOT / "prompts" / "wiring_relay.json").read_text(encoding="utf-8"))

    def _verify(self, state: dict, wiring: dict | None = None):
        return self.server.evaluate_rules("verify", state, wiring or self.wiring)

    def test_deny_wait_only_streaming_step(self):
        state = {
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
        rule = self._verify(state)
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule["verdict"], "deny")
        self.assertIn(rule["id"], {"deny_response_no_evidence", "deny_wait_only_content_receipt"})

    def test_no_confirm_for_pure_wait(self):
        state = {
            "last_outcome": "OK: wait : waited 1000 ms",
            "last_actions_raw": [{"verb": "wait", "target": "", "value": "1000"}],
            "current_step": {
                "description": "wait until streaming ends",
                "done_when": "response received",
            },
            "memory": {},
            "screen": "",
            "history": [],
        }
        rule = self._verify(state)
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertNotEqual(rule["verdict"], "confirm")

    def test_relay_has_no_confirm_relay_wait(self):
        ids = {rule["id"] for rule in self.relay_wiring.get("rules", [])}
        self.assertNotIn("confirm_relay_wait", ids)

    def test_llm_response_confirm_requires_memory(self):
        state = {
            "last_outcome": "OK: llm_wait_response : received",
            "last_actions_raw": [{"verb": "llm_wait_response", "target": "", "value": ""}],
            "current_step": {"description": "wait for relay", "done_when": "llm response in memory"},
            "memory": {},
            "screen": "",
            "history": [],
        }
        rule = self._verify(state)
        if rule and rule.get("id") == "confirm_llm_response_received":
            self.fail("confirm_llm_response_received fired without memory evidence")

    def test_llm_response_confirm_with_memory(self):
        state = {
            "last_outcome": "OK: llm_wait_response : received",
            "last_actions_raw": [{"verb": "llm_wait_response", "target": "", "value": ""}],
            "current_step": {"description": "wait for relay", "done_when": "llm response in memory"},
            "memory": {"llm_response": "A" * 25},
            "screen": "",
            "history": [],
        }
        rule = self._verify(state)
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule["id"], "confirm_llm_response_received")


if __name__ == "__main__":
    unittest.main()