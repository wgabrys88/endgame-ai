#!/usr/bin/env python3
"""Colony status report — run: python status.py"""
import json, os, time, glob
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

def load_events(name):
    path = f"events-child-{name}.jsonl"
    if not os.path.exists(path):
        return []
    events = []
    with open(path) as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except:
                pass
    return events

def analyze_agent(name, events):
    if not events:
        return None
    stats = {
        "name": name, "total": len(events), "fissions": 0, "confirms": 0,
        "denials": 0, "reflects": 0, "errors": 0, "timeouts": 0,
        "blocked": 0, "unique_obs": set(), "rules": [], "denial_reasons": [],
        "last_phase": "", "last_obs": "", "verbs": Counter(),
        "success_rate": 0.0, "exec_count": 0, "exec_ok": 0,
        "elapsed_s": 0.0, "events_per_min": 0.0,
    }

    t0 = events[0].get("t", "")
    t1 = events[-1].get("t", "")
    stats["last_phase"] = events[-1].get("phase", "")

    for e in events:
        p = e.get("phase", "")
        d = e.get("d") or {}

        if p == "fission":
            stats["fissions"] += 1
        elif p == "verify":
            v = d.get("verdict", "")
            if v == "confirmed":
                stats["confirms"] += 1
            elif v == "denied":
                stats["denials"] += 1
                stats["denial_reasons"].append(d.get("evidence", "")[:80])
        elif p == "reflect":
            stats["reflects"] += 1
            rule = d.get("rule", "").strip()
            if rule:
                stats["rules"].append(rule)
        elif "error" in p:
            stats["errors"] += 1
        elif p == "actor":
            verb = d.get("verb", "python")
            stats["verbs"][verb] += 1
            stats["exec_count"] += 1
            if d.get("ok"):
                stats["exec_ok"] += 1
            obs = d.get("obs", "")
            if obs and "no output" not in obs.lower() and obs not in ("ok",):
                stats["unique_obs"].add(obs[:100])
            if "timeout" in str(obs):
                stats["timeouts"] += 1
            stats["last_obs"] = obs[:120]
        elif p == "plan":
            if d.get("mode") == "blocked":
                stats["blocked"] += 1

    if stats["exec_count"]:
        stats["success_rate"] = stats["exec_ok"] / stats["exec_count"]

    # Time calc from ISO timestamps
    try:
        from datetime import datetime, timezone
        dt0 = datetime.fromisoformat(t0)
        dt1 = datetime.fromisoformat(t1)
        stats["elapsed_s"] = (dt1 - dt0).total_seconds()
        if stats["elapsed_s"] > 0:
            stats["events_per_min"] = len(events) / (stats["elapsed_s"] / 60)
    except:
        pass

    return stats

def dedupe_rules(rules):
    """Keep unique-ish rules (no near-duplicates)."""
    seen = []
    for r in rules:
        low = r.lower()[:60]
        if not any(low[:40] in s for s in seen):
            seen.append(low)
            yield r

def main():
    files = sorted(glob.glob("events-child-*.jsonl"))
    names = [f.replace("events-child-", "").replace(".jsonl", "") for f in files]

    if not names:
        print("No event files found. Colony hasn't run yet.")
        return

    agents = []
    for name in names:
        events = load_events(name)
        s = analyze_agent(name, events)
        if s:
            agents.append(s)

    print("=" * 72)
    print(f"COLONY STATUS — {len(agents)} agents | {time.strftime('%H:%M:%S')}")
    print("=" * 72)

    # Summary table
    print(f"\n{'Agent':<5} {'Evts':>5} {'F':>2} {'C':>2} {'D':>3} {'R':>2} {'Blk':>3} {'TO':>3} {'Succ%':>5} {'e/min':>5} {'Phase':<12}")
    print("-" * 72)
    totals = Counter()
    for s in agents:
        print(f"{s['name']:<5} {s['total']:>5} {s['fissions']:>2} {s['confirms']:>2} "
              f"{s['denials']:>3} {s['reflects']:>2} {s['blocked']:>3} {s['timeouts']:>3} "
              f"{s['success_rate']*100:>4.0f}% {s['events_per_min']:>5.1f} {s['last_phase']:<12}")
        for k in ('total','fissions','confirms','denials','reflects','blocked','timeouts','exec_count','exec_ok'):
            totals[k] += s.get(k, 0)

    sr = f"{totals['exec_ok']/totals['exec_count']*100:.0f}%" if totals['exec_count'] else "n/a"
    print("-" * 72)
    print(f"{'TOTAL':<5} {totals['total']:>5} {totals['fissions']:>2} {totals['confirms']:>2} "
          f"{totals['denials']:>3} {totals['reflects']:>2} {totals['blocked']:>3} {totals['timeouts']:>3} "
          f"{sr:>5}")

    # Top denial reasons
    all_denials = []
    for s in agents:
        all_denials.extend(s["denial_reasons"])
    if all_denials:
        print(f"\nTOP DENIAL REASONS ({len(all_denials)} total):")
        for reason, count in Counter(all_denials).most_common(5):
            print(f"  {count}x {reason}")

    # Unique lessons learned
    all_rules = []
    for s in agents:
        all_rules.extend(s["rules"])
    unique = list(dedupe_rules(all_rules))
    if unique:
        print(f"\nLESSONS LEARNED ({len(all_rules)} total, {len(unique)} unique):")
        for r in unique[:10]:
            print(f"  • {r[:90]}")

    # Real output produced
    all_obs = set()
    for s in agents:
        all_obs.update(s["unique_obs"])
    if all_obs:
        print(f"\nREAL OUTPUT ({len(all_obs)} unique observations):")
        for o in list(all_obs)[:8]:
            print(f"  → {o}")

    # Blocked plans
    total_blocked = totals['blocked']
    if total_blocked:
        print(f"\nBLOCKADE: {total_blocked} plans blocked (denial decay working)")

    # Health warnings
    print("\nHEALTH:")
    for s in agents:
        issues = []
        if s["timeouts"] > 3:
            issues.append(f"⚠ {s['timeouts']} timeouts")
        if s["denials"] > 10 and s["confirms"] == 0:
            issues.append(f"⚠ {s['denials']} denials, 0 confirms")
        if s["exec_count"] > 10 and s["success_rate"] < 0.3:
            issues.append(f"⚠ {s['success_rate']*100:.0f}% success rate")
        if s["total"] > 50 and s["fissions"] == 0 and s["reflects"] == 0:
            issues.append("⚠ no progress or learning")
        if issues:
            print(f"  {s['name']}: {' | '.join(issues)}")
    if not any(s["timeouts"] > 3 or (s["denials"] > 10 and s["confirms"] == 0) for s in agents):
        print("  ✓ No critical issues")

if __name__ == "__main__":
    main()
