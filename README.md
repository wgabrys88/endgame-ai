```powershell
# wipe dumps
Remove-Item -Recurse -Force .\_transmissions -ErrorAction SilentlyContinue

# switch wiring to execute (default)
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_guidance'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"

# switch wiring to verify
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_verify'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"

# switch wiring to recover
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_recover'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"

# brain-only (no path → LLM, exit 42, no body)
python .\core_organism.py --breakpoint "click once in the center of the screen"

# body-only (path → no LLM, run code from dumps)
python .\core_organism.py --breakpoint .\_transmissions
```
