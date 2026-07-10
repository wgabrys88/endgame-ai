import core_bus as bus


def run(ctx):
    state = ctx["state"]
    repair = state["repair_validation"]
    if repair["status"] != "probing":
        raise RuntimeError(f"repair dispatch requires probing status, got {repair['status']!r}")
    observed_at = state["observed_at"]
    if observed_at is None or float(observed_at) < float(repair["probe_started_at"]):
        raise RuntimeError("repair dispatch requires a fresh pre-probe observation")
    repair = {**repair, "probe_observed_at": observed_at}
    faculty = repair["probe"]["faculty"]
    target = f"node_execute:{faculty}"
    targets = list(ctx["wiring"]["topology"]["edges"][ctx["node"]]["dispatch"])
    if target not in targets:
        raise RuntimeError(f"repair probe faculty {faculty!r} has no wired execute target")
    return bus.emit(
        "dispatch",
        {
            "repair_validation": repair,
            "_dispatch_targets": [target],
            "_barrier_release_signal": "repair_join",
            "turn_executions": {},
        },
        evidence={
            "repair_id": repair["repair_id"],
            "failure_signature": repair["probe"]["failure_signature"],
            "faculty": faculty,
        },
    )
