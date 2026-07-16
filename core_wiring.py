import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default)
    raw = raw.replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_wiring(path: str | None = None) -> dict[str, Any]:
    source_path = root_path(path, "wiring.json").resolve()
    cfg = load_json(source_path)
    validate_wiring(cfg)
    import check_topology
    problems = check_topology.coherence_problems(cfg)
    if problems:
        raise RuntimeError(f"wiring topology is incoherent: {problems}")
    cfg["_source_path"] = str(source_path)
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
    for key in ("schema", "model", "paths", "observe_config", "topology", "prompts", "shared_prompt_prefix", "record_contracts"):
        if key not in cfg:
            raise RuntimeError(f"wiring missing required key: {key}")
    _obj(cfg, "model")
    transport = _require(cfg, "model.transport", str)
    transport_cfg = _require(cfg, "model.transport_config", dict)
    if transport not in transport_cfg:
        raise RuntimeError(f"wiring.model.transport_config missing selected transport {transport!r}")
    _require(cfg, f"model.transport_config.{transport}.request", dict)
    _require(cfg, f"model.transport_config.{transport}.url", str)
    for path in (
        "model.global", "model.organs",
        "observe_config.hover_cache", "observe_config.hover_cache.phases", "observe_config.hover_cache.scan", "observe_config.hover_cache.filter", "observe_config.hover_cache.budget",
        "topology.edges", "topology.barriers",
    ):
        _require(cfg, path, dict)
    for path in (
        "paths.nodes",
        "paths.brains",
        "paths.guidance",
        "observe_config.hover_cache.phases.scan",
        "observe_config.hover_cache.phases.filter",
        "observe_config.hover_cache.phases.build",
        "topology.cycle_start",
    ):
        _require(cfg, path, str)
    for path in (
        "observe_config.hover_cache.enabled",
        "observe_config.hover_cache.filter.require_interactive",
    ):
        _require(cfg, path, bool)
    numeric_paths = (
        "observe_config.hover_cache.scan.step_px",
        "observe_config.hover_cache.scan.max_subtree_nodes_per_point",
        "observe_config.hover_cache.scan.max_total_nodes",
        "observe_config.hover_cache.filter.max_elements",
        "observe_config.hover_cache.filter.max_per_window",
        "observe_config.hover_cache.filter.max_depth",
        "observe_config.hover_cache.filter.max_children_per_window",
        "observe_config.hover_cache.filter.max_llm_nodes",
        "observe_config.hover_cache.budget.line_preview_chars",
        "observe_config.hover_cache.budget.expand_char_budget",
    )
    for path in numeric_paths:
        value = _require(cfg, path, int)
        if isinstance(value, bool) or value < 0 or (path.endswith(("step_px", "max_subtree_nodes_per_point", "max_total_nodes", "max_elements", "max_per_window", "max_depth", "max_children_per_window", "max_llm_nodes", "expand_char_budget")) and value == 0):
            raise RuntimeError(f"wiring.{path} must be a valid non-negative count")
    nodes = _require_list_str(cfg, "topology.nodes")
    edges = _require(cfg, "topology.edges", dict)
    prompts = _require(cfg, "prompts", dict)
    _require(cfg, "shared_prompt_prefix", str)
    validate_record_contracts(cfg)
    if len(nodes) != len(set(nodes)):
        raise RuntimeError("wiring.topology.nodes contains duplicates")
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
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
        if "description" in defn and (not isinstance(defn["description"], str) or not defn["description"].strip()):
            raise RuntimeError(f"wiring.node_defs.{name}.description must be a non-empty string")



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


def prompt(cfg: dict[str, Any], key: str) -> str:
    prompts = cfg["prompts"]
    if key not in prompts:
        raise RuntimeError(f"wiring.prompts missing prompt: {key}")
    return str(cfg["shared_prompt_prefix"]).rstrip() + "\n\n" + str(prompts[key]).lstrip()


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring["model"]
    transport = model["transport"].strip()
    cfg = dict(model["transport_config"][transport])
    for key in ("timeout",):
        if key not in cfg:
            cfg[key] = model["global"][key]
    cfg["transport"] = transport
    return transport, cfg


def guidance_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["guidance"])
