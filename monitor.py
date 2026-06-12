#!/usr/bin/env python3
"""Colony monitor — deduces patterns and appends insights to report.md every 3 min."""
import json, os, time, glob
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
REPORT = os.path.join(BASE, "report.md")
INTERVAL = 180

prev_state = {}

def load_events(name):
    path = f"events-child-{name}.jsonl"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def analyze():
    files = sorted(glob.glob("events-child-*.jsonl"))
    names = [f.replace("events-child-","").replace(".jsonl","") for f in files]
    if not names:
        return None

    state = {}
    for name in names:
        events = load_events(name)
        s = {"total": len(events), "fissions": 0, "confirms": 0, "denials": 0,
             "reflects": 0, "timeouts": 0, "blocked": 0, "exec_ok": 0, "exec_total": 0,
             "verbs": Counter(), "obs_set": set(), "rules": [], "denial_reasons": [],
             "plan_topics": [], "last_done_when": ""}
        for e in events:
            p = e.get("phase",""); d = e.get("d") or {}
            if p == "fission": s["fissions"] += 1
            elif p == "verify":
                v = d.get("verdict","")
                if v == "confirmed": s["confirms"] += 1
                elif v == "denied":
                    s["denials"] += 1
                    s["denial_reasons"].append(d.get("evidence","")[:80])
            elif p == "reflect":
                s["reflects"] += 1
                r = d.get("rule","").strip()
                if r: s["rules"].append(r)
            elif p == "actor":
                s["exec_total"] += 1
                if d.get("ok"): s["exec_ok"] += 1
                obs = d.get("obs","")
                if "timeout" in obs: s["timeouts"] += 1
                elif obs and "no output" not in obs.lower() and obs not in ("ok",):
                    s["obs_set"].add(obs[:100])
            elif p == "plan":
                dw = d.get("done_when","")
                if dw: s["last_done_when"] = dw[:80]
                if d.get("mode") == "blocked": s["blocked"] += 1
        state[name] = s
    return state

def deduce(state):
    """Produce human insight paragraphs, not raw data."""
    global prev_state
    lines = []
    ts = time.strftime("%H:%M:%S")
    total_f = sum(s["fissions"] for s in state.values())
    total_ev = sum(s["total"] for s in state.values())
    total_d = sum(s["denials"] for s in state.values())
    total_r = sum(s["reflects"] for s in state.values())
    total_to = sum(s["timeouts"] for s in state.values())
    active = sum(1 for s in state.values() if s["total"] > 0)

    lines.append(f"### {ts} — {active} agents, {total_ev} events, {total_f} fissions\n")

    # Who's producing?
    producers = [(n,s) for n,s in state.items() if s["fissions"] > 0]
    stuck = [(n,s) for n,s in state.items() if s["total"] > 50 and s["fissions"] == 0 and s["exec_ok"] == 0]
    learning = [(n,s) for n,s in state.items() if s["reflects"] > 0]

    if producers:
        lines.append("**Productive:** " + ", ".join(f"{n}({s['fissions']}F)" for n, s in producers))
    if stuck:
        lines.append(f"**Stuck:** {', '.join(n for n,_ in stuck)} — no successful execs")
    if total_to > 0:
        timeout_agents = [(n,s["timeouts"]) for n,s in state.items() if s["timeouts"]>0]
        lines.append(f"**Timeouts:** {', '.join(f'{n}({t})' for n,t in timeout_agents)} — likely subprocess/git calls")

    # What are they trying to do?
    goals = set()
    for n,s in state.items():
        if s["last_done_when"]:
            goals.add(s["last_done_when"])
    if goals:
        lines.append(f"\n**Current objectives:** ")
        for g in list(goals)[:4]:
            lines.append(f"- {g}")

    # What did they learn?
    all_rules = []
    for s in state.values():
        all_rules.extend(s["rules"])
    prev_rules = set()
    for s in prev_state.values():
        prev_rules.update(s.get("rules",[]))
    new_rules = [r for r in all_rules if r not in prev_rules]
    if new_rules:
        seen = set()
        lines.append(f"\n**New lessons this cycle:**")
        for r in new_rules:
            short = r[:60].lower()
            if short not in seen:
                seen.add(short)
                lines.append(f"- {r[:100]}")

    # Pattern detection
    denial_reasons = []
    for s in state.values():
        denial_reasons.extend(s["denial_reasons"])
    if denial_reasons:
        top = Counter(denial_reasons).most_common(1)[0]
        if top[1] >= 3:
            lines.append(f"\n**Pattern:** Verifier repeatedly denying for: \"{top[0][:60]}\" ({top[1]}x)")

    # Real output (what files exist in comms)
    comms = os.listdir("runtime/comms") if os.path.isdir("runtime/comms") else []
    non_beacon = [f for f in comms if not f.startswith("beacon-")]
    if non_beacon:
        lines.append(f"\n**Colony artifacts:** {', '.join(non_beacon[:8])}")

    # Delta from last cycle
    if prev_state:
        new_fissions = total_f - sum(s.get("fissions",0) for s in prev_state.values())
        new_denials = total_d - sum(s.get("denials",0) for s in prev_state.values())
        new_reflects = total_r - sum(s.get("reflects",0) for s in prev_state.values())
        if new_fissions or new_denials or new_reflects:
            lines.append(f"\n**Δ since last:** +{new_fissions}F +{new_denials}D +{new_reflects}R")

    lines.append("\n---\n")
    prev_state = {n: {"fissions": s["fissions"], "denials": s["denials"],
                      "reflects": s["reflects"], "rules": list(s["rules"])}
                  for n,s in state.items()}
    return "\n".join(lines)

def main():
    if not os.path.exists(REPORT):
        with open(REPORT, "w") as f:
            f.write("# Colony Intelligence Report\n\nAuto-generated insights from colony monitoring.\n\n---\n")

    print(f"Monitoring every {INTERVAL}s. Appending insights to report.md. Ctrl+C to stop.")
    while True:
        state = analyze()
        if state:
            insight = deduce(state)
            with open(REPORT, "a", encoding="utf-8") as f:
                f.write(insight + "\n")
            total_f = sum(s["fissions"] for s in state.values())
            print(f"[{time.strftime('%H:%M:%S')}] Appended insight ({total_f} fissions total)")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] No events yet")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
