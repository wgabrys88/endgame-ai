
import tkinter as tk
import threading, time, os, sys, random, subprocess, json
from datetime import datetime

class ReactorDemo:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("endgame-ai Living Reactor Demo")
        self.root.geometry("900x700")
        self.root.configure(bg="#1a1a2e")
        self.cycle = 0
        self.log_lines = []
        self.modifications = 0
        self.running = True
        self.build_gui()
        self.start_reactor()

    def build_gui(self):
        title = tk.Label(self.root, text="endgame-ai Reactor Demo", font=("Consolas",16,"bold"), fg="#00ff88", bg="#1a1a2e")
        title.pack(pady=5)
        
        status_frame = tk.Frame(self.root, bg="#16213e")
        status_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_planner = tk.Label(status_frame, text="PLANNER: idle", font=("Consolas",10), fg="#e94560", bg="#16213e", anchor="w")
        self.lbl_planner.pack(fill="x", padx=5)
        self.lbl_actor = tk.Label(status_frame, text="ACTOR: idle", font=("Consolas",10), fg="#f5a623", bg="#16213e", anchor="w")
        self.lbl_actor.pack(fill="x", padx=5)
        self.lbl_verifier = tk.Label(status_frame, text="VERIFIER: idle", font=("Consolas",10), fg="#50fa7b", bg="#16213e", anchor="w")
        self.lbl_verifier.pack(fill="x", padx=5)
        self.lbl_reflector = tk.Label(status_frame, text="REFLECTOR: idle", font=("Consolas",10), fg="#bd93f9", bg="#16213e", anchor="w")
        self.lbl_reflector.pack(fill="x", padx=5)
        self.lbl_scheduler = tk.Label(status_frame, text="SCHEDULER: idle", font=("Consolas",10), fg="#8be9fd", bg="#16213e", anchor="w")
        self.lbl_scheduler.pack(fill="x", padx=5)
        
        self.lbl_cycle = tk.Label(self.root, text="Cycle: 0 | Mods: 0", font=("Consolas",11), fg="#fff", bg="#1a1a2e")
        self.lbl_cycle.pack(pady=3)
        
        self.log_text = tk.Text(self.root, height=25, bg="#0f3460", fg="#eee", font=("Consolas",9), wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        with open("reactor_demo_log.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.root.after(0, self._append_log, line)

    def _append_log(self, line):
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")

    def start_reactor(self):
        t = threading.Thread(target=self.reactor_loop, daemon=True)
        t.start()

    def reactor_loop(self):
        tasks = [
            ("count files in demo directory", self.task_count_files),
            ("fetch current system time", self.task_system_time),
            ("search for Grok in local file", self.task_search_grok),
            ("generate self-modification proposal", self.task_self_modify),
        ]
        while self.running:
            self.cycle += 1
            task_name, task_fn = random.choice(tasks)
            self.root.after(0, lambda: self.lbl_cycle.config(text=f"Cycle: {self.cycle} | Mods: {self.modifications}"))
            
            # PLANNER
            self.update_status("planner", f"planning: {task_name}")
            self.log(f"PLAN: selected task '{task_name}'")
            time.sleep(1)
            
            # ACTOR
            self.update_status("actor", f"executing: {task_name}")
            result = task_fn()
            self.log(f"ACT: {result}")
            time.sleep(0.5)
            
            # VERIFIER
            self.update_status("verifier", "verifying result...")
            verified = len(result) > 0
            self.log(f"VERIFY: {'confirmed' if verified else 'denied'} - output len={len(result)}")
            time.sleep(0.5)
            
            # REFLECTOR
            self.update_status("reflector", "reflecting on cycle")
            self.log(f"REFLECT: cycle {self.cycle} complete, stagnation=0.0")
            time.sleep(0.5)
            
            # SCHEDULER
            self.update_status("scheduler", "scheduling next cycle")
            time.sleep(0.5)
            
            # Self-modification every 3 cycles
            if self.cycle % 3 == 0:
                self.do_self_modify()
            
            time.sleep(5)

    def update_status(self, component, status):
        lbl = getattr(self, f"lbl_{component}")
        self.root.after(0, lambda: lbl.config(text=f"{component.upper()}: {status}"))

    def task_count_files(self):
        files = os.listdir(".")
        return f"Found {len(files)} files in current directory"

    def task_system_time(self):
        return f"System time: {datetime.now().isoformat()}"

    def task_search_grok(self):
        target = "grok_search_target.txt"
        if not os.path.exists(target):
            with open(target, "w") as f:
                f.write("Grok is an AI by xAI. endgame-ai talks to Grok.")
        with open(target) as f:
            content = f.read()
        count = content.lower().count("grok")
        return f"Found 'Grok' {count} times in {target}"

    def task_self_modify(self):
        proposal = f"# Self-mod proposal cycle {self.cycle}: add capability_{self.cycle}"
        return f"Proposed: {proposal}"

    def do_self_modify(self):
        self.modifications += 1
        mod_file = "reactor_self_mods.py"
        mod_line = f"# Modification #{self.modifications} at cycle {self.cycle} - {datetime.now().isoformat()}\n"
        with open(mod_file, "a") as f:
            f.write(mod_line)
        self.log(f"SELF-MOD: wrote modification #{self.modifications} to {mod_file}")
        self.update_status("reflector", f"self-modified ({self.modifications} total)")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    app = ReactorDemo()
    app.run()
