r"""Needle. The engine lives inside the board's `## engine` python block; this only drops it.

    python entity.py entity.md [--dry|--once|--inject FILE]

Equivalent one-liner, no py file:
    python -c "import re,pathlib,sys; t=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); exec(re.search(chr(96)*3+'python'+chr(10)+'(.*?)'+chr(10)+chr(96)*3, t, re.S).group(1), {'BOARD':sys.argv[1],'ARGV':sys.argv})" entity.md
"""
import re, sys, pathlib

if len(sys.argv) < 2:
    sys.exit("usage: python entity.py BOARD.md [--dry|--once|--inject FILE]")
board = sys.argv[1]
text = pathlib.Path(board).read_text(encoding="utf-8")
m = re.search(r"##\s+engine\s*\n```python\n(.*?)^```", text, re.S | re.M)
if not m:
    sys.exit("no `## engine` python block found in " + board)
exec(m.group(1), {"BOARD": board, "ARGV": sys.argv})
