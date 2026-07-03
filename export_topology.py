from __future__ import annotations
import pathlib
from typing import Any
import brain
import bus
ROOT = pathlib.Path(__file__).parent.resolve()

def collect_datasheets(wiring: dict[str, Any]) -> dict[str, dict[str, Any]]:
    edges = wiring.get('topology', {}).get('edges', {})
    sheets: dict[str, dict[str, Any]] = {}
    for node in wiring.get('topology', {}).get('nodes', []):
        mapping = edges.get(node, {})
        signals = sorted(mapping.keys()) if isinstance(mapping, dict) else []
        sheets[str(node)] = {'node': str(node), 'kind': 'organism_node', 'signals': signals, 'record_type': None}
    return sheets

def main() -> int:
    wiring = brain.load_json(ROOT / 'wiring.json')
    print(bus.mermaid_state_diagram(wiring, collect_datasheets(wiring)), end='')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())