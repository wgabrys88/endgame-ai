# 3. The Observation Model: Whole-Screen, Focus-Free

## One Flat Scan, Every Visible Element

```python
def observe(desktop, config):
    gathered = gather(desktop, config)      # UIA hover-cache scan
    filtered = filter_gather(gathered, config)
    return filtered
```

The scanner hovers a low-discrepancy grid over the entire desktop, caching UIA properties and patterns. Every visible window, button, edit, list, pane — ranked by content and on-screen position — ends up in one tree.

**No focused window. No foreground tracking.** The body never steals, tracks, or reasons about focus. The brain acts on *any* element directly.

## Short Hierarchical IDs: W2E4C1

```
W0 Screen Desktop
  W1 Window Task Manager
    W1E1 Text Task Manager [read]
    W1E2 Button CPU 43% [click]
    W1E3 Pane
    W1E4 Pane CPU
  W2 Window OpenCode
    W2E1 Group
    W2E2 Document OpenCode [write]
    W2E3 List Desktop [scroll]
    W2E4 Hyperlink ... [click]
  W0C1 Button OpenCode - 1 running window [click]
  W0C2 Button Task Manager CPU 50% [click]
```

- `W0` = Screen root
- `W{n}` = Window n (z-order)
- `E{n}` = Element n within window
- `C{n}` = Child n of parent element
- Action suffix: `[click]`, `[read]`, `[write]`, `[scroll]`

These IDs are **the only addressing the brain sees**. Long runtime IDs (`e_42_1638582_4_0_0_399`) live only in `action_index` values for execution.

## Dual Index Architecture

```python
# Brain-facing: semantic tree with short_ids as keys
"desktop_tree": {
  "node_index": { "W1E2": {...}, "W1E4": {...} },
  "root": { "id": "W0", "children": [...] }
}

# Body-facing: actionable elements with runtime_id for execution
"action_index": {
  "W1E2": { "id": "e_42_...", "runtime_id": [...], "px": 123, "py": 456, "hwnd": 789 }
}
```

Brain picks `W1E2` from `desktop_tree_text`. Body executes via `action_index["W1E2"]["runtime_id"]`. Single lookup path. No fallback.