import urllib.request
import json

payload = {
    "model": "nvidia-nemotron-3-nano-4b",
    "messages": [
        {"role": "system", "content": "You are the planner node of endgame-ai. Return one JSON object with record_type='plan', data.next_signal, and data.intent."},
        {"role": "user", "content": "{\"goal\": \"open notepad\", \"state\": {\"_phase\": \"executing_node\", \"goal\": \"open notepad\", \"tick\": 0, \"current_node\": \"planner\", \"last_error\": null, \"last_action\": null, \"wiring_transport\": \"openai\"}}"}
    ],
    "temperature": 0.2
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request("http://localhost:1234/v1/chat/completions", data=data, headers={"Content-Type": "application/json"}, method="POST")

with urllib.request.urlopen(req, timeout=30) as resp:
    body = resp.read().decode("utf-8")
    obj = json.loads(body)
    content = obj["choices"][0]["message"]["content"]
    print("Content:", content)
    print("Reasoning:", obj["choices"][0]["message"].get("reasoning", ""))