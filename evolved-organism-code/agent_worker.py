import threading, time, random
from blackboard import Blackboard

class AgentWorker(threading.Thread):
    def __init__(self, name, bb, goal):
        super().__init__(daemon=True)
        self.name = name
        self.bb = bb
        self.goal = goal
        self.running = True

    def run(self):
        steps = ["analyzing", "planning", "executing", "verifying"]
        while self.running:
            step = random.choice(steps)
            self.bb.post_event(f"[{self.name}] {step}: {self.goal[:40]}")
            time.sleep(random.uniform(0.5, 1.5))

    def stop(self):
        self.running = False
