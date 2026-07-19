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

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        st = ctx.get("state", {})
        return {
            "goal": ctx.get("goal", ""),
            "state": bus.state_brief(st),
            "observation": bus.observation_brief(st),
        }

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: JsonDict) -> bus.Record:
        w = ctx["wiring"]
        prompt = wiring.prompt(w, self.prompt_key)
        think_kwargs: JsonDict = {"expected_record_type": self.expected_record_type, "emitting_node": ctx.get("node")}
        payload = self.build_payload(ctx)
        payload["goal"] = ctx["state"]["goal"]
        record = brain.think(prompt, payload, w, **think_kwargs)
        if record.get("record_type") != self.expected_record_type:
            raise bus.NodeRecordContractError(
                f"{self.prompt_key} expected record_type {self.expected_record_type!r}, "
                f"got {record.get('record_type')!r}"
            )
        return bus.Record.from_json(record)

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        record = self.think(ctx)
        data = record.data
        signal = self.signal_from_data(data, ctx)
        patch = self.patch_from_record(record, ctx)
        return bus.emit(signal, patch)


def call_node(node_name: str, ctx: JsonDict) -> tuple[str, JsonDict]:
    w = ctx["wiring"]
    base, instance = loader.split_instance(node_name)
    ctx = {**ctx, "node": node_name, "node_base": base, "node_instance": instance}
    mod = loader.load("node", node_name, w)
    result = mod.run(ctx)
    signal, patch = bus.coerce_node_output(node_name, result)
    bus.validate_signal(w, node_name, signal)
    return signal, dict(patch)
