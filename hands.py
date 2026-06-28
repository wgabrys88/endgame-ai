"""hands — the body. A thin adapter over the proven Windows I/O layer.

We do NOT reimplement raw UI Automation / ctypes. desktop.py and actions.py are a mature,
dependency-free Windows observation + input layer. hands reuses them directly: observe
the screen, execute a verb, read the focused title.

Verbs (from actions.py): click, write, press, hotkey, focus, open_url, scroll, wait,
launch. Targets are visible element ids/tokens or window titles from the observation.

If the I/O layer is unavailable (e.g. not on Windows), hands degrade to a clear text
message rather than crashing, so the cognition loop can still be exercised.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent.resolve()


class Hands:
    def __init__(self):
        self._io = None
        self._err = ""
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        try:
            import actions  # desktop I/O layer (sibling module)
            actions.configure_runtime({})
            self._io = actions
        except Exception as e:  # not on Windows, or import failure
            self._err = f"{type(e).__name__}: {e}"

    @property
    def live(self) -> bool:
        return self._io is not None

    def observe(self) -> str:
        if not self._io:
            return f"(no desktop: {self._err})"
        try:
            return self._io.observe_screen()
        except Exception as e:
            return f"(observe failed: {type(e).__name__}: {e})"

    def focused_title(self) -> str:
        if not self._io:
            return ""
        try:
            return self._io.get_focused_title()
        except Exception:
            return ""

    def act(self, verb: str, target: str = "", value: str = "") -> str:
        if not self._io:
            return f"FAILED: no desktop ({self._err})"
        try:
            return self._io.execute_verb(verb, target, value)
        except Exception as e:
            return f"FAILED: {type(e).__name__}: {e}"
