#!/usr/bin/env python3
"""Generate a slim, headless-only twin of endgame.md.

Derives the twin FRESH from the live endgame.md every run, so it can never drift:
it is a build output, not a maintained second source. The single-document law is
preserved because endgame.md remains the one authority; this file is disposable.

What it does: replaces the ## capabilities Python body with only the parts the
headless (--no-gui) path actually executes -- ROOT, NO_GUI, _LAST_OBS,
_no_gui_hand, build, environment -- and drops the ~840 lines of Windows UI
Automation and input synthesis that a GUI-less host never runs. Everything else
in the document (config, engine, reset, prompts, memory) is copied verbatim.

Usage:
    python3 make_headless_twin.py [SOURCE] [DEST]
Defaults: SOURCE=endgame.md  DEST=endgame-headless.md
The twin is always run WITH --no-gui; running it on Windows for a real desktop
makes no sense (the hand is gone). Do not commit the twin.
"""
import sys
import pathlib

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "endgame.md")
DEST = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "endgame-headless.md")

doc = SRC.read_text(encoding="utf-8")
OPEN = "## capabilities\n```python\n"
if OPEN not in doc:
    raise SystemExit("no `## capabilities` python fence found in " + str(SRC))
head, rest = doc.split(OPEN, 1)
cap_body, tail = rest.split("\n```", 1)

# Slice the live tail: from the _LAST_OBS anchor to the end of the section.
ANCHOR = "_LAST_OBS = {"
if ANCHOR not in cap_body:
    raise SystemExit("capabilities has no _LAST_OBS anchor; structure changed")
kept_tail = cap_body[cap_body.index(ANCHOR):]

# Drop the eager bind line; on a headless twin NO_GUI is always true so it would
# never fire, but _bind_windows no longer exists, so remove it to keep the body
# honest and free of dangling names.
kept_tail = kept_tail.replace("if not NO_GUI:\n    _bind_windows()\n\n\n", "")
kept_tail = kept_tail.replace("if not NO_GUI:\n    _bind_windows()\n", "")

# Minimal header: the two names the kept functions need, plus types import.
header = (
    "import types as _types\n"
    "import pathlib as _pathlib\n\n"
    'NO_GUI = True\n'
    'ROOT = _pathlib.Path(globals().get("BOARD", ".")).resolve().parent\n\n\n'
)

slim_cap = header + kept_tail.rstrip("\n") + "\n"
twin = head + OPEN + slim_cap + "\n```" + tail
DEST.write_text(twin, encoding="utf-8", newline="\n")

# Report the reduction.
def _lines(s):
    return s.count("\n") + 1
print("wrote %s" % DEST)
print("  source doc lines : %d" % _lines(doc))
print("  twin doc lines   : %d" % _lines(twin))
print("  capabilities: %d -> %d lines" % (_lines(cap_body), _lines(slim_cap)))

# Self-check: the twin's engine, reset, and slim capabilities must compile, and
# capabilities must exec cleanly with BOARD/NO_GUI injected the way the engine does.
def _fence(text, name):
    o = "## %s\n```python\n" % name
    return text.split(o, 1)[1].split("\n```", 1)[0]

for name in ("engine", "reset", "capabilities"):
    compile(_fence(twin, name), name, "exec")
import types as _t
m = _t.ModuleType("capabilities")
m.BOARD = str(DEST)
m.NO_GUI = True
exec(_fence(twin, "capabilities"), m.__dict__)
sec = {}
m.environment(sec)
ns = m.build("actor", sec)
assert sec["environment"].startswith("(no GUI"), sec["environment"]
try:
    ns["desktop"].click(1, 2)
    raise SystemExit("FAIL: headless desktop.click did not raise")
except RuntimeError:
    pass
assert m.build("witness", sec).get("desktop") is None
print("  self-check OK: compiles, environment thin-reads, desktop hand raises on call")
