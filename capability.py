from __future__ import annotations
import ctypes
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
import desktop

def _node_center(node: dict[str, Any]) -> tuple[int, int]:
    if node.get('x') is not None and node.get('y') is not None:
        return (int(node['x']), int(node['y']))
    rect = node.get('rect') if isinstance(node.get('rect'), dict) else {}
    left = int(rect.get('left', 0) or 0)
    right = int(rect.get('right', left) or left)
    top = int(rect.get('top', 0) or 0)
    bottom = int(rect.get('bottom', top) or top)
    return (left + max(0, right - left) // 2, top + max(0, bottom - top) // 2)

def build_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    state = ctx.get('state', {})
    wiring = ctx.get('wiring', {})
    goal = ctx.get('goal', '')
    action_index = state.get('action_index') if isinstance(state.get('action_index'), dict) else desktop.last_action_index()

    def node_by_id(node_id: str) -> dict[str, Any]:
        return dict(action_index.get(str(node_id), {}) or {})

    def click_node(node_id: str) -> dict[str, Any]:
        node = node_by_id(node_id)
        if not node:
            return {'ok': False, 'action': 'click_node', 'error': f'node not found: {node_id}'}
        x, y = _node_center(node)
        return desktop.click(x, y, int(node.get('hwnd') or 0))

    def scroll_node(node_id: str, amount: int = -3) -> dict[str, Any]:
        node = node_by_id(node_id)
        if not node:
            return {'ok': False, 'action': 'scroll_node', 'error': f'node not found: {node_id}'}
        x, y = _node_center(node)
        return desktop.scroll(x, y, int(amount))

    class _PyAutoGuiCompat:

        def click(self, x: int | None = None, y: int | None = None, clicks: int = 1, interval: float = 0.0, **kwargs: Any) -> Any:
            if x is None or y is None:
                return {'ok': False, 'action': 'pyautogui.click', 'error': 'x and y required'}
            result = None
            for _ in range(max(1, int(clicks or 1))):
                result = desktop.click(int(x), int(y), int(kwargs.get('hwnd') or 0))
                if interval:
                    time.sleep(float(interval))
            return result

        def write(self, text: str, interval: float = 0.0) -> Any:
            if interval:
                for ch in str(text):
                    desktop.type_text(ch)
                    time.sleep(float(interval))
                return {'ok': True, 'action': 'pyautogui.write', 'chars': len(str(text))}
            return desktop.type_text(str(text))

        typewrite = write

        def press(self, key: str, presses: int = 1, interval: float = 0.0) -> Any:
            result = None
            for _ in range(max(1, int(presses or 1))):
                result = desktop.press_key(str(key))
                if interval:
                    time.sleep(float(interval))
            return result

        def hotkey(self, *keys: str) -> Any:
            seq = keys[0] if len(keys) == 1 and isinstance(keys[0], (list, tuple)) else keys
            return desktop.hotkey([str(k) for k in seq])

        def scroll(self, amount: int = 0, x: int | None = None, y: int | None = None) -> Any:
            px = int(x or 0)
            py = int(y or 0)
            return desktop.scroll(px, py, int(amount))

    pyautogui = _PyAutoGuiCompat()
    return {
        'state': state,
        'wiring': wiring,
        'goal': goal,
        'node_by_id': node_by_id,
        'click_node': click_node,
        'scroll_node': scroll_node,
        'click': desktop.click,
        'type_text': desktop.type_text,
        'press_key': desktop.press_key,
        'hotkey': desktop.hotkey,
        'scroll': desktop.scroll,
        'focus_window': desktop.focus_window,
        'open_url': desktop.open_url,
        'pyautogui': pyautogui,
        'pag': pyautogui,
        'subprocess': subprocess,
        'ctypes': ctypes,
        'os': os,
        'sys': sys,
        'json': json,
        're': re,
        'time': time,
        'pathlib': pathlib,
        'math': math,
        'random': random,
        'types': types,
    }