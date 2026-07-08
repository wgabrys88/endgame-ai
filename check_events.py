import json
with open('runtime_events.jsonl') as f:
    events = [json.loads(line) for line in f]
for e in events:
    if e.get('event') in ('node_start', 'node_complete', 'brain_request', 'brain_response'):
        node = e.get('node', '')
        tick = e.get('tick', '')
        signal = e.get('signal', '')
        next_node = e.get('next_node', '')
        print(f"{e['event']:15s} node={node:15s} tick={str(tick):4s} signal={signal:12s} next={next_node}")