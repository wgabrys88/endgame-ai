import time
from typing import Any

import core_wiring as wiring
import core_bus as bus
import core_loader as loader


def classify_node_exception(node_name: str, exc: Exception) -> dict[str, Any]:
    message = str(exc)
    kind = "node_exception"
    contract_repair_allowed = False
    node_base, _ = loader.split_instance(node_name)
    if node_base == "node_execute":
        kind = "execute_actor_failure"
    elif isinstance(exc, bus.TopologyContractError):
        kind = "topology_contract_violation"
        contract_repair_allowed = True
    elif isinstance(exc, bus.NodeRecordContractError):
        kind = "node_record_contract_violation"
        contract_repair_allowed = True
    elif node_base == "node_self_modify":
        kind = "self_modify_patch_contract_violation"
    elif node_base == "node_observe":
        kind = "observation_contract_violation"
        contract_repair_allowed = True
    return {
        "source": node_name,
        "kind": kind,
        "exception_type": type(exc).__name__,
        "message": message,
        "contract_repair_allowed": contract_repair_allowed,
    }
