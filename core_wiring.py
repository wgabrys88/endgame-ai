import importlib.util
import pathlib
import re
from typing import Any, NamedTuple

ROOT = pathlib.Path(__file__).parent.resolve()

SENTINELS = {"halt"}


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default)
    raw = raw.replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_wiring(path: str | None = None) -> dict[str, Any]:
    source_path = root_path(path, "wiring.json").resolve()
    cfg = load_json(source_path)
    validate_wiring(cfg)
    problems = coherence_problems(cfg)
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
    selected_transport = _require(cfg, f"model.transport_config.{transport}", dict)
    _require(cfg, f"model.transport_config.{transport}.request", dict)
    _require(cfg, f"model.transport_config.{transport}.url", str)
    request_profiles = selected_transport.get("request_profiles", {})
    if not isinstance(request_profiles, dict) or not all(isinstance(name, str) and name and isinstance(body, dict) for name, body in request_profiles.items()):
        raise RuntimeError(f"wiring.model.transport_config.{transport}.request_profiles must map names to request objects")
    for path in (
        "model.global", "model.organs",
        "observe_config.hover_cache", "observe_config.hover_cache.scan", "observe_config.hover_cache.budget",
        "topology.edges",
    ):
        _require(cfg, path, dict)
    for path in (
        "paths.nodes",
        "paths.brains",
        "paths.guidance",
        "topology.cycle_start",
    ):
        _require(cfg, path, str)
    for path in (
        "observe_config.hover_cache.enabled",
    ):
        _require(cfg, path, bool)
    numeric_paths = (
        "observe_config.hover_cache.scan.step_px",
        "observe_config.hover_cache.scan.max_subtree_nodes_per_point",
        "observe_config.hover_cache.budget.line_preview_chars",
    )
    for path in numeric_paths:
        value = _require(cfg, path, int)
        if isinstance(value, bool) or value < 0 or (path.endswith(("step_px", "max_subtree_nodes_per_point")) and value == 0):
            raise RuntimeError(f"wiring.{path} must be a valid non-negative count")
    nodes = _require_list_str(cfg, "topology.nodes")
    edges = _require(cfg, "topology.edges", dict)
    _require(cfg, "prompts", dict)
    _require(cfg, "shared_prompt_prefix", str)
    templates = _require(cfg, "prompt_templates", dict)
    for key in ("living_word_header", "living_word_goal_row", "living_word_empty_row",
                "proven_ledger_empty", "proven_ledger_header", "standing_host_header"):
        if not isinstance(templates.get(key), str) or not templates[key].strip():
            raise RuntimeError(f"wiring.prompt_templates.{key} must be a non-empty string")
    validate_record_contracts(cfg)
    if len(nodes) != len(set(nodes)):
        raise RuntimeError("wiring.topology.nodes contains duplicates")
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
    missing = [node for node in nodes if node not in edges]
    if missing:
        raise RuntimeError(f"wiring missing edges for nodes: {missing}")


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


def _contract_coherence(w: dict[str, Any]) -> list[str]:
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
    return problems


def coherence_problems(w: dict[str, Any]) -> list[str]:
    """Return topology/contract incoherence reasons for wiring `w`. Empty = coherent."""
    topo = w["topology"]
    edges = topo["edges"]
    nodes = set(topo["nodes"])
    problems: list[str] = _contract_coherence(w)

    if topo["cycle_start"] not in nodes:
        problems.append(f"cycle_start '{topo['cycle_start']}' not in topology.nodes")

    for src, sigmap in edges.items():
        if src not in nodes:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, target in sigmap.items():
            if not isinstance(target, str) or not target:
                problems.append(f"{src}.{sig} has no valid target: {target!r}")
                continue
            if target not in SENTINELS and target not in nodes:
                problems.append(f"{src}.{sig} -> '{target}' is not a known node")
            if target in SENTINELS and sig != target:
                problems.append(f"{src}.{sig} targets terminal name '{target}' instead of emitting terminal signal '{target}'")

    node_dir = root_path(w["paths"]["nodes"])
    for n in nodes:
        if n not in edges:
            problems.append(f"node '{n}' has no edges")
        base = n.split(":", 1)[0]
        if not (node_dir / f"{base}.py").is_file():
            problems.append(f"node '{n}' has no plugin file {(node_dir / f'{base}.py')}")

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
    unreachable = nodes - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")
    return problems


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


class PluginKind(NamedTuple):
    paths_key: str
    module_prefix: str
    export: str


KINDS: dict[str, PluginKind] = {
    "node": PluginKind(paths_key="nodes", module_prefix="endgame_node_", export="run"),
    "transport": PluginKind(paths_key="brains", module_prefix="endgame_brain_transport_", export="call"),
}


def split_instance(name: str) -> tuple[str, str | None]:
    """Split "base:instance" -> ("base", "instance"). No colon -> (name, None)."""
    if ":" in name:
        base, instance = name.split(":", 1)
        if not base or not instance:
            raise RuntimeError(f"malformed plugin name '{name}': expected 'base:instance'")
        return base, instance
    return name, None


def load(kind: str, name: str, w: dict[str, Any]):
    """Resolve plugin `name` of `kind` to a module exporting the kind's contract.

    Returns the loaded module. Raises hard on missing dir key, missing file,
    unloadable spec, or missing exported symbol. No fallback.
    """
    spec_kind = KINDS.get(kind)
    if spec_kind is None:
        raise RuntimeError(f"unknown plugin kind '{kind}'; known: {', '.join(sorted(KINDS))}")
    base, _instance = split_instance(name)
    plugin_dir = root_path(w["paths"][spec_kind.paths_key])
    path = plugin_dir / f"{base}.py"
    if not path.exists():
        raise RuntimeError(f"{kind} plugin '{base}' has no module at {path}; no fallback was attempted")
    spec = importlib.util.spec_from_file_location(f"{spec_kind.module_prefix}{base}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {kind} plugin module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, spec_kind.export):
        raise RuntimeError(f"{kind} plugin '{base}' does not export {spec_kind.export}(...)")
    return mod
