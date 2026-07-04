from __future__ import annotations
import contextlib
import ctypes
import io
import json
import math
import os
import pathlib
import random
import re
import subprocess
import sys
import time
import types
from typing import Any
import brain
import bus
import win32_api
from node import LlmNode

class Execute(LlmNode):
    name = 'execute'
    record_type = 'execution'
    prompt_key = 'execute'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'state': bus.state_brief(state), 'ui_context': {'focused_title': state.get('focused_title', ''), 'desktop_tree_text': state.get('desktop_tree_text', ''), 'observed_at': state.get('observed_at')}, 'action_frame': state.get('action_frame'), 'last': {'error': state.get('last_error'), 'result': state.get('last_result', ''), 'action': state.get('last_action', {})}}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        return str(data.get('_route_signal', 'verify'))

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        return dict(record.get('data', {}).get('_patch') or {})

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        wiring = ctx.get('wiring', {})
        goal = ctx.get('goal', '')
        payload = self.payload(ctx)
        record = brain.think(organ=self.name, system_prompt=wiring.get('prompts', {}).get(self.prompt_key, ''), payload=payload, wiring=wiring, expected_record_type=self.record_type)
        if record.get('record_type') != 'execution':
            raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')!r}")
        data = record.get('data', {})
        code = str(data.get('code', '') or '')
        conclusion = str(data.get('conclusion', '') or '').upper()
        if conclusion not in {'EXECUTE', 'CANNOT', 'FRAME', 'SELF_MODIFY'}:
            raise RuntimeError(f"execute invalid conclusion: {conclusion!r}")
        if conclusion == 'SELF_MODIFY':
            return bus.emit('self_modify', {'last_action': {'code': '', 'conclusion': conclusion}, 'last_error': 'execute requested self modification'}, record=record, evidence=payload)
        if conclusion != 'EXECUTE' or not code.strip():
            signal = 'frame' if self._should_frame(state, conclusion) else 'reflect'
            return bus.emit(signal, {'last_action': {'code': '', 'conclusion': conclusion}, 'last_error': f'execute returned {conclusion}'}, record=record, evidence=payload)
        ns = {'subprocess': subprocess, 'ctypes': ctypes, 'os': os, 'sys': sys, 'json': json, 're': re, 'time': time, 'pathlib': pathlib, 'math': math, 'random': random, 'types': types, 'state': state, 'wiring': wiring, 'goal': goal, 'win32_api': win32_api, 'click_at': win32_api.click_at, 'type_text': win32_api.type_text, 'hotkey': win32_api.hotkey, 'press_key': win32_api.press_key, 'set_foreground_window': win32_api.set_foreground_window, 'open_url': win32_api.open_url}
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, ns)
            result = {'result': ns.get('result'), 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue()}
            error = None
        except Exception as exc:
            result = {'stdout': stdout.getvalue(), 'stderr': stderr.getvalue()}
            error = f'{type(exc).__name__}: {exc}'
        signal = 'reflect' if error else 'verify'
        return bus.emit(signal, {'last_action': {'code': code, 'conclusion': conclusion}, 'last_code': code, 'last_result': result, 'last_error': error, 'action_frame': None if not error else state.get('action_frame')}, record=record, evidence=payload)

    def _should_frame(self, state: dict[str, Any], conclusion: str) -> bool:
        step_index = int(state.get('step', 0) or 0)
        if state.get('action_frame') and (state.get('action_frame') or {}).get('step_index') == step_index:
            return False
        if state.get('framing_attempted_for_step') == step_index:
            return False
        if conclusion in {'CANNOT', 'FRAME'}:
            return True
        return bool(state.get('last_error')) and state.get('framing_attempted_for_step') != step_index

NODE = Execute()