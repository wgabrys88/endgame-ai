from __future__ import annotations

import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default)
    raw = raw.replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_wiring(path: str | None = None) -> dict[str, Any]:
    return load_json(root_path(path, "wiring.json"))


def load_json(path: pathlib.Path) -> dict[str, Any]:
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    import os
    import threading
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    import json
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring.get("model")
    if not isinstance(model, dict):
        raise RuntimeError("wiring.json missing object model")

    transport = str(model.get("transport") or "").strip()
    if not transport:
        raise RuntimeError("wiring model.transport is empty; no fallback transport is allowed")

    transport_config = model.get("transport_config", {})
    if not isinstance(transport_config, dict) or transport not in transport_config:
        raise RuntimeError(f"wiring model.transport_config.{transport} missing; no fallback transport config is allowed")
    cfg = dict(transport_config[transport])

    global_keys = {"timeout", "brain_call_budget"}
    global_cfg = model.get("global", {})
    for k in global_keys:
        if isinstance(global_cfg, dict) and k in global_cfg and k not in cfg:
            cfg[k] = global_cfg[k]
        if k in model and k not in cfg:
            cfg[k] = model[k]
    paths = wiring.get("paths", {})
    if isinstance(paths, dict):
        cfg.setdefault("event_log_path", paths.get("event_log") or "runtime_events.jsonl")

    cfg["transport"] = transport
    return transport, cfg


def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring.get("paths", {}).get("state"), "runtime_state.json")


def control_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring.get("paths", {}).get("control"), "runtime_control.json")


def event_log_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring.get("paths", {}).get("event_log"), "runtime_events.jsonl")


def request_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring.get("paths", {}).get("request"), "runtime_request.json")


def response_path(wiring: dict[str, Any]) -> pathlib.Path:
    return root_path(wiring.get("paths", {}).get("response"), "runtime_response.json")


def default_control(wiring: dict[str, Any]) -> dict[str, Any]:
    ctrl = dict(wiring.get("control_default") or {"mode": "run", "step_token": 0, "updated_at": 0})
    ctrl.setdefault("mode", "run")
    ctrl.setdefault("step_token", 0)
    ctrl.setdefault("updated_at", 0)
    return ctrl


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
    for key, default in [("state", "runtime_state.json"), ("control", "runtime_control.json")]:
        p = root_path(wiring.get("paths", {}).get(key), default)
        if p.exists():
            p.unlink()
    for key, default in [("request", "runtime_request.json"), ("response", "runtime_response.json")]:
        p = root_path(wiring.get("paths", {}).get(key), default)
        if p.exists():
            p.unlink()
    stop_check.clear_stop()
    stop_check.ensure_self_evolution_enabled(source="reset")


def topology_summary(w: dict[str, Any]) -> dict[str, Any]:
    topo = w.get("topology", {})
    return {
        "cycle_start": topo.get("cycle_start"),
        "nodes": list(topo.get("nodes", [])),
        "edges": topo.get("edges", {}),
    }


def topology_mermaid(w: dict[str, Any]) -> str:
    import core_bus as bus
    import core_node_base as nodes
    return bus.mermaid_state_diagram(w, nodes.node_datasheets(w))