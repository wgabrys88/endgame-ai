"""Independent hover+cache observation probe for endgame-ai R&D.

Methodology:
  1. SetCursorPos (real mouse hover)
  2. IUIAutomation.ElementFromPointBuildCache with TreeScope_Subtree
  3. Harvest cached descendants + TextPattern.GetText(-1) / ValuePattern
  4. Gather everything; llm_preview shows filter layer (not wired to organism yet)
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from . import constants as C
from .scan import fullscreen_hover_cache_scan, single_point_probe

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "comms" / "hover_cache_probe_report.json"


def create_automation() -> Any:
    import comtypes.client

    return comtypes.client.CreateObject(C.uia.CUIAutomation, interface=C.uia.IUIAutomation)


def run_fullscreen_scan(**kwargs) -> dict[str, Any]:
    automation = create_automation()
    return fullscreen_hover_cache_scan(automation, **kwargs)


def run_sinusoidal_scan(**kwargs) -> dict[str, Any]:
    automation = create_automation()
    return fullscreen_hover_cache_scan(automation, pattern="sinusoidal", **kwargs)


def run_point(x: int, y: int, **kwargs) -> dict[str, Any]:
    automation = create_automation()
    return single_point_probe(automation, x, y, **kwargs)


def write_report(payload: dict[str, Any], path: pathlib.Path | None = None) -> pathlib.Path:
    out = path or DEFAULT_REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out