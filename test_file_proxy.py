import sys
sys.path.insert(0, r'C:\Users\ewojgab\Downloads\endgame-ai')
import json
import time
import threading
from seed_brains.file_proxy import call

def write_response():
    time.sleep(0.5)  # Wait for call to start and delete the file
    resp = {'content': '{"record_type":"plan","data":{"next_signal":"observe","intent":"test"}}', 'reasoning': 'test'}
    with open('comms/response.json', 'w') as f:
        json.dump(resp, f)
    print("Response written")

messages = [{'role': 'system', 'content': 'test'}, {'role': 'user', 'content': 'hello'}]
cfg = {'request_path': 'comms/request.json', 'response_path': 'comms/response.json', 'poll_interval': 0.1, 'timeout': 5}

# Start response writer in background
t = threading.Thread(target=write_response)
t.start()

try:
    result = call(messages, cfg)
    print('SUCCESS:', result)
except Exception as e:
    print('ERROR:', e)

t.join()