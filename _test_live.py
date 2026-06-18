"""Real execution test - actions are LIVE. Safe goal only."""
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
    filename=str(LOGS_DIR / f"live_{datetime.now():%Y%m%d_%H%M%S}.txt"),
    level=logging.DEBUG, format="%(asctime)s %(message)s"
)

sys.path.insert(0, str(BASE_DIR))
from desktop import Desktop
from llm import LLMClient
from bus import Bus
from colony import Colony
from actions import ActionExecutor

def _load_wiring():
    return json.loads((PROMPTS_DIR / "wiring.json").read_text(encoding="utf-8"))

wiring = _load_wiring()
bus = Bus()
llm = LLMClient(prompts_dir=PROMPTS_DIR)
colony = Colony(llm=llm, bus=bus, prompts_dir=PROMPTS_DIR, workspace=BASE_DIR, wiring=wiring)
colony.active_slots.clear()

desktop = Desktop()
actions_exec = ActionExecutor(desktop, wiring)

goal = sys.argv[1] if len(sys.argv) > 1 else "open notepad and type hello world"
print(f"GOAL: {goal}")
print(f"{'='*60}")
colony.set_goal(goal)

for cycle in range(10):
    print(f"\n{'─'*60}")
    print(f"CYCLE {cycle + 1}")
    print(f"{'─'*60}")

    obs = desktop.observe()
    print(f"Observed: {len(obs.elements)} elements, focused='{obs.focused_title}'")

    for slot in colony.active_slots.values():
        if slot.can_act_desktop:
            slot.observe(obs.context_text, obs.elements)

    results = colony.step()
    for name, result in results:
        if not result:
            continue
        event = result.get("event", "")
        conclusion = result.get("conclusion", "")
        print(f"  {name}:{result.get('phase','?')} → {event} {conclusion}")

        actions_list = result.get("actions", [])
        if actions_list:
            slot = colony.active_slots.get(name)
            elements = slot.state.screen_elements if slot else {}
            reasoning_entry = result.get("reasoning_entry")
            outcomes = []
            for a in actions_list:
                verb = str(a.get("verb", ""))
                print(f"    ▶ {verb} target={a.get('target','')} value={a.get('value','')}")
                r = actions_exec.execute(verb, a, elements)
                print(f"      {'✓' if r.success else '✗'} {r.observation}")
                outcomes.append(f"{verb}: {'OK' if r.success else r.observation}")
                if slot and not r.success:
                    slot.state.last_action_error = f"{verb}: {r.observation}"
            if slot and reasoning_entry is not None:
                reasoning_entry["outcome"] = "; ".join(outcomes)
                slot.state.reasoning_history.append(reasoning_entry)

        if event == "goal_complete":
            print(f"\n{'='*60}")
            print("GOAL COMPLETE!")
            sys.exit(0)

    # Show task progress
    for sname, slot in colony.active_slots.items():
        if slot.state.goal:
            done = sum(1 for t in slot.state.tasks if t.status == "verified_done")
            total = len(slot.state.tasks)
            active = next((t for t in slot.state.tasks if t.status == "active"), None)
            print(f"  [{sname}] {done}/{total} done, active: {active.description[:50] if active else 'none'}")

    time.sleep(0.5)

print(f"\n{'='*60}")
print("MAX CYCLES REACHED")
