"""Headless test run — no TUI, just colony.step() for N seconds."""
import json, logging, sys, time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.resolve()
_LOGS = BASE / "logs"
_LOGS.mkdir(exist_ok=True)
logging.basicConfig(filename=str(_LOGS / f"{datetime.now():%Y%m%d_%H%M%S}.txt"),
                    level=logging.DEBUG, format="%(asctime)s %(message)s")

from llm import LLMClient
from bus import Bus
from colony import Colony

BASE = Path(__file__).parent.resolve()
wiring = json.loads((BASE / "prompts/wiring.json").read_text(encoding="utf-8"))
bus = Bus()
llm = LLMClient(prompts_dir=BASE / "prompts")
colony = Colony(llm=llm, bus=bus, prompts_dir=BASE / "prompts", workspace=BASE, wiring=wiring)
colony.active_slots.clear()
goal = " ".join(sys.argv[1:]) or "open chrome and play shakira on youtube"
colony.set_goal(goal)

deadline = time.time() + 120
cycles = 0

from actions import ActionExecutor
from desktop import Desktop
desktop = Desktop()
executor = ActionExecutor(desktop, wiring)

def refresh_screen():
    """Observe desktop and update active slot's screen state."""
    obs = desktop.observe()
    for slot in colony.active_slots.values():
        slot.observe(obs.context_text, obs.elements)

while time.time() < deadline:
    refresh_screen()
    results = colony.step()
    for name, r in results:
        if r:
            cycles += 1
            print(f"[{cycles}] {name}:{r.get('phase','?')} -> {r.get('event','')} {r.get('conclusion','')}")
            actions = r.get("actions", [])
            reasoning_entry = r.get("reasoning_entry")
            slot = colony.active_slots.get(name)
            if actions and slot:
                elements = slot.state.screen_elements or {}
                outcomes = []
                for act in actions:
                    verb = str(act.get("verb", ""))
                    if verb == "inspect":
                        # inspect = re-observe and update screen
                        refresh_screen()
                        outcomes.append("inspect:OK")
                        print(f"      inspect -> OK (screen refreshed)")
                    else:
                        res = executor.execute(verb, act, elements)
                        outcomes.append(f"{verb}:{'OK' if res.success else res.observation}")
                        print(f"      {verb} -> {'OK' if res.success else 'FAIL'}: {res.observation[:80]}")
                        if not res.success:
                            slot.state.last_action_error = f"{verb}: {res.observation}"
                        bus.publish("evidence", "tool", slot.state.active_task_id or "",
                                   {"verb": verb, "success": res.success, "obs": res.observation})
                if reasoning_entry is not None:
                    reasoning_entry["outcome"] = "; ".join(outcomes)
                    slot.state.reasoning_history.append(reasoning_entry)
            elif reasoning_entry is not None and slot:
                reasoning_entry["outcome"] = "no actions"
                slot.state.reasoning_history.append(reasoning_entry)
    if not results:
        time.sleep(1)
print(f"\nDone: {cycles} cycles in {time.time() - deadline + 60:.0f}s")
