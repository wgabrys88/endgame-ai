import pathlib
from typing import Any

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


def validate_wiring(cfg: dict[str, Any]) -> None:
    for key in ("schema", "model", "paths", "control_default", "observe_config", "self_modify", "topology", "prompts", "fractal"):
        if key not in cfg:
            raise RuntimeError(f"wiring missing required key: {key}")
    model = _obj(cfg, "model")
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
        "paths.control",
        "paths.event_log",
        "paths.guidance",
        "control_default.mode",
        "control_default.step_token",
        "control_default.updated_at",
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
        "fractal.child_duration_seconds",
    ):
        _require(cfg, path, object)
    nodes = _require(cfg, "topology.nodes", list)
    edges = _require(cfg, "topology.edges", dict)
    prompts = _require(cfg, "prompts", dict)
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
    missing = [node for node in nodes if node not in edges or node not in prompts]
    if missing:
        raise RuntimeError(f"wiring missing edges/prompts for nodes: {missing}")


def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    import os
    import threading
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    import json
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring["model"]
    transport = model["transport"].strip()
    cfg = dict(model["transport_config"][transport])
    for key in ("timeout", "brain_call_budget"):
        if key not in cfg:
            cfg[key] = model["global"][key]
    cfg["event_log_path"] = wiring["paths"]["event_log"]
    cfg["transport"] = transport
    return transport, cfg


def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["state"])


def control_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["control"])


def event_log_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["event_log"] if wiring else "runtime_events.jsonl")


def guidance_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring["paths"]["guidance"])


def default_control(wiring: dict[str, Any]) -> dict[str, Any]:
    return dict(wiring["control_default"])


def read_control(wiring: dict[str, Any]) -> dict[str, Any]:
    import time
    path = control_path(wiring)
    if not path.exists():
        ctrl = default_control(wiring)
        ctrl["updated_at"] = time.time()
        atomic_write_json(path, ctrl)
        return ctrl
    ctrl = load_json(path)
    mode = ctrl.get("mode")
    if mode not in {"run", "pause", "step"}:
        raise RuntimeError(f"invalid control mode in {path}: {mode!r}")
    try:
        ctrl["step_token"] = int(ctrl.get("step_token", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid step_token in {path}: {ctrl.get('step_token')!r}") from exc
    return ctrl


def write_state(wiring: dict[str, Any], state: dict[str, Any]) -> None:
    atomic_write_json(state_path(wiring), state)


def reset_runtime(wiring: dict[str, Any]) -> None:
    import core_stop_check as stop_check
    for key in ("state", "control"):
        p = root_path(wiring["paths"][key])
        if p.exists():
            p.unlink()
    stop_check.clear_stop()


def topology_summary(w: dict[str, Any]) -> dict[str, Any]:
    topo = w["topology"]
    return {
        "cycle_start": topo["cycle_start"],
        "nodes": list(topo["nodes"]),
        "edges": topo["edges"],
    }
