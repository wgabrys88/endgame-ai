import networkx as nx
import json

G = nx.DiGraph()

with open('runtime_events.jsonl', 'r') as f:
    events = [json.loads(line) for line in f]

prev_node = None
for e in events:
    if e.get('event') in ('node_start', 'node_complete'):
        node = e.get('node', '')
        if node and prev_node and prev_node != node:
            G.add_edge(prev_node, node, tick=e.get('tick', 0))
        prev_node = node

print('Nodes:', list(G.nodes()))
print()
print('Edges (call flow):')
for u, v, data in G.edges(data=True):
    tick_val = data.get('tick', '?')
    print(f'  {u} -> {v} (tick={tick_val})')

cycles = list(nx.simple_cycles(G))
print(f'\nCycles: {cycles}')