"""Full system test - observe + LLM decisions, actions SUPPRESSED (dry-run)."""
import sys
import io
import time
import json
import logging
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
from datetime import datetime
logging.basicConfig(
    filename=str(LOGS_DIR / f"test_{datetime.now():%Y%m%d_%H%M%S}.txt"),
    level=logging.DEBUG, format="%(asctime)s %(message)s"
)

sys.path.insert(0, str(BASE_DIR))
from desktop import Desktop
from llm import LLMClient
from bus import Bus
from colony import Colony

def _load_wiring():
    return json.loads((PROMPTS_DIR / "wiring.json").read_text(encoding="utf-8"))

# Patch action execution to be dry-run (no actual clicks/types)
desktop = Desktop()

def dry_click(px, py, hwnd=0):
    print(f"  [DRY-RUN] click({px}, {py}, hwnd={hwnd})")

def dry_type(text):
    print(f"  [DRY-RUN] type_text('{text[:80]}')")

def dry_press(key):
    print(f"  [DRY-RUN] press_key('{key}')")

def dry_hotkey(keys):
    print(f"  [DRY-RUN] hotkey({keys})")

desktop.click = dry_click
desktop.type_text = dry_type
desktop.press_key = dry_press
desktop.hotkey = dry_hotkey

# Create colony (same as TUI does)
wiring = _load_wiring()
bus = Bus()
llm = LLMClient(prompts_dir=PROMPTS_DIR)
colony = Colony(llm=llm, bus=bus, prompts_dir=PROMPTS_DIR, workspace=BASE_DIR, wiring=wiring)
colony.active_slots.clear()

# Set goal
goal = sys.argv[1] if len(sys.argv) > 1 else "open notepad and type hello world"
print(f"GOAL: {goal}")
print(f"{'='*60}")
colony.set_goal(goal)

# Run 3 cycles
for cycle in range(3):
    print(f"\n{'─'*60}")
    print(f"CYCLE {cycle + 1}")
    print(f"{'─'*60}")
    
    # Observe
    t0 = time.time()
    obs = desktop.observe()
    print(f"Observed in {time.time()-t0:.1f}s: {len(obs.elements)} elements, focused='{obs.focused_title}'")
    
    # Feed observation to slots
    for slot in colony.active_slots.values():
        if slot.can_act_desktop:
            slot.observe(obs.context_text, obs.elements)
    
    # Step colony
    t0 = time.time()
    results = colony.step()
    print(f"Step took {time.time()-t0:.1f}s")
    for name, result in results:
        if result:
            print(f"  {name}: phase={result.get('phase','?')} event={result.get('event','')} conclusion={result.get('conclusion','')}")
            actions = result.get("actions", [])
            for a in actions:
                print(f"    ACTION: {a.get('verb','')} target={a.get('target','')} value={a.get('value','')}")
    
    time.sleep(1)

print(f"\n{'='*60}")
print("TEST COMPLETE")
