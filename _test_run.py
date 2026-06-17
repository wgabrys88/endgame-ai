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

deadline = time.time() + 60
cycles = 0
while time.time() < deadline:
    results = colony.step()
    for name, r in results:
        if r:
            cycles += 1
            print(f"[{cycles}] {name}:{r.get('phase','?')} -> {r.get('event','')} {r.get('conclusion','')}")
    if not results:
        time.sleep(1)
print(f"\nDone: {cycles} cycles in {time.time() - deadline + 60:.0f}s")
