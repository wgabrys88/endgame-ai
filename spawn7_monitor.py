"""Monitor 7 L3 agents: fissions, mutations, comms, errors."""
import json, os, glob, time, sys

BASE = os.path.dirname(os.path.abspath(__file__))
COMMS = os.path.join(BASE, "runtime", "comms")

def scan():
    files = sorted(glob.glob(os.path.join(BASE, "events-child-l3-*.jsonl")))
    total_fissions = 0
    total_mutations = 0
    total_errors = 0
    agents = []

    for f in files:
        name = os.path.basename(f)
        try:
            events = [json.loads(l) for l in open(f) if l.strip()]
        except:
            agents.append(f"  {name}: UNREADABLE")
            continue

        fissions = [e for e in events if e.get("phase") == "fission"]
        mutations = [e for e in events if e.get("phase") == "mutation"]
        actors_ok = [e for e in events if e.get("phase") == "actor" and e.get("d", {}).get("ok")]
        actors_fail = [e for e in events if e.get("phase") == "actor" and not e.get("d", {}).get("ok", True)]
        stopped = [e for e in events if e.get("phase") == "stop"]

        total_fissions += len(fissions)
        total_mutations += len(mutations)
        total_errors += len(actors_fail)

        status = "STOPPED" if stopped else "RUNNING"
        power = fissions[-1]["d"]["power"] if fissions else 0
        last_obs = actors_ok[-1]["d"]["obs"][:60] if actors_ok else "-"

        agents.append(f"  {name}: {len(events)}ev {len(fissions)}F {len(mutations)}M {status} p={power:.3f} [{last_obs}]")

    # Check comms channel
    comms_files = glob.glob(os.path.join(COMMS, "agent-*.json")) if os.path.isdir(COMMS) else []

    print(f"\n{'='*60}")
    print(f"  ENDGAME MONITOR — {time.strftime('%H:%M:%S')}")
    print(f"  Fissions: {total_fissions}  Mutations: {total_mutations}  Errors: {total_errors}")
    print(f"  Comms channel: {len(comms_files)} agents registered")
    print(f"{'='*60}")
    for a in agents:
        print(a)

    # Show recent mutations
    if total_mutations:
        print(f"\n  MUTATIONS:")
        for f in files:
            try:
                events = [json.loads(l) for l in open(f) if l.strip()]
            except:
                continue
            for e in events:
                if e.get("phase") == "mutation":
                    d = e.get("d", {})
                    print(f"    {os.path.basename(f)} n={e['n']}: {json.dumps(d)[:100]}")

    # Show README if exists
    readme = os.path.join(COMMS, "README.md")
    if os.path.exists(readme):
        lines = open(readme).readlines()
        print(f"\n  README.md: {len(lines)} lines")

    return total_fissions

if "--watch" in sys.argv:
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        scan()
        time.sleep(5)
else:
    scan()
