from __future__ import annotations

import time
from typing import Any

import comtypes.client

from . import constants as C
from .depth import expand
from .filter import FilteredObservation, ObservationFilter
from .models import CachedNode
from .scan import fullscreen_hover_cache_scan


class HoverCacheObserver:
    def __init__(self, desktop: Any):
        self._d = desktop

    def observe(self, config: dict[str, Any]) -> dict[str, Any]:
        scan_cfg = expand(config)
        automation = comtypes.client.CreateObject(C.uia.CUIAutomation, interface=C.uia.IUIAutomation)
        run = fullscreen_hover_cache_scan(
            automation,
            pattern=str(scan_cfg.get("pattern", "sinusoidal")),
            step_px=int(scan_cfg.get("step_px", 96)),
            delay_ms=int(scan_cfg.get("delay_ms", 5)),
            max_probe_points=scan_cfg.get("max_probe_points"),
            max_subtree_nodes_per_point=int(scan_cfg.get("max_subtree_nodes_per_point", 250)),
            max_total_nodes=int(scan_cfg.get("max_total_nodes", 2000)),
            include_nodes=True,
        )
        nodes: list[CachedNode] = run.pop("_nodes", [])
        filtered = ObservationFilter(config).apply(nodes)
        return self._package(run, filtered, scan_cfg, config)

    def _package(
        self,
        run: dict[str, Any],
        filtered: FilteredObservation,
        scan_cfg: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        user32 = __import__("ctypes").windll.user32
        screen = {
            "width": user32.GetSystemMetrics(0),
            "height": user32.GetSystemMetrics(1),
        }
        focused_title = str(run.get("focus", {}).get("window_title") or "")
        if not focused_title:
            focused_title = self._d.get_focused_title()
        self._d._focused_title_cache = focused_title
        observed_at = time.time()
        elements = self._tree_elements(filtered)
        windows = self._d.get_window_tokens()
        full_tree = self._d.build_desktop_tree(
            screen,
            elements,
            windows,
            focused_title,
            observed_at=observed_at,
            scan_config={**scan_cfg, "method": "hover_cache"},
            raw_element_count=len(filtered.gather_nodes),
        )
        if isinstance(full_tree.get("root"), dict) and isinstance(full_tree["root"].get("scan"), dict):
            full_tree["root"]["scan"]["method"] = "hover_cache"
            full_tree["root"]["scan"]["stats"] = run.get("stats", {})
        desktop_tree = self._d.semantic_desktop_tree(full_tree)
        action_index = self._d.action_index_from_tree(full_tree)
        artifact = self._d.write_observation_artifact(
            {
                "observed_at": observed_at,
                "fresh_scan": True,
                "focused_title": focused_title,
                "scan_config": scan_cfg,
                "hover_cache_config": config,
                "windows": windows,
                "gather": filtered.gather_nodes,
                "llm_nodes": filtered.llm_nodes,
                "scan_stats": run.get("stats", {}),
                "full_desktop_tree": full_tree,
                "semantic_desktop_tree": desktop_tree,
                "action_index": action_index,
            },
            observed_at,
        )
        self._d._last_desktop_tree = desktop_tree
        self._d._last_action_index = action_index
        text_max = int((config.get("filter") or {}).get("text_hint_max", 120))
        return {
            "observed_at": observed_at,
            "fresh_scan": True,
            "desktop_tree": desktop_tree,
            "desktop_tree_text": self._render_llm_tree(desktop_tree, filtered, text_max),
            "action_index": action_index,
            "observation_artifact": artifact,
            "focused_title": focused_title,
        }

    def _tree_elements(self, filtered: FilteredObservation) -> dict[str, dict[str, Any]]:
        return dict(filtered.action_elements)

    def _render_llm_tree(
        self,
        semantic_tree: dict[str, Any],
        filtered: FilteredObservation,
        text_max: int,
    ) -> str:
        hints = {
            n["id"]: n.get("text_hint", {}).get("prefix", "")
            for n in filtered.llm_nodes
            if isinstance(n, dict) and n.get("text_hint")
        }
        base = self._d.render_tree_text(semantic_tree)
        if not hints:
            return base
        lines = []
        for line in base.splitlines():
            patched = line
            for node_id, hint in hints.items():
                token = f"({node_id})"
                if token in line and hint and hint not in line:
                    patched = f"{line} ~{hint[:text_max]}"
                    break
            lines.append(patched)
        return "\n".join(lines)