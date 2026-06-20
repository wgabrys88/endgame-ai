"""ROD proof: Open Chrome -> YouTube -> search Shakira Waka Waka -> play video.
Uses desktop.py + actions.py directly on Windows.
Planner->Act->Verify->Reflect loop with LM Studio."""
import json, time, urllib.request, pathlib

# Load wiring for config
WIRING = json.loads(pathlib.Path("prompts/wiring.json").read_text(encoding="utf-8"))
MODEL = json.loads(pathlib.Path("prompts/model.json").read_text(encoding="utf-8"))
LLM_URL = f"{MODEL['host']}/v1/chat/completions"

from actions import execute_verb, observe_screen
from desktop import Desktop

desktop = Desktop()

def llm(system_prompt, user_msg):
    body = json.dumps({"model": MODEL.get("model","local"), "messages":[
        {"role":"system","content":system_prompt},
        {"role":"user","content":user_msg}
    ], "temperature":0.3, "max_tokens":512}).encode()
    req = urllib.request.Request(LLM_URL, body, {"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def observe():
    return observe_screen()

def act(verb, target, value=""):
    return execute_verb(verb, target, value)

# --- ROD loop ---
GOAL = "Open Chrome, go to youtube.com, search 'Shakira Waka Waka', click on the first video result and play it"
MAX_STEPS = 20

print(f"=== ROD TEST: {GOAL} ===\n")

history = []
for step in range(MAX_STEPS):
    screen = observe()
    print(f"\n--- Step {step+1} ---")
    print(f"Screen: {screen[:300]}")
    
    # Check if video is playing (verify condition)
    if "playing" in screen.lower() or ("youtube" in screen.lower() and "pause" in screen.lower()):
        print("\n=== SUCCESS: Video appears to be playing! ===")
        break
    
    # Plan next action
    prompt = f"""You are a desktop automation agent. Your goal: {GOAL}

Current screen observation:
{screen}

Previous actions: {json.dumps(history[-5:]) if history else 'none'}

Respond with EXACTLY one JSON action:
{{"verb": "click|write|press|hotkey|focus", "target": "<element name or number>", "value": "<text to type or key>"}}

Rules:
- Use "focus" with title to switch windows
- Use "write" to type in search boxes
- Use "press" with "enter" to submit
- Use "click" with element name/number to click
- If Chrome isn't open, use hotkey "win" then write "chrome" then press "enter"
"""
    
    try:
        response = llm("You are a precise desktop automation agent. Output only valid JSON.", prompt)
        # Parse JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n",1)[1].rsplit("```",1)[0]
        action = json.loads(response)
        verb = action.get("verb","")
        target = action.get("target","")
        value = action.get("value","")
        
        print(f"Action: {verb} target='{target}' value='{value}'")
        result = act(verb, target, value)
        print(f"Result: {result}")
        history.append({"step":step, "verb":verb, "target":target, "result":result})
        time.sleep(1.5)
    except Exception as e:
        print(f"Error: {e}")
        history.append({"step":step, "error":str(e)})
        time.sleep(1)

else:
    print("\n=== FAILED: Max steps reached ===")

print(f"\nTotal steps: {len(history)}")
