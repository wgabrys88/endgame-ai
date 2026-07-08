import json

with open('request-logs-2026-07-07.jsonl', 'r') as f:
    for line in f:
        try:
            event = json.loads(line)
            logged = event.get('logged', {})
            chat = logged.get('chat', {})
            request = chat.get('request', {})
            messages = request.get('messages', [])
            
            for msg in messages:
                role = msg.get('role', '')
                content = msg.get('content', [])
                for c in content:
                    if c.get('type') == 'text':
                        text = c.get('text', '')
                        print(f"=== {role.upper()} ({len(text)} chars) ===")
                        print(text[:800])
                        print("...")
                        print()
        except Exception as e:
            print(f"Error: {e}")