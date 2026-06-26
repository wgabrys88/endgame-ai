"""Compatibility wrapper for the panel-managed endgame-ai slot runtime.

Preferred startup is:
    python server.py
    open http://127.0.0.1:9077/
"""
from __future__ import annotations

import sys
import time

from server import http_port, slot_status, start_slots, stop_slots


def _slots(argv: list[str]) -> list[int]:
    slots = []
    for arg in argv:
        if arg.isdigit():
            slot = int(arg)
            if slot > 0 and slot not in slots:
                slots.append(slot)
    return slots or [1, 2]


def main(argv: list[str] | None = None) -> int:
    slots = _slots(argv if argv is not None else sys.argv[1:])
    result = start_slots(slots)
    print(f"endgame-ai compatibility colony started slots {slots}")
    for item in result.get("started", []):
        print(f"  slot {item['slot']} {item['status']} port={item['port']} pid={item.get('pid')}")
    print("Panel root:", f"http://127.0.0.1:{http_port(0)}/")
    print("Slot 1:", f"http://127.0.0.1:{http_port(1)}/")
    try:
        while True:
            statuses = slot_status(slots)
            if not any(s.get("running") for s in statuses):
                print("All slots stopped.")
                return 0
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping managed slots...")
        stop_slots(slots)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
