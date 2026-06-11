import json, time
from pathlib import Path

class InstanceComm:
    def __init__(self, base):
        self.dir = Path(base) / "comms"
        self.dir.mkdir(exist_ok=True)

    def send(self, target, goal):
        msg = {"goal": goal, "from": "self", "ts": time.time()}
        (self.dir / f"to_{target}.json").write_text(json.dumps(msg))

    def receive(self):
        msgs = []
        for f in self.dir.glob("from_*.json"):
            msgs.append(json.loads(f.read_text()))
            f.unlink()
        return msgs
