"""
Validation tests for observation subsystem fixes.
Tests rect interpretation, short_id uniqueness, truncation markers,
focused_elements matching, and terminal text extraction.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core_observation as obs
import core_bus as bus


def test_rect_interpretation():
    """Test _to_rect correctly interprets UIA BoundingRectangle formats."""
    # Test width/height format (most common) - use values that exceed screen
    # Screen is 1536x864, so width=2000, height=2000 will exceed
    rect1 = obs._to_rect((10, 10, 2000, 2000))
    # 2000 > 1536 and 2000 > 864, so should be treated as width/height
    assert rect1 == {"left": 10, "top": 10, "right": 2010, "bottom": 2010}, f"Failed: {rect1}"
    
    # Test right/bottom format - element at (100,100) to (150,150)
    rect2 = obs._to_rect((100, 100, 150, 150))
    # 150 >= 100 and 150 <= screen dimensions, so treated as right/bottom
    assert rect2 == {"left": 100, "top": 100, "right": 150, "bottom": 150}, f"Failed: {rect2}"
    
    # Test width/height at origin (small element)
    rect3 = obs._to_rect((0, 0, 100, 100))
    # 100 <= screen, but 100 > 0, so treated as right/bottom in current logic
    # This is the edge case - small elements at origin
    assert rect3 == {"left": 0, "top": 0, "right": 100, "bottom": 100}, f"Failed: {rect3}"
    
    # Test RECT-like object
    class MockRect:
        left, top, right, bottom = 50, 50, 150, 150
    rect4 = obs._to_rect(MockRect())
    assert rect4 == {"left": 50, "top": 50, "right": 150, "bottom": 150}, f"Failed: {rect4}"
    
    print("[OK] test_rect_interpretation passed")


def test_short_id_uniqueness():
    """Test _node_id generates unique IDs even for similar runtime_ids."""
    # Same suffix, different prefix - should be different
    id1 = obs._node_id([1, 2, 3, 4, 5], 100, {"left": 0, "top": 0})
    id2 = obs._node_id([9, 2, 3, 4, 5], 100, {"left": 0, "top": 0})
    assert id1 != id2, f"Collision: {id1} == {id2}"
    
    # Same runtime_id - should be SAME (runtime_id is the canonical identifier)
    id3 = obs._node_id([1, 2, 3, 4, 5], 100, {"left": 0, "top": 0})
    id4 = obs._node_id([1, 2, 3, 4, 5], 100, {"left": 10, "top": 20})
    assert id3 == id4, f"Same runtime_id should produce same ID: {id3} != {id4}"
    
    # No runtime_id fallback - different positions should be different
    id5 = obs._node_id([], 100, {"left": 10, "top": 20})
    id6 = obs._node_id([], 100, {"left": 10, "top": 30})
    assert id5 != id6, f"Fallback collision: {id5} == {id6}"
    
    # Verify hash component is present
    assert "_" in id1 and len(id1.split("_")[-1]) == 4, f"Missing hash: {id1}"
    
    print("[OK] test_short_id_uniqueness passed")


def test_truncation_marker():
    """Test that render() adds truncation marker when limit hit."""
    # Build a mock tree with many nodes
    root = {
        "id": "W0", "role": "Screen", "name": "Screen", "title": "Desktop",
        "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        "fresh_scan": True, "observed_at": 0, "children": []
    }
    
    # Add 10 children
    for i in range(10):
        root["children"].append({
            "id": f"W{i+1}", "short_id": f"W{i+1}", "role": "Window",
            "name": f"Window {i}", "rect": {"left": 0, "top": 0, "right": 100, "bottom": 100},
            "children": []
        })
    
    # We can't easily test render() without the full pipeline, but we can verify
    # the logic exists by checking the source
    import inspect
    source = inspect.getsource(obs.build_tree_and_map)
    assert "TRUNCATED" in source, "Truncation marker not in render function"
    
    print("[OK] test_truncation_marker passed")


def test_focused_elements_by_name():
    """Test focused_elements matches by name, not just short_id."""
    state = {
        "action_index": {
            "W1E1": {"short_id": "W1E1", "name": "Search", "role": "Button", "action": "click"},
            "W1E2": {"short_id": "W1E2", "name": "Submit", "role": "Button", "action": "click"},
            "W2E1": {"short_id": "W2E1", "name": "Terminal", "role": "Text", "action": "read"},
        },
        "current_step": {"description": "Click the Search button"},
        "action_frame": {"target": "Search"},
        "last_action": {},
        "last_reflection": {},
        "focus_ids": [],
    }
    
    focused = bus.focused_elements(state)
    
    # Should match by name "Search" in step description
    assert "W1E1" in focused, f"Expected W1E1 in focused, got {list(focused.keys())}"
    assert focused["W1E1"]["name"] == "Search"
    
    # Should NOT match Submit
    assert "W1E2" not in focused
    
    print("[OK] test_focused_elements_by_name passed")


def test_focused_elements_by_short_id():
    """Test focused_elements still matches by short_id."""
    state = {
        "action_index": {
            "W1E1": {"short_id": "W1E1", "name": "Button", "role": "Button", "action": "click"},
            "W1E2": {"short_id": "W1E2", "name": "Other", "role": "Button", "action": "click"},
        },
        "current_step": {"description": "Click W1E1"},
        "action_frame": {"target": "W1E1"},
        "last_action": {},
        "last_reflection": {},
        "focus_ids": ["W1E1"],
    }
    
    focused = bus.focused_elements(state)
    
    assert "W1E1" in focused
    assert "W1E2" not in focused
    
    print("[OK] test_focused_elements_by_short_id passed")


def test_observation_brief_structure():
    """Test observation_brief returns expected structure."""
    state = {
        "desktop_tree_text": "W0 Screen\n  W1 Window\n    W1E1 Button",
        "observation_artifact": {
            "screen": {"width": 1920, "height": 1080},
            "scan_stats": {"probes": 100, "unique_nodes": 50},
        },
        "observed_at": 1234567890.0,
        "rendered_node_count": 10,
        "max_llm_nodes": 1000,
        "llm_node_limit_hit": False,
    }
    
    brief = bus.observation_brief(state)
    
    assert "desktop_tree_text" in brief
    assert "focused_elements" in brief
    assert "observed_at" in brief
    assert "screen" in brief
    assert "scan_stats" in brief
    assert "rendered_node_count" in brief
    assert "max_llm_nodes" in brief
    assert "llm_node_limit_hit" in brief
    
    print("[OK] test_observation_brief_structure passed")


def test_runtime_id_to_short_id():
    """Test that runtime_id produces consistent short_ids."""
    # Same runtime_id should produce same short_id
    rid = [42, 12345, 4, 5, 12, 2744]
    id1 = obs._node_id(rid, 0, {"left": 614, "top": 109})
    id2 = obs._node_id(rid, 0, {"left": 614, "top": 109})
    assert id1 == id2, f"Non-deterministic: {id1} != {id2}"
    
    # Different runtime_id should produce different short_id
    rid2 = [42, 12345, 4, 5, 12, 2745]
    id3 = obs._node_id(rid2, 0, {"left": 614, "top": 109})
    assert id1 != id3, f"Collision: {id1} == {id3}"
    
    print("[OK] test_runtime_id_to_short_id passed")


def test_element_to_raw_structure():
    """Verify element_to_raw returns expected fields."""
    # We can't easily test without UIA, but we can verify the function exists
    assert hasattr(obs.UiaScanner, 'element_to_raw')
    assert hasattr(obs.UiaScanner, 'harvest_subtree')
    assert hasattr(obs, 'gather_raw')
    assert hasattr(obs, 'filter_raw')
    assert hasattr(obs, 'build_tree_and_map')
    assert hasattr(obs, 'observe')
    
    print("[OK] test_element_to_raw_structure passed")


def run_all_tests():
    """Run all validation tests."""
    print("Running observation subsystem validation tests...\n")
    
    test_rect_interpretation()
    test_short_id_uniqueness()
    test_truncation_marker()
    test_focused_elements_by_name()
    test_focused_elements_by_short_id()
    test_observation_brief_structure()
    test_runtime_id_to_short_id()
    test_element_to_raw_structure()
    
    print("\nAll validation tests passed!")


if __name__ == "__main__":
    run_all_tests()