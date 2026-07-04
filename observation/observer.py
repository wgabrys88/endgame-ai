from __future__ import annotations

import json
import pathlib
import time
from typing import Any

from .depth import expand
from .filter import ObservationFilter
from .models import CachedNode
from .scan import fullscreen_hover_cache_scan
from .tree import DesktopTree

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Observer:
    def __init__(self, desktop: Any):
        self._d = desktop

    def observe(self, config: dict[str, Any]) -> dict[str, Any]:
        scan_cfg = expand(config)
        run = fullscreen_hover_cache_scan(
            self._d.automation,
            pattern=str(scan_cfg.get("pattern", "sinusoidal")),
            step_px=int(scan_cfg.get("step_px", 96)),
            delay_ms=int(scan_cfg.get("delay_ms", 5)),
            max_probe_points=scan_cfg.get("max_probe_points"),
            max_subtree_nodes_per_point=int(scan_cfg.get("max_subtree_nodes_per_point", 250)),
            max_total_nodes=int(scan_cfg.get("max_total_nodes", 2000)),
            include_nodes=True,
            scan_cfg=scan_cfg,
        )
        nodes: list[CachedNode] = run.pop("_nodes", [])
        filtered = ObservationFilter(config).apply(nodes)
        return self._package(run, filtered, scan_cfg, config)

    def _package(
        self,
        run: dict[str, Any],
        filtered: Any,
        scan_cfg: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32
        screen = {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}
        focused_title = str(run.get("focus", {}).get("window_title") or "") or self._d.get_focused_title()
        self._d._focused_title_cache = focused_title
        observed_at = time.time()
        scan_meta = {**scan_cfg, "method": "hover_cache", "stats": run.get("stats", {})}
        full_tree = DesktopTree.build(
            screen,
            dict(filtered.action_elements),
            self._d.get_window_tokens(),
            focused_title,
            observed_at=observed_at,
            scan_config=scan_meta,
            raw_element_count=len(filtered.gather_nodes),
        )
        desktop_tree = DesktopTree.semantic(full_tree)
        action_index = DesktopTree.action_index(full_tree)
        text_max = int((config.get("filter") or {}).get("text_hint_max", 120))
        hints = {
            n["id"]: str((n.get("text_hint") or {}).get("prefix", ""))[:text_max]
            for n in filtered.llm_nodes
            if isinstance(n, dict) and n.get("text_hint")
        }
        artifact = self._write_artifact(
            {
                "observed_at": observed_at,
                "fresh_scan": True,
                "focused_title": focused_title,
                "scan_config": scan_cfg,
                "hover_cache_config": config,
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
        return {
            "observed_at": observed_at,
            "fresh_scan": True,
            "desktop_tree": desktop_tree,
            "desktop_tree_text": DesktopTree.render_text(desktop_tree, hints),
            "action_index": action_index,
            "observation_artifact": artifact,
            "focused_title": focused_title,
        }

    @staticmethod
    def _write_artifact(payload: dict[str, Any], observed_at: float) -> dict[str, Any]:
        artifact_dir = ROOT / "comms" / "observations"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{int(observed_at * 1000)}.json"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
        return {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "kind": "raw_full_observation"}