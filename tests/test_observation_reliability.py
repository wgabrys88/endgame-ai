"""Regression tests for observation-reliability fixes (INC-1 parenting, INC-2 short_id
churn resolution, INC-3 silent per-window truncation flag).

These tests are platform-independent: they exercise the pure tree-building and bus logic
with synthetic payloads shaped like the real Windows UIA scans recorded in the runtime log
(notably the case where a window's BoundingRectangle under-covers its own content).
"""
import sys
import types
import ctypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# core_observation targets Windows: at import it touches ctypes.windll and comtypes COM.
# The tree-building logic under test (build_tree_and_map) and bus.focused_elements are pure
# Python. We stub the Windows-only surface so the logic can be exercised on any platform,
# consistent with tests/test_focused_observation.py importing only core_bus.
if not hasattr(ctypes, "windll"):
    class _Stub:
        def __getattr__(self, _):
            return lambda *a, **k: 0
    ctypes.windll = _Stub()  # type: ignore[attr-defined]
if "comtypes" not in sys.modules:
    comtypes = types.ModuleType("comtypes")
    comtypes.CoInitialize = lambda *a, **k: None
    client = types.ModuleType("comtypes.client")
    client.GetModule = lambda *a, **k: None
    client.CreateObject = lambda *a, **k: None
    comtypes.client = client
    sys.modules["comtypes"] = comtypes
    sys.modules["comtypes.client"] = client
    sys.modules["comtypes.gen"] = types.ModuleType("comtypes.gen")
    sys.modules["comtypes.gen.UIAutomationClient"] = types.ModuleType("comtypes.gen.UIAutomationClient")

import core_bus as bus
import core_observation as obs


def _mk_elem(eid, px, py, action="click", name="x"):
    return {
        "id": eid, "short_id": "", "name": name, "role": "Button", "action": action,
        "px": px, "py": py, "hwnd": 0, "rect": {"left": px - 10, "top": py - 10, "right": px + 10, "bottom": py + 10},
        "enabled": True, "automation_id": "", "class_name": "", "runtime_id": [1, 2, int(eid.split("_")[-1])], "depth": 1,
    }


def _mk_config(max_per_window=120):
    return {
        "enabled": True,
        "scan": {"step_px": 64, "delay_ms": 0, "max_subtree_nodes_per_point": 2000, "max_total_nodes": 10000},
        "filter": {"max_elements": 500, "max_per_window": max_per_window, "max_text": 200,
                   "require_interactive": True, "max_depth": 10, "max_children_per_window": max_per_window},
    }


def test_inc1_orphan_recovery_to_nearest_window():
    """Element whose center falls OUTSIDE its window's reported rect must still attach to that
    window (nearest-window fallback), not orphan to desktop root W0.

    Mirrors the real tick-146 case: Chrome rect right=1315 but content extends to px~1832.
    """
    screen = {"width": 1920, "height": 1080}
    # Two Window-role raw nodes + elements. Chrome rect under-covers its content.
    raw_nodes = [
        {"role": "Window", "hwnd": 111, "name": "Chrome", "text_full": "", "class_name": "C",
         "framework_id": "Win32", "rect": {"left": 605, "top": 0, "right": 1315, "bottom": 1020},
         "offscreen": False, "action": "", "px": 960, "py": 510, "depth": 0, "runtime_id": [111]},
        {"role": "Window", "hwnd": 222, "name": "PowerShell", "text_full": "", "class_name": "P",
         "framework_id": "Win32", "rect": {"left": -8, "top": 1, "right": 598, "bottom": 1023},
         "offscreen": False, "action": "", "px": 295, "py": 512, "depth": 0, "runtime_id": [222]},
    ]
    action_elements = {
        "e_1_2_1": _mk_elem("e_1_2_1", 900, 200),    # inside Chrome rect
        "e_1_2_2": _mk_elem("e_1_2_2", 1721, 284),   # OUTSIDE Chrome rect (was orphaned) - nearest Chrome
        "e_1_2_3": _mk_elem("e_1_2_3", 300, 400),    # inside PowerShell rect
    }
    hwnd_to_z = {111: 0, 222: 1}
    mapped = obs.build_tree_and_map(action_elements, {}, raw_nodes, hwnd_to_z, screen, _mk_config())
    root = mapped["root"]
    # No element may be parented directly to root W0 (only windows are)
    orphans = [c for c in root["children"] if isinstance(c, dict) and not c.get("id", "").startswith("W")]
    assert orphans == [], f"expected no orphaned elements, got {[o['id'] for o in orphans]}"
    # The out-of-rect Chrome element must live under Chrome (W1, z_order 0)
    w1 = next(c for c in root["children"] if c.get("id") == "W1")
    child_ids = {c["id"] for c in w1["children"]}
    assert "e_1_2_2" in child_ids, "out-of-rect element should attach to nearest window (Chrome)"
    print("INC-1 OK: out-of-rect element recovered to nearest window; 0 orphans.")


def test_inc3_truncation_flag_surfaces():
    """When a window exceeds max_per_window, the drop must be observable via
    elements_truncated / elements_dropped_per_window, not silent."""
    screen = {"width": 1920, "height": 1080}
    raw_nodes = [
        {"role": "Window", "hwnd": 111, "name": "Chrome", "text_full": "", "class_name": "C",
         "framework_id": "Win32", "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
         "offscreen": False, "action": "", "px": 960, "py": 540, "depth": 0, "runtime_id": [111]},
    ]
    # 5 elements, cap of 2 -> 3 dropped
    action_elements = {f"e_1_2_{i}": _mk_elem(f"e_1_2_{i}", 100 + i, 100 + i) for i in range(5)}
    mapped = obs.build_tree_and_map(action_elements, {}, raw_nodes, {111: 0}, screen, _mk_config(max_per_window=2))
    assert mapped["elements_truncated"] is True, "truncation must be flagged"
    assert sum(mapped["elements_dropped_per_window"].values()) == 3, "must report exact dropped count"
    print("INC-3 OK: per-window truncation surfaced:", mapped["elements_dropped_per_window"])


def test_inc3_no_truncation_flag_when_under_cap():
    screen = {"width": 1920, "height": 1080}
    raw_nodes = [
        {"role": "Window", "hwnd": 111, "name": "W", "text_full": "", "class_name": "C",
         "framework_id": "Win32", "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
         "offscreen": False, "action": "", "px": 960, "py": 540, "depth": 0, "runtime_id": [111]},
    ]
    action_elements = {f"e_1_2_{i}": _mk_elem(f"e_1_2_{i}", 100 + i, 100 + i) for i in range(3)}
    mapped = obs.build_tree_and_map(action_elements, {}, raw_nodes, {111: 0}, screen, _mk_config(max_per_window=120))
    assert mapped["elements_truncated"] is False
    assert mapped["elements_dropped_per_window"] == {}
    print("INC-3 OK: no false truncation flag under cap.")


def test_inc2_focus_resolves_by_stable_id_after_shortid_churn():
    """A focus reference minted with a now-stale short_id (or the stable id) must still
    resolve to the physical element via its stable id / runtime_id."""
    action_index = {
        # Current-tick short_id is W2E5, but its stable id is e_42_459492_2.
        "W2E5": {"id": "e_42_459492_2", "runtime_id": [42, 459492, 4, 2], "name": "Terminal",
                 "role": "Edit", "action": "write", "rect": {"left": 0, "top": 0, "right": 10, "bottom": 10}},
    }
    # last_reflection referenced the element by its stable id (churn-proof anchor)
    state = {"action_index": action_index, "current_step": {}, "action_frame": {},
             "last_action": {}, "last_reflection": {"lesson": "retry writing to e_42_459492_2"}, "focus_ids": []}
    fe = bus.focused_elements(state)
    assert "W2E5" in fe, "reference by stable id must resolve even when short_id churned"
    assert fe["W2E5"]["id"] == "e_42_459492_2"
    # Also resolves when the (possibly stale) short_id is what was cited
    state2 = dict(state, last_reflection={"lesson": "retry W2E5"})
    assert "W2E5" in bus.focused_elements(state2)
    print("INC-2 OK: focus resolves by stable id and by short_id.")


def test_phase6_stable_id_rendered_for_actionable_elements():
    """desktop_tree_text must cite the identity-stable #id for actionable elements so the model
    can reference a churn-proof address."""
    screen = {"width": 1920, "height": 1080}
    raw_nodes = [
        {"role": "Window", "hwnd": 111, "name": "W", "text_full": "", "class_name": "C",
         "framework_id": "Win32", "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
         "offscreen": False, "action": "", "px": 960, "py": 540, "depth": 0, "runtime_id": [111]},
    ]
    action_elements = {"e_1_2_7": _mk_elem("e_1_2_7", 100, 100, action="click", name="Go")}
    mapped = obs.build_tree_and_map(action_elements, {}, raw_nodes, {111: 0}, screen, _mk_config())
    assert "#e_1_2_7" in mapped["desktop_tree_text"], "stable id must be cited in text tree"
    print("Phase6 OK: stable #id rendered for actionable element.")


def test_phase6_append_narrative_bounds_growth():
    """append_narrative must keep the root goal and bound the appended tail."""
    root = "ROOT GOAL: do the thing."
    eff = root
    for i in range(5000):
        eff = bus.append_narrative(eff, f"\n\n[STEP {i}] some fairly long narrative line about progress and evidence.", root_goal=root)
    assert len(eff) <= bus.NARRATIVE_TAIL_CHARS + len(root) + 100, "narrative must be bounded"
    assert eff.startswith(root), "root goal must be preserved at head"
    assert "trimmed for token efficiency" in eff, "trim marker expected once bounded"
    # under the bound, no trimming
    small = bus.append_narrative(root, "\n\n[STEP] tiny", root_goal=root)
    assert small == root + "\n\n[STEP] tiny"
    print("Phase6 OK: effective_goal growth bounded, root preserved.")


def test_phase6_offscreen_actionable_excluded():
    """filter_raw must drop actionable elements whose center is off the visible screen."""
    screen = {"width": 1920, "height": 1080}
    raw = [
        {"id": "e_on", "role": "Button", "name": "On", "text_full": "", "class_name": "", "hwnd": 5,
         "framework_id": "", "rect": {"left": 90, "top": 90, "right": 110, "bottom": 110}, "px": 100, "py": 100,
         "offscreen": False, "enabled": True, "automation_id": "", "runtime_id": [1], "depth": 1,
         "action": "click", "value": "", "patterns": [], "pattern_values": {}},
        {"id": "e_off", "role": "Button", "name": "Off", "text_full": "", "class_name": "", "hwnd": 5,
         "framework_id": "", "rect": {"left": 90, "top": 1190, "right": 110, "bottom": 1210}, "px": 100, "py": 1200,
         "offscreen": False, "enabled": True, "automation_id": "", "runtime_id": [2], "depth": 1,
         "action": "click", "value": "", "patterns": [], "pattern_values": {}},
    ]
    obs.get_window_z_order = lambda: [5]  # stub Windows-only EnumWindows API
    out = obs.filter_raw(raw, _mk_config(), screen)
    ids = set(out["action_elements"].keys())
    assert "e_on" in ids and "e_off" not in ids, f"off-screen actionable must be excluded, got {ids}"
    print("Phase6 OK: off-screen actionable element excluded.")


if __name__ == "__main__":
    test_inc1_orphan_recovery_to_nearest_window()
    test_inc3_truncation_flag_surfaces()
    test_inc3_no_truncation_flag_when_under_cap()
    test_inc2_focus_resolves_by_stable_id_after_shortid_churn()
    test_phase6_stable_id_rendered_for_actionable_elements()
    test_phase6_append_narrative_bounds_growth()
    test_phase6_offscreen_actionable_excluded()
    print("\nAll observation-reliability regression tests passed.")
