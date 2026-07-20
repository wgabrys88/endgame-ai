import json
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
SENTINELS = {"halt"}
_TEMPLATE_KEYS = (
    "living_word_header", "living_word_goal_row", "living_word_empty_row",
    "standing_host_header", "environment_screen_header",
)


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default).replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


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
        if not isinstance(types, dict) or not all(
            isinstance(key, str) and value in {"string", "boolean", "array", "object", "number", "integer"}
            for key, value in types.items()
        ):
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


def validate_wiring(cfg: dict[str, Any]) -> None:
    for key in ("schema", "model", "paths", "exploration", "topology", "prompts", "shared_prompt_prefix", "record_contracts"):
        if key not in cfg:
            raise RuntimeError(f"wiring missing required key: {key}")
    if not isinstance(cfg["model"], dict):
        raise RuntimeError("wiring.model must be object")
    transport = _require(cfg, "model.transport", str)
    transport_cfg = _require(cfg, "model.transport_config", dict)
    if transport not in transport_cfg:
        raise RuntimeError(f"wiring.model.transport_config missing selected transport {transport!r}")
    selected = _require(cfg, f"model.transport_config.{transport}", dict)
    _require(cfg, f"model.transport_config.{transport}.request", dict)
    _require(cfg, f"model.transport_config.{transport}.url", str)
    profiles = selected.get("request_profiles", {})
    if not isinstance(profiles, dict) or not all(isinstance(n, str) and n and isinstance(b, dict) for n, b in profiles.items()):
        raise RuntimeError(f"wiring.model.transport_config.{transport}.request_profiles must map names to request objects")
    _require(cfg, "model.global", dict)
    _require(cfg, "model.organs", dict)
    _require(cfg, "exploration", dict)
    _require(cfg, "topology.edges", dict)
    _require(cfg, "paths.guidance", str)
    _require(cfg, "topology.cycle_start", str)
    for path in ("exploration.step_px", "exploration.max_subtree_nodes_per_point", "exploration.max_environment_chars", "exploration.max_action_output_chars"):
        value = _require(cfg, path, int)
        if isinstance(value, bool) or value <= 0:
            raise RuntimeError(f"wiring.{path} must be a positive count")
    nodes = _require_list_str(cfg, "topology.nodes")
    _require(cfg, "prompts", dict)
    _require(cfg, "shared_prompt_prefix", str)
    templates = _require(cfg, "prompt_templates", dict)
    for key in _TEMPLATE_KEYS:
        if not isinstance(templates.get(key), str) or not templates[key].strip():
            raise RuntimeError(f"wiring.prompt_templates.{key} must be a non-empty string")
    validate_record_contracts(cfg)
    if len(nodes) != len(set(nodes)):
        raise RuntimeError("wiring.topology.nodes contains duplicates")
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
    missing = [node for node in nodes if node not in cfg["topology"]["edges"]]
    if missing:
        raise RuntimeError(f"wiring missing edges for nodes: {missing}")


def coherence_problems(w: dict[str, Any]) -> list[str]:
    import core_nodes as nodes

    topo = w["topology"]
    edges = topo["edges"]
    node_set = set(topo["nodes"])
    problems: list[str] = []
    try:
        validate_record_contracts(w)
    except Exception as exc:
        problems.append(f"record_contracts invalid: {type(exc).__name__}: {exc}")
        return problems
    contracts = w["record_contracts"]
    for prompt_key, text in w.get("prompts", {}).items():
        for record_type in re.findall(r"record_type '([^']+)'", str(text)):
            if record_type not in contracts:
                problems.append(f"prompt '{prompt_key}' names record_type '{record_type}' with no record_contracts entry")
    for record_type in w.get("model", {}).get("organs", {}):
        if record_type not in contracts:
            problems.append(f"model.organs.{record_type} has no record_contracts entry")
    if topo["cycle_start"] not in node_set:
        problems.append(f"cycle_start '{topo['cycle_start']}' not in topology.nodes")
    for src, sigmap in edges.items():
        if src not in node_set:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, target in sigmap.items():
            if not isinstance(target, str) or not target:
                problems.append(f"{src}.{sig} has no valid target: {target!r}")
                continue
            if target not in SENTINELS and target not in node_set:
                problems.append(f"{src}.{sig} -> '{target}' is not a known node")
            if target in SENTINELS and sig != target:
                problems.append(f"{src}.{sig} targets terminal name '{target}' instead of emitting terminal signal '{target}'")
    for n in node_set:
        if n not in edges:
            problems.append(f"node '{n}' has no edges")
        base = n.split(":", 1)[0]
        if base not in nodes.FACULTIES:
            problems.append(f"node '{n}' has no faculty in core_nodes.FACULTIES")
    seen: set[str] = set()
    stack = [topo["cycle_start"]]
    while stack:
        cur = stack.pop()
        if cur in seen or cur in SENTINELS:
            continue
        seen.add(cur)
        for target in edges.get(cur, {}).values():
            if isinstance(target, str) and target:
                stack.append(target)
    unreachable = node_set - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")
    return problems


def load_wiring(path: str | None = None) -> dict[str, Any]:
    source_path = root_path(path, "wiring.json").resolve()
    cfg = load_json(source_path)
    validate_wiring(cfg)
    problems = coherence_problems(cfg)
    if problems:
        raise RuntimeError(f"wiring topology is incoherent: {problems}")
    cfg["_source_path"] = str(source_path)
    return cfg


def prompt(cfg: dict[str, Any], key: str) -> str:
    prompts = cfg["prompts"]
    if key not in prompts:
        raise RuntimeError(f"wiring.prompts missing prompt: {key}")
    return str(cfg["shared_prompt_prefix"]).rstrip() + "\n\n" + str(prompts[key]).lstrip()


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring["model"]
    transport = model["transport"].strip()
    cfg = dict(model["transport_config"][transport])
    if "timeout" not in cfg:
        cfg["timeout"] = model["global"]["timeout"]
    cfg["transport"] = transport
    return transport, cfg
