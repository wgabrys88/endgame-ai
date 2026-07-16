from abc import ABC
from typing import Any

import core_bus as bus
import core_brain as brain
import core_loader as loader
import core_wiring as wiring

JsonDict = dict[str, Any]


class BaseNode(ABC):
    """Unified base class for all LLM-driven nodes. Single source of truth for think/build_payload/signal/patch."""

    prompt_key: str = ""
    expected_record_type: str = ""
    body_override: JsonDict | None = None

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        st = ctx.get("state", {})
        return {
            "goal": ctx.get("goal", ""),
            "state": bus.state_brief(st),
            "observation": bus.observation_brief(st),
        }

    def evidence(self, ctx: JsonDict) -> JsonDict:
        return {"state": bus.state_brief(ctx.get("state", {}))}

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: JsonDict) -> bus.Record:
        w = ctx["wiring"]
        prompt = wiring.prompt(w, self.prompt_key)
        think_kwargs: JsonDict = {"expected_record_type": self.expected_record_type, "emitting_node": ctx.get("node")}
        if self.body_override is not None:
            think_kwargs["body_override"] = self.body_override
        payload = self.build_payload(ctx)
        payload["goal"] = ctx["state"]["goal"]
        record = brain.think(prompt, payload, w, **think_kwargs)
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


_HELPERS = {
    "bus.state_brief": bus.state_brief,
    "bus.observation_brief": bus.observation_brief,
    "bus.execution_evidence": bus.execution_evidence,
}


def _lookup(scope: JsonDict, path: str) -> Any:
    cur: Any = scope
    for part in path.split("."):
        cur = cur[part]
    return cur


def _resolve(spec: Any, scope: JsonDict) -> Any:
    if isinstance(spec, dict):
        if "path" in spec:
            return _lookup(scope, spec["path"])
        if "call" in spec:
            return _HELPERS[spec["call"]](_resolve(spec["arg"], scope))
        if "format" in spec:
            return spec["format"].format(*[_resolve(a, scope) for a in spec["args"]])
        if "pick" in spec:
            source = _resolve(spec["pick"], scope)
            return {key: source[key] for key in spec["keys"]}
        if "int" in spec:
            return int(_resolve(spec["int"], scope) or spec.get("default", 0))
        if "interpret" in spec:
            return bus.with_interpretation(_resolve(spec["interpret"], scope), spec["faculty"], _resolve(spec["sentence"], scope))
        if "get" in spec:
            source = _resolve(spec["get"], scope)
            value = source.get(spec["key"]) if isinstance(source, dict) else None
            return value if value not in (None, "") else _resolve(spec["default"], scope)
        return {key: _resolve(value, scope) for key, value in spec.items()}
    if isinstance(spec, list):
        return [_resolve(item, scope) for item in spec]
    return spec


class DeclarativeNode(BaseNode):
    """A node whose think->signal->patch behavior is fully described by JSON data."""

    def __init__(self, definition: JsonDict) -> None:
        self._def = definition
        self.prompt_key = definition["prompt_key"]
        self.expected_record_type = definition["expected_record_type"]
        self.body_override = definition.get("body_override")

    def _scope(self, ctx: JsonDict, *, data: JsonDict | None = None, record: bus.Record | None = None, signal: str | None = None) -> JsonDict:
        st = ctx["state"]
        return {
            "state": st,
            "goal": st["goal"],
            "node": ctx.get("node"),
            "node_instance": ctx.get("node_instance"),
            "data": data or {},
            "record": {"reasoning": record.reasoning} if record is not None else {},
            "signal": signal,
        }

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        return _resolve(self._def["build_payload"], self._scope(ctx))

    def evidence(self, ctx: JsonDict) -> JsonDict:
        return _resolve(self._def["evidence"], self._scope(ctx))

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        signal = str(_lookup({"data": data}, self._def["signal_source"]))
        self._signal = signal
        return signal

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        scope = self._scope(ctx, data=record.data, record=record, signal=self._signal)
        return _resolve(self._def["patch"], scope)


def call_node(node_name: str, ctx: JsonDict) -> tuple[str, JsonDict]:
    w = ctx["wiring"]
    base, instance = loader.split_instance(node_name)
    ctx = {**ctx, "node": node_name, "node_base": base, "node_instance": instance}
    node_defs = w.get("node_defs", {})
    if node_name in node_defs or base in node_defs:
        definition = node_defs.get(node_name) or node_defs[base]
        result = DeclarativeNode(definition).run(ctx)
    else:
        mod = loader.load("node", node_name, w)
        result = mod.run(ctx)
    output = bus.coerce_node_output(node_name, result)
    bus.validate_signal(w, node_name, output.signal)
    patch = dict(output.patch)
    patch.setdefault("_last_bus_frame", output.trace(node=node_name))
    return output.signal, patch
