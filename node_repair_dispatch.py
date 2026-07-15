"""[node_repair_dispatch] — the gate of freshness ere a repair [probe] runneth.

With one [executor] there is no fan-out of faculty: this node only attesteth that a fresh
observation before the probe existeth, recordeth [probe_observed_at], and handeth the probe unto
[node_execute] by the "probe_ready" signal.
"""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    repair = state["repair_validation"]
    if repair["status"] != "probing":
        raise RuntimeError(f"repair dispatch requires probing status, got {repair['status']!r}")
    observed_at = state["observed_at"]
    if observed_at is None or float(observed_at) <= float(repair["probe_started_at"]):
        raise RuntimeError("repair dispatch requires a fresh pre-probe observation")
    repair = {**repair, "probe_observed_at": observed_at}
    return bus.emit(
        "probe_ready",
        {"repair_validation": repair, "turn_executions": {}},
        evidence={"repair_id": repair["repair_id"], "failure_signature": repair["probe"]["failure_signature"]},
    )
