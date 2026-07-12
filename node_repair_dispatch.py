"""node_repair_dispatch — freshness gate before a repair probe runs.

With one executor there is no faculty fan-out: this node only asserts a fresh
pre-probe observation exists, records probe_observed_at, and hands the probe to
node_execute via "probe_ready".
"""
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
    return bus.emit(
        "probe_ready",
        {"repair_validation": repair, "turn_executions": {}},
        evidence={"repair_id": repair["repair_id"], "failure_signature": repair["probe"]["failure_signature"]},
    )
