from __future__ import annotations

from abc import ABC
from typing import Any

import core_bus as bus
import core_brain as brain
import core_wiring as wiring
import core_state as state

JsonDict = dict[str, Any]


class BaseNode(ABC):
    """Unified base class for all LLM-driven nodes. Single source of truth for think/build_payload/signal/patch."""

    prompt_key: str = ""
    expected_record_type: str = ""
    request_config: JsonDict | None = None

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        st = ctx.get("state", {})
        return {
            "goal": ctx.get("goal", ""),
            "state": state.state_brief(st),
            "fresh_observation": st.get("fresh_observation") or state.observation_brief(st),
        }

    def evidence(self, ctx: JsonDict) -> JsonDict:
        return {"state": state.state_brief(ctx.get("state", {}))}

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: JsonDict) -> bus.Record:
        w = ctx["wiring"]
        prompt = w.get("prompts", {}).get(self.prompt_key, "")
        think_kwargs: JsonDict = {"expected_record_type": self.expected_record_type}
        if self.request_config is not None:
            think_kwargs["request_config"] = self.request_config
        record = brain.think(prompt, self.build_payload(ctx), w, **think_kwargs)
        if record.get("record_type") != self.expected_record_type:
            raise bus.NodeRecordContractError(
                f"{self.prompt_key} expected record_type {self.expected_record_type!r}, "
                f"got {record.get('record_type')!r}"
            )
        return bus.Record.from_json(record)

    def run(self, ctx: JsonDict) -> bus.NodeOutput:
        record = self.think(ctx)
        data = record.data
        signal = self.signal_from_data(data, ctx)
        patch = self.patch_from_record(record, ctx)
        return bus.emit(signal, patch, record=record, evidence=self.evidence(ctx))


def call_node(node_name: str, ctx: JsonDict) -> tuple[str, JsonDict]:
    w = ctx["wiring"]
    mod = _load_node(node_name, w)
    result = mod.run(ctx)
    output = bus.coerce_node_output(node_name, result)
    bus.validate_signal(w, node_name, output.signal)
    patch = dict(output.patch)
    patch.setdefault("_last_bus_frame", output.trace(node=node_name))
    sheet = getattr(mod, "DATASHEET", None)
    if isinstance(sheet, dict):
        patch.setdefault("_last_datasheet", dict(sheet))
    return output.signal, patch


def _load_node(node_name: str, w: JsonDict):
    import importlib.util
    node_dir = wiring.root_path(w.get("paths", {}).get("nodes"), ".")
    path = node_dir / f"{node_name}.py"
    if not path.exists():
        raise RuntimeError(f"topology node '{node_name}' has no module at {path}")
    spec = importlib.util.spec_from_file_location(f"endgame_node_{node_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load node module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise RuntimeError(f"node '{node_name}' does not export run(ctx)")
    return mod


def topology_summary(w: JsonDict) -> JsonDict:
    topo = w.get("topology", {})
    return {
        "cycle_start": topo.get("cycle_start"),
        "nodes": list(topo.get("nodes", [])),
        "edges": topo.get("edges", {}),
    }


def node_datasheets(w: JsonDict) -> dict[str, JsonDict]:
    sheets: dict[str, JsonDict] = {}
    for node_name in w.get("topology", {}).get("nodes", []):
        try:
            mod = _load_node(str(node_name), w)
        except Exception:
            continue
        sheet = getattr(mod, "DATASHEET", None)
        if isinstance(sheet, dict):
            sheets[str(node_name)] = dict(sheet)
    return sheets


def topology_mermaid(w: JsonDict) -> str:
    return bus.mermaid_state_diagram(w, node_datasheets(w))