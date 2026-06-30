import sys
import json
import time
import threading
import os

sys.path.insert(0, r'C:\Users\ewojgab\Downloads\endgame-ai')

# Auto-responder for file_proxy - handles 2 calls per node (ROD pattern)
def auto_respond():
    # Each node makes 2 brain calls (ROD: reasoning + decision)
    # We need 2 responses per node
    responses = [
        # Planner - call 1 (reasoning)
        {'content': 'reasoning for plan', 'reasoning': 'reasoning for plan'},
        # Planner - call 2 (decision)
        {'content': '{"record_type":"plan","data":{"next_signal":"observe","intent":"open notepad"}}', 'reasoning': 'plan to open notepad'},
        # Observe - call 1 (reasoning)
        {'content': 'reasoning for observe', 'reasoning': 'reasoning for observe'},
        # Observe - call 2 (decision) - observe doesn't use brain, but decide does
        # Actually observe doesn't call brain.think(), it just returns observation
        # Decide - call 1 (reasoning)
        {'content': 'reasoning for decide', 'reasoning': 'reasoning for decide'},
        # Decide - call 2 (decision)
        {'content': '{"record_type":"decision","data":{"next_signal":"act","action":{"verb":"open_notepad"}}}', 'reasoning': 'decide to open notepad'},
        # Act - call 1 (reasoning) - act doesn't call brain
        # Verify - call 1 (reasoning)
        {'content': 'reasoning for verify', 'reasoning': 'reasoning for verify'},
        # Verify - call 2 (decision)
        {'content': '{"record_type":"verification","data":{"next_signal":"planner","success":true}}', 'reasoning': 'notepad opened successfully'},
        # Reflect - call 1 (reasoning)
        {'content': 'reasoning for reflect', 'reasoning': 'reasoning for reflect'},
        # Reflect - call 2 (decision)
        {'content': '{"record_type":"reflection","data":{"next_signal":"planner","lesson":"notepad opens via open_notepad verb"}}', 'reasoning': 'reflection on action'},
    ]
    
    for i, resp in enumerate(responses):
        # Wait for request.json to appear
        while not os.path.exists('comms/request.json'):
            time.sleep(0.1)
        time.sleep(0.2)  # Let the request be fully written
        print(f"Writing response {i+1}/{len(responses)}")
        with open('comms/response.json', 'w') as f:
            json.dump(resp, f)
        # Wait for request.json to be updated (next call)
        time.sleep(0.5)

# Start auto-responder in background
t = threading.Thread(target=auto_respond, daemon=True)
t.start()

# Run organism
from organism import run
run("open notepad", reset=True, max_ticks=5, max_brain_calls=20)
print("Organism completed")