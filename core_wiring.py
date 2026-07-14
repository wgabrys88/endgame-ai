import pathlib
from typing import Any

from io_helpers import atomic_write_json, replace_with_retry

ROOT = pathlib.Path(__file__).parent.resolve()


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default)
    raw = raw.replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_wiring(path: str | None = None) -> dict[str, Any]:
    cfg = load_json(root_path(path, "wiring.json"))
    validate_wiring(cfg)
    return cfg


def load_json(path: pathlib.Path) -> dict[str, Any]:
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


def _obj(obj: dict[str, Any], key: str) -> dict[str, Any]:
    value = obj[key]
    if not isinstance(value, dict):
        raise RuntimeError(f"wiring.{key} must be object")
    return value


def _require(obj: dict[str, Any], path: str, typ: type | tuple[type, ...]) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise RuntimeError(f"wiring missing required key: {path}")
        cur = cur[part]
    if not isinstance(cur, typ):
        raise RuntimeError(f"wiring.{path} must be {typ}")
    return cur



def _require_list_str(obj: dict[str, Any], path: str) -> list[str]:
    value = _require(obj, path, list)
    if not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"wiring.{path} must be list[str]")
    return value

def validate_wiring(cfg: dict[str, Any]) -> None:
    for key in ("schema", "model", "paths", "observe_config", "self_modify", "topology", "prompts", "prompt_aliases", "shared_prompt_prefix", "record_contracts", "capabilities", "fractal"):
        if key not in cfg:
            raise RuntimeError(f"wiring missing required key: {key}")
    _obj(cfg, "model")
    transport = _require(cfg, "model.transport", str)
    transport_cfg = _require(cfg, "model.transport_config", dict)
    if transport not in transport_cfg:
        raise RuntimeError(f"wiring.model.transport_config missing selected transport {transport!r}")
    if transport == "transport_file_proxy":
        _require(cfg, "model.transport_config.transport_file_proxy.request_path", str)
        _require(cfg, "model.transport_config.transport_file_proxy.response_path", str)
        _require(cfg, "model.transport_config.transport_file_proxy.poll_interval", (int, float))
    for path in (
        "model.global",
        "model.stable_prefix",
        "model.organs",
        "paths.nodes",
        "paths.brains",
        "paths.caps",
        "paths.state",
        "paths.guidance",
        "observe_config.hover_cache.enabled",
        "observe_config.hover_cache.scan.step_px",
        "observe_config.hover_cache.scan.delay_ms",
        "observe_config.hover_cache.scan.max_subtree_nodes_per_point",
        "observe_config.hover_cache.scan.max_total_nodes",
        "observe_config.hover_cache.filter.max_elements",
        "observe_config.hover_cache.filter.max_per_window",
        "observe_config.hover_cache.filter.max_text",
        "observe_config.hover_cache.filter.require_interactive",
        "self_modify.context_mode",
        "self_modify.known_good_ref",
        "self_modify.hot_swap_on_failure",
        "self_modify.execution.rollback_on_failure",
        "self_modify.git.remote",
        "self_modify.git.push_after_commit",
        "self_modify.web_search",
        "topology.cycle_start",
        "topology.nodes",
        "topology.edges",
        "topology.barriers",
        "fractal.max_recursion_depth",
        "model.stable_prefix.source",
        "model.stable_prefix.source.suffixes",
        "model.stable_prefix.source.names",
        "model.stable_prefix.source.skip_parts",
        "model.stable_prefix.source.skip_prefixes",
        "self_modify.evolvable",
        "self_modify.evolvable.suffixes",
        "self_modify.evolvable.names",
        "self_modify.evolvable.skip_prefixes",
        "self_modify.evolvable.activation",
        "self_modify.evolvable.activation.immediate",
        "self_modify.evolvable.activation.next_run",
    ):
        _require(cfg, path, object)
    nodes = _require_list_str(cfg, "topology.nodes")
    edges = _require(cfg, "topology.edges", dict)
    prompts = _require(cfg, "prompts", dict)
    aliases = _require(cfg, "prompt_aliases", dict)
    _require(cfg, "shared_prompt_prefix", str)
    validate_record_contracts(cfg)
    _require(cfg, "capabilities.schema", str)
    _require(cfg, "capabilities.power", str)
    _require(cfg, "capabilities.helpers", dict)
    _require(cfg, "capabilities.faculties", dict)
    _require_list_str(cfg, "capabilities.modules")
    _require_list_str(cfg, "capabilities.state")
    _require_list_str(cfg, "capabilities.signals")
    _require_list_str(cfg, "model.stable_prefix.source.suffixes")
    _require_list_str(cfg, "model.stable_prefix.source.names")
    _require_list_str(cfg, "model.stable_prefix.source.skip_parts")
    _require_list_str(cfg, "model.stable_prefix.source.skip_prefixes")
    _require_list_str(cfg, "self_modify.evolvable.suffixes")
    _require_list_str(cfg, "self_modify.evolvable.names")
    _require_list_str(cfg, "self_modify.evolvable.skip_prefixes")
    _require_list_str(cfg, "self_modify.evolvable.activation.immediate")
    _require_list_str(cfg, "self_modify.evolvable.activation.next_run")
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
    for alias, target in aliases.items():
        if not isinstance(alias, str) or not isinstance(target, str) or target not in prompts:
            raise RuntimeError(f"wiring.prompt_aliases.{alias} must name an existing prompt")
    missing = [node for node in nodes if node not in edges]
    if missing:
        raise RuntimeError(f"wiring missing edges for nodes: {missing}")
    validate_node_defs(cfg, prompts)


def validate_node_defs(cfg: dict[str, Any], prompts: dict[str, Any]) -> None:
    node_defs = cfg.get("node_defs", {})
    if not isinstance(node_defs, dict):
        raise RuntimeError("wiring.node_defs must be object")
    for name, defn in node_defs.items():
        if not isinstance(defn, dict):
            raise RuntimeError(f"wiring.node_defs.{name} must be object")
        for key in ("prompt_key", "expected_record_type", "signal_source", "build_payload", "evidence", "patch"):
            if key not in defn:
                raise RuntimeError(f"wiring.node_defs.{name} missing required key: {key}")
        if defn["prompt_key"] not in prompts:
            raise RuntimeError(f"wiring.node_defs.{name}.prompt_key names missing prompt {defn['prompt_key']!r}")
        if not isinstance(defn["expected_record_type"], str) or not defn["expected_record_type"]:
            raise RuntimeError(f"wiring.node_defs.{name}.expected_record_type must be non-empty string")
        if not isinstance(defn["signal_source"], str) or not defn["signal_source"]:
            raise RuntimeError(f"wiring.node_defs.{name}.signal_source must be non-empty string")



def validate_record_contracts(cfg: dict[str, Any]) -> None:
    contracts = _require(cfg, "record_contracts", dict)
    for record_type, contract in contracts.items():
        if not isinstance(record_type, str) or not record_type:
            raise RuntimeError(f"wiring.record_contracts key must be non-empty string: {record_type!r}")
        if not isinstance(contract, dict):
            raise RuntimeError(f"wiring.record_contracts.{record_type} must be object")
        required = contract.get("required")
        enums = contract.get("enums")
        types = contract.get("types", {})
        non_empty = contract.get("non_empty", [])
        additional_properties = contract.get("additional_properties", True)
        if not isinstance(required, list) or not all(isinstance(key, str) and key for key in required):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.required must be list[str]")
        if not isinstance(enums, dict):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.enums must be object")
        if not isinstance(types, dict) or not all(isinstance(key, str) and value in {"string", "boolean", "array", "object", "number", "integer"} for key, value in types.items()):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.types must map keys to supported JSON types")
        if not isinstance(non_empty, list) or not all(isinstance(key, str) and key for key in non_empty):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.non_empty must be list[str]")
        if not isinstance(additional_properties, bool):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.additional_properties must be boolean")
        known = set(required) | set(enums) | set(types)
        if not set(non_empty) <= known:
            raise RuntimeError(f"wiring.record_contracts.{record_type}.non_empty names unknown keys")
        for key, values in enums.items():
            if not isinstance(key, str) or not key:
                raise RuntimeError(f"wiring.record_contracts.{record_type}.enums key must be non-empty string")
            if not isinstance(values, list) or not values:
                raise RuntimeError(f"wiring.record_contracts.{record_type}.enums.{key} must be non-empty list")
    for record_type in cfg.get("model", {}).get("organs", {}):
        if record_type not in contracts:
            raise RuntimeError(f"wiring.model.organs.{record_type} has no matching wiring.record_contracts entry")


def prompt_name(cfg: dict[str, Any], key: str) -> str:
    aliases = cfg["prompt_aliases"]
    return aliases[key] if key in aliases else key


def prompt(cfg: dict[str, Any], key: str) -> str:
    name = prompt_name(cfg, key)
    prompts = cfg["prompts"]
    if name not in prompts:
        raise RuntimeError(f"wiring.prompts missing prompt: {key}")
    return str(cfg["shared_prompt_prefix"]) + str(prompts[name])


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring["model"]
    transport = model["transport"].strip()
    cfg = dict(model["transport_config"][transport])
    for key in ("timeout", "brain_call_budget"):
        if key not in cfg:
            cfg[key] = model["global"][key]
    cfg["transport"] = transport
    return transport, cfg


def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["state"])


def guidance_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["guidance"])


def write_state(wiring: dict[str, Any], state: dict[str, Any]) -> None:
    atomic_write_json(state_path(wiring), state)


def reset_runtime(wiring: dict[str, Any]) -> None:
    p = root_path(wiring["paths"]["state"])
    if p.exists():
        p.unlink()


def topology_summary(w: dict[str, Any]) -> dict[str, Any]:
    topo = w["topology"]
    return {
        "cycle_start": topo["cycle_start"],
        "nodes": list(topo["nodes"]),
        "edges": topo["edges"],
    }
