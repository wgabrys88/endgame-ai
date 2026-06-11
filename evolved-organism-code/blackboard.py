
import threading, time, collections

class Blackboard:
    def __init__(self):
        self.lock = threading.Lock()
        self.messages = collections.deque(maxlen=200)
        self.work_events = 0
        self.agent_chains = []
        self.status = "idle"

    def post(self, sender, text):
        with self.lock:
            self.messages.append({"t": time.time(), "from": sender, "text": text})
            self.work_events += 1

    def get_recent(self, n=20):
        with self.lock:
            return list(self.messages)[-n:]

    def add_chain(self, name, progress=0.0):
        with self.lock:
            for c in self.agent_chains:
                if c["name"] == name:
                    c["progress"] = progress
                    return
            self.agent_chains.append({"name": name, "progress": progress})
            self.work_events += 1

    def get_chains(self):
        with self.lock:
            return list(self.agent_chains)

    def get_work_events(self):
        with self.lock:
            return self.work_events

BB = Blackboard()
