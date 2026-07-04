from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import brain
import bus

class Node(ABC):
    name: str

    @abstractmethod
    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        ...

class LlmNode(Node):
    record_type: str
    prompt_key: str

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'state': bus.state_brief(state)}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        raise NotImplementedError

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def request_config(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        wiring = ctx['wiring']
        record = brain.think(organ=self.name, system_prompt=wiring.get('prompts', {}).get(self.prompt_key, ''), payload=self.payload(ctx), wiring=wiring, expected_record_type=self.record_type, request_config=self.request_config(ctx))
        if record.get('record_type') != self.record_type:
            raise RuntimeError(f"{self.name} expected record_type={self.record_type!r}, got {record.get('record_type')!r}")
        data = record.get('data', {})
        if not isinstance(data, dict):
            raise RuntimeError(f"{self.name} record data must be object")
        return bus.emit(self.signal(data, record), self.patch(record, ctx), record=record, evidence=self.payload(ctx))

class MechanicalNode(Node):
    @abstractmethod
    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        ...