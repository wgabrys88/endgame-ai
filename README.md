```powershell
# wipe dumps
Remove-Item -Recurse -Force .\_transmissions -ErrorAction SilentlyContinue

# restore default start (guidance → execute → …)
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_guidance'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"

# full life (no fuse; dumps still written)
python .\core_organism.py "programatically open notepad"

# fuse: live LLM once → full dump → exit 42 (hands do not run that reply)
python .\core_organism.py --breakpoint "programatically open notepad"

# inject one full reply (content.txt or transmission.json) → hands run → wheel continues
# until next live LLM → fuse dump → exit 42
python .\core_organism.py --breakpoint .\_transmissions\PREFIX_content.txt

# aim first organ (optional lab)
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_verify'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"
python -c "import json,pathlib; p=pathlib.Path('wiring.json'); w=json.loads(p.read_text(encoding='utf-8')); w['topology']['cycle_start']='node_recover'; p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')"
```
