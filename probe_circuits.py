"""Probe each LLM circuit in isolation — real prompts, no graph engine, no desktop.

Usage:
  python probe_circuits.py                    # all circuits, state.json fixture
  python probe_circuits.py planner unified    # specific circuits
  python probe_circuits.py --dry all          # print prompts only, no LLM
  python probe_circuits.py probe_fixtures/shakira_clean.json unified
"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "probe_results"
CIRCUITS = ["planner", "unified", "verifier", "reflector", "self_modify"]
EXPECTED = {
    "planner": "task",
    "unified": "action",
    "verifier": "verdict",
    "reflector": "diagnosis",
    "self_modify": "wiring_patch",
}


def _import_server():
    sys.path.insert(0, str(ROOT))
    import server as srv
    return srv


def load_fixture(path=None):
    p = pathlib.Path(path) if path else ROOT / "state.json"
    if not p.is_absolute():
        p = ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


def probe(srv, circuit, state, dry=False, save=True):
    system = srv.load_system_prompt(circuit, state)
    user = srv.build_user_message(circuit, state)
    header = f"\n{'='*60}\nCIRCUIT: {circuit}  (expect record_type={EXPECTED.get(circuit)})\n{'='*60}"
    print(header)
    print(f"SYSTEM ({len(system)} chars)")
    print(system)
    print(f"\nUSER ({len(user)} chars)")
    print(user)

    result = {
        "circuit": circuit,
        "expected_record_type": EXPECTED.get(circuit),
        "fixture_goal": state.get("goal"),
        "step_goal": state.get("step_goal"),
        "system": system,
        "user": user,
        "dry_run": dry,
    }

    if dry:
        print("\n[DRY RUN — no LLM call]")
        return result

    t0 = time.time()
    content, reasoning, elapsed = srv.llm(system, user)
    parsed_content = srv.extract_json(content)
    parsed_reasoning = srv.extract_json(reasoning) if reasoning else None
    parsed = parsed_content or parsed_reasoning
    record_type = (parsed or {}).get("record_type")
    ok = record_type == EXPECTED.get(circuit)

    result.update({
        "content": content,
        "reasoning_content": reasoning or "",
        "parsed_from": "content" if parsed_content else ("reasoning" if parsed_reasoning else None),
        "parsed": parsed,
        "record_type": record_type,
        "record_type_ok": ok,
        "elapsed_s": round(elapsed, 1),
    })

    print(f"\n--- RESPONSE ({elapsed:.1f}s) record_type_ok={ok} ---")
    print(f"CONTENT:\n{content}")
    print(f"\nREASONING_CONTENT:\n{reasoning or '(none)'}")
    print(f"\nPARSED ({result['parsed_from']}): {json.dumps(parsed, indent=2) if parsed else None}")

    if save:
        OUT.mkdir(exist_ok=True)
        (OUT / f"{circuit}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    return result


def main():
    args = sys.argv[1:]
    dry = False
    if "--dry" in args:
        dry = True
        args = [a for a in args if a != "--dry"]

    fixture_path = None
    if args and args[0].endswith(".json"):
        fixture_path = args[0]
        args = args[1:]

    circuits = CIRCUITS if not args or args == ["all"] else args
    for c in circuits:
        if c not in CIRCUITS:
            print(f"Unknown circuit: {c}. Choose from: {', '.join(CIRCUITS)}")
            sys.exit(1)

    state = load_fixture(fixture_path)
    srv = _import_server()
    print(f"Fixture: {fixture_path or 'state.json'}")
    print(f"Goal: {state.get('goal')}")
    print(f"Step: {state.get('step')} step_goal={state.get('step_goal')!r}")

    summary = []
    for circuit in circuits:
        r = probe(srv, circuit, state, dry=dry)
        summary.append({
            "circuit": circuit,
            "record_type": r.get("record_type"),
            "record_type_ok": r.get("record_type_ok"),
            "elapsed_s": r.get("elapsed_s"),
            "reasoning_len": len(r.get("reasoning_content") or ""),
            "content_len": len(r.get("content") or ""),
        })

    summary_path = OUT / "summary.json"
    OUT.mkdir(exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{'='*60}\nSUMMARY\n{'='*60}")
    for s in summary:
        print(f"  {s['circuit']:12} ok={s.get('record_type_ok')} type={s.get('record_type')} reasoning={s.get('reasoning_len',0)}ch elapsed={s.get('elapsed_s','-')}s")
    print(f"\nSaved: {OUT}/")


if __name__ == "__main__":
    main()