# Navigation — Desktop & UIA (task-agnostic)

Patterns discovered on Windows 10/11 with UIA. **Not** wired into prompts — inform `guards.advance_hints` and planner behavior.

---

## Core principle

The executor sees only what `observe_screen()` returns. If an element is not in the UIA tree, the act circuit cannot target it — no prompt hack fixes missing UIA.

---

## Generic launch pattern

```
1. hotkey win+r          → Run dialog (if not already visible)
2. write <executable>    → Open field (not goal text)
3. press enter           → launch (prefer enter over clicking OK)
4. focus <window title>  → interact inside app
```

Wired in `guards.advance_hints` for Run dialog transitions.

---

## Generic text entry

| Context | Pattern |
|---------|---------|
| Launch dialog Open field | `write` executable name only |
| App document/editor | `write` into Document or Edit from SCREEN |
| URL/address field | `write` URL or query, then `press enter` |
| Repeat after success | Blocked by `check_repeat_block` — must advance |

---

## Browser (any Chromium-based)

**UIA reality:** native chrome (toolbar, tabs, address bar) usually visible; page DOM often not.

| Works | Often fails |
|-------|-------------|
| Address bar Edit | In-page search boxes |
| Tab title | Video thumbnails as clickable names |
| Toolbar buttons | Dynamic React content |
| `prompt()` dialogs | Embedded players |

**Generic navigation:** focus browser → `hotkey ctrl+l` → write destination → `press enter`

**Accessibility flag (manual):** launch with `--force-renderer-accessibility` for richer trees — still incomplete for SPAs.

---

## System dialog targeting

Prefer `[ID]` from SCREEN over bare names:

```
✓ click [2] Button "OK"
✗ click OK                    → may fail UIA resolution
```

Evidence: Shakira run `click OK: FAILED: element OK not found`.

---

## Wiring editor / self-test

- Server serves `wiring-editor.html` at `/`
- Editor calls `POST /node/{type}` with state
- Auto-discovers port: tries 9078, 9077, 9079 via `/health`
- Mock mode: `no_desktop: true` + inject `screen` in state

---

## What belongs where

| Knowledge type | Belongs in |
|----------------|------------|
| Launch sequence hints | `guards.advance_hints` in wiring.json |
| Circuit output contracts | `prompts/*.txt` |
| UIA limitations | This file + TEST_RESULTS.md |
| Task-specific URLs | **Nowhere** (goal only) |

---

## Self-criticism

`NAVIGATION.md` is human knowledge, not executable wiring. Until patterns become `advance_hints` or planner examples in wiring, the LLM may rediscover failures slowly. That is intentional under task-agnostic prompts — trade speed for generality.