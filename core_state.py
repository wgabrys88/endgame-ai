import time
from typing import Any

import core_wiring as wiring
import core_stop_check as stop_check
import core_bus as bus

def expire_duration(
    wiring_cfg: dict[str, Any],
    state: dict[str, Any],
    duration_seconds: float | None,
    node_name: str,
) -> dict[str, Any]:
    reason = f"duration_seconds expired after {duration_seconds:g}s" if duration_seconds is not None else "duration expired"
    state["_phase"] = "duration_expired"
    state["current_node"] = node_name
    state["stop_reason"] = reason
    wiring.write_state(wiring_cfg, state)
    stop_check.request_stop(reason, source="duration")
    runtime_event(
        wiring_cfg,
        "duration_expired",
        node=node_name,
        tick=state.get("tick"),
        duration_seconds=duration_seconds,
        stop_file=str(stop_check.STOP_FILE),
    )
    return state


def stop_file_detected(wiring_cfg: dict[str, Any], state: dict[str, Any], node_name: str) -> dict[str, Any]:
    state["_phase"] = "stop_requested"
    state["current_node"] = node_name
    state["stop_reason"] = f"stop file detected: {stop_check.STOP_FILE.name}"
    wiring.write_state(wiring_cfg, state)
    runtime_event(
        wiring_cfg,
        "stop_file_detected",
        node=node_name,
        tick=state.get("tick"),
        stop_file=str(stop_check.STOP_FILE),
    )
    return state


def duration_expired(deadline_at: float | None) -> bool:
    return deadline_at is not None and time.time() >= deadline_at


def runtime_event(wiring_cfg: dict[str, Any], event: str, **payload: Any) -> None:
    import core_brain as brain
    brain.log_runtime_event(wiring_cfg, event, **payload)


def classify_node_exception(node_name: str, exc: Exception) -> dict[str, Any]:
    message = str(exc)
    kind = "node_exception"
    contract_repair_allowed = False
    if node_name == "node_execute":
        kind = "execute_actor_failure"
    elif isinstance(exc, bus.TopologyContractError):
        kind = "topology_contract_violation"
        contract_repair_allowed = True
    elif isinstance(exc, bus.NodeRecordContractError):
        kind = "node_record_contract_violation"
        contract_repair_allowed = True
    elif node_name == "node_self_modify":
        kind = "self_modify_patch_contract_violation"
    elif node_name == "node_observe":
        kind = "observation_contract_violation"
        contract_repair_allowed = True
    return {
        "source": node_name,
        "kind": kind,
        "exception_type": type(exc).__name__,
        "message": message,
        "contract_repair_allowed": contract_repair_allowed,
    }


def wait_before_node(
    wiring_cfg: dict[str, Any],
    state: dict[str, Any],
    node_name: str,
    deadline_at: float | None = None,
) -> bool:
    entered_pause = False
    while True:
        if duration_expired(deadline_at):
            return False
        if stop_check.stop_requested():
            return False
        ctrl = wiring.read_control(wiring_cfg)
        mode = ctrl["mode"]
        token = int(ctrl.get("step_token", 0))
        if mode == "run":
            return True
        consumed = int(state.get("_last_step_token_consumed", -1))
        if mode == "step" and token > consumed:
            state["_last_step_token_consumed"] = token
            state["_phase"] = "stepping_node"
            state["current_node"] = node_name
            wiring.write_state(wiring_cfg, state)
            runtime_event(wiring_cfg, "step_consumed", node=node_name, step_token=token)
            return True
        if not entered_pause:
            state["_phase"] = "paused_before_node"
            state["current_node"] = node_name
            state["control_mode"] = mode
            wiring.write_state(wiring_cfg, state)
            runtime_event(wiring_cfg, "paused_before_node", node=node_name, mode=mode, step_token=token)
            entered_pause = True
        time.sleep(0.1)
