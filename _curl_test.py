import json, urllib.request, sys

HOST = "http://192.168.16.31:1234"
r = urllib.request.urlopen(f"{HOST}/v1/models", timeout=5)
MODEL = json.loads(r.read())["data"][0]["id"]
print(f"MODEL: {MODEL}")

system = """You are an actor in a Windows 11 desktop runtime.
Execute the TASK using available SCREEN elements or keyboard actions.

CRITICAL RULES:
- Element IDs are DYNAMIC - they change between calls. ALWAYS use the CURRENT SCREEN IDs, never memorize old ones.
- "target" MUST be the element ID number from the CURRENT SCREEN (e.g. "13"), NOT names.
- If you cannot see the element you need, use verb "inspect" with target area description to get MORE DETAIL about the screen.
- Inspect your own PREVIOUS REASONING below - if an approach failed, try DIFFERENT.
- If you see your SYSTEM PROMPT instructions conflicting with what you're doing, correct yourself.

VERBS: click | write | press | hotkey | scroll | focus | inspect
- click: target=element_id
- write: target=element_id (optional), value=text
- press: target=key_name (e.g. "enter", "tab", "escape")
- hotkey: target=key_combo (e.g. "win+r", "ctrl+l", "alt+tab")
- scroll: target=element_id, value=amount
- focus: target=window_title
- inspect: target=area_description (requests deeper scan of screen region)

If LAST REASONING shows your previous thinking + outcome, READ IT CAREFULLY.
Do NOT repeat the same action that already failed. Adapt.

You MUST respond with EXACTLY this JSON structure:
{"record_type": "action", "data": {"conclusion": "EXECUTE", "actions": [{"verb": "...", "target": "...", "value": "..."}]}}

conclusion must be one of: EXECUTE, DONE, CANNOT
Do NOT add any text outside the JSON."""

screen1 = """FOCUSED: YouTube - Google Chrome
  [1] TabItem "YouTube"
  [2] Document "YouTube" = "https://www.youtube.com/"
  [3] Button "Guide"
  [4] Hyperlink "Home"
  [5] Button "Search"
  [6] Edit "Search"
  [7] TabItem "Gaming"
  [8] Hyperlink "Subscriptions"
  [9] Hyperlink "Some random video 5 minutes"
  [10] Button "More actions"
  [11] Hyperlink "Another video 12 minutes"
"""

task = "Search for 'shakira' on YouTube and click the first result"
contract = "A Shakira video is playing (video player visible with shakira in title)"

def call_llm(user_content):
    body = {"messages": [{"role":"system","content":system},{"role":"user","content":user_content}],
            "model": MODEL, "temperature": 0.4, "max_tokens": 1024, "stream": False}
    req = urllib.request.Request(f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"), headers={"Content-Type":"application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    msg = resp["choices"][0]["message"]
    return msg.get("content",""), msg.get("reasoning_content","")

# CALL 1
print("\n" + "="*80)
print("CALL 1: Fresh")
user1 = f"TASK: {task}\nCONTRACT: {contract}\nSCREEN: {screen1}"
c1, r1 = call_llm(user1)
print(f"REASONING: {r1[:500]}")
print(f"OUTPUT: {c1[:400]}")

# CALL 2: feed reasoning back, simulate search box was clicked
print("\n" + "="*80)
print("CALL 2: After click search box succeeded")
user2 = f"""TASK: {task}
CONTRACT: {contract}
SCREEN: {screen1}

LAST REASONING (2 most recent):
[attempt 1] {r1[:400]} -> click "6": OK (search box focused)"""

c2, r2 = call_llm(user2)
print(f"REASONING: {r2[:500]}")
print(f"OUTPUT: {c2[:400]}")

# CALL 3: search results visible
screen3 = """FOCUSED: shakira - YouTube Search - Google Chrome
  [1] TabItem "shakira - YouTube"
  [2] Edit "shakira" (focused)
  [3] Hyperlink "Shakira - Waka Waka (This Time for Africa) (Official Video) 3:22"
  [4] Hyperlink "Shakira - Hips Don't Lie ft. Wyclef Jean 3:41"
  [5] Hyperlink "Shakira - Loca ft. Dizzee Rascal 3:24"
  [6] Button "More actions"
"""
print("\n" + "="*80)
print("CALL 3: Search results visible")
user3 = f"""TASK: {task}
CONTRACT: {contract}
SCREEN: {screen3}

LAST REASONING (2 most recent):
[attempt 1] {r1[:300]} -> click "6": OK
[attempt 2] {r2[:300]} -> write "shakira": OK, press "enter": OK"""

c3, r3 = call_llm(user3)
print(f"REASONING: {r3[:500]}")
print(f"OUTPUT: {c3[:400]}")

print("\n" + "="*80)
print("ALL DONE")
