"""Unified agent test - single prompt observe→act loop with LIVE actions."""
import sys
import io
import time
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"
sys.path.insert(0, str(BASE_DIR))

from desktop import Desktop
from llm import LLMClient
from actions import ActionExecutor

def _load_wiring():
    return json.loads((PROMPTS_DIR / "wiring.json").read_text(encoding="utf-8"))

wiring = _load_wiring()
llm = LLMClient(prompts_dir=PROMPTS_DIR)
desktop = Desktop()
actions_exec = ActionExecutor(desktop, wiring)

# Load unified prompt
prompt = (PROMPTS_DIR / "unified.txt").read_text(encoding="utf-8").strip()

goal = sys.argv[1] if len(sys.argv) > 1 else "open calculator and press 2 plus 2 equals"
print(f"GOAL: {goal}")
print(f"{'='*60}")

reasoning_history = []
last_error = ""
last_action = None
repeat_count = 0
MAX_DEPTH = 5

for cycle in range(15):
    print(f"\n{'─'*40} CYCLE {cycle+1} {'─'*40}")
    
    # Observe
    obs = desktop.observe()
    print(f"Screen: {len(obs.elements)} elements, focused='{obs.focused_title}'")
    
    # Build context
    parts = [f"GOAL: {goal}", f"SCREEN:\n{obs.context_text}"]
    if last_error:
        parts.append(f"LAST ERROR: {last_error}")
        last_error = ""
    if reasoning_history:
        rh = "\n".join(f"[attempt] {e}" for e in reasoning_history[-MAX_DEPTH:])
        parts.append(f"LAST REASONING:\n{rh}")
    context = "\n\n".join(parts)
    
    # Call LLM
    t0 = time.time()
    result = llm.call(prompt, context)
    elapsed = time.time() - t0
    
    # Parse response
    try:
        record = json.loads(result.text)
        data = record["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Fallback: extract JSON from mixed text
        extracted = None
        text = result.text.strip()
        for i in range(len(text)):
            if text[i] == '{':
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == '{': depth += 1
                    elif text[j] == '}': depth -= 1
                    if depth == 0:
                        try:
                            extracted = json.loads(text[i:j+1])
                        except json.JSONDecodeError:
                            pass
                        break
                if extracted:
                    break
        if extracted and "data" in extracted:
            data = extracted["data"]
        else:
            print(f"  ✗ Parse error ({elapsed:.1f}s): {e}")
            print(f"  Raw: {result.text[:200]}")
            reasoning_history.append(f"parse error → {result.text[:100]}")
            continue
    
    conclusion = str(data.get("conclusion", "EXECUTE"))
    actions_list = data.get("actions", [])
    
    if conclusion == "DONE":
        # Guard: check if we actually completed compound goals
        goal_lower = goal.lower()
        has_write_goal = any(w in goal_lower for w in ("type", "write", "enter text"))
        # Check if the text from the goal was actually written (not just "notepad" in Run dialog)
        goal_text_candidates = []
        for w in ("type ", "write ", "enter text "):
            if w in goal_lower:
                goal_text_candidates.append(goal_lower.split(w, 1)[1].strip())
        did_write_goal_text = False
        for r in reasoning_history:
            for candidate in goal_text_candidates:
                if candidate and candidate in r.lower():
                    did_write_goal_text = True
        if has_write_goal and not did_write_goal_text:
            print(f"  ⚠ Premature DONE — haven't typed the goal text yet ({elapsed:.1f}s)")
            reasoning_history.append("SYSTEM: you haven't typed the required text yet. Focus the app window and write the text.")
            continue
        print(f"  ✓ GOAL COMPLETE ({elapsed:.1f}s)")
        break
    elif conclusion == "CANNOT":
        print(f"  ✗ CANNOT ({elapsed:.1f}s)")
        reasoning_history.append("cannot")
        continue
    
    # Execute actions
    current_action = json.dumps(actions_list, sort_keys=True)
    if current_action == last_action:
        repeat_count += 1
        if repeat_count >= 2:
            print(f"  ⚠ Repeated same action {repeat_count+1}x — injecting progress hint")
            reasoning_history.append("SYSTEM: You are repeating the same action. Move to the NEXT step of the goal.")
            repeat_count = 0
            continue
    else:
        repeat_count = 0
        last_action = current_action
    
    for a in actions_list:
        verb = str(a.get("verb", ""))
        target = str(a.get("target", ""))
        value = str(a.get("value", ""))
        print(f"  ▶ {verb} target={target} value={value} ({elapsed:.1f}s)")
        r = actions_exec.execute(verb, a, obs.elements)
        status = "✓" if r.success else "✗"
        print(f"    {status} {r.observation}")
        reasoning_history.append(f"{verb} {target} {value} → {'OK' if r.success else r.observation}")
        if not r.success:
            last_error = f"{verb}: {r.observation}"
    
    time.sleep(0.5)

print(f"\n{'='*60}")
print("DONE" if conclusion == "DONE" else "ENDED")
