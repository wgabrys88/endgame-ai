from __future__ import annotations

from typing import Any


class DesktopTree:
    @staticmethod
    def _contains_point(rect: dict[str, int], x: int, y: int) -> bool:
        return int(rect.get("left", 0)) <= x <= int(rect.get("right", 0)) and int(rect.get("top", 0)) <= y <= int(rect.get("bottom", 0))

    @staticmethod
    def _rect_area(rect: dict[str, int]) -> int:
        return max(0, int(rect.get("right", 0)) - int(rect.get("left", 0))) * max(0, int(rect.get("bottom", 0)) - int(rect.get("top", 0)))

    @staticmethod
    def _sort_children(node: dict[str, Any]) -> None:
        children = node.get("children")
        if not isinstance(children, list):
            return
        children.sort(key=lambda c: (
            int((c.get("rect") or {}).get("top", 0)),
            int((c.get("rect") or {}).get("left", 0)),
            DesktopTree._rect_area(c.get("rect") or {}),
        ))
        for child in children:
            if isinstance(child, dict):
                DesktopTree._sort_children(child)

    @classmethod
    def build(
        cls,
        screen: dict[str, int],
        elements: dict[str, dict[str, Any]],
        windows: list[dict[str, Any]],
        focused_title: str,
        *,
        observed_at: float,
        scan_config: dict[str, Any],
        raw_element_count: int,
    ) -> dict[str, Any]:
        root_rect = {"left": 0, "top": 0, "right": int(screen.get("width", 0)), "bottom": int(screen.get("height", 0))}
        root = {
            "id": "W0",
            "role": "Screen",
            "name": "Screen",
            "title": "Desktop",
            "rect": root_rect,
            "focused": False,
            "fresh_scan": True,
            "observed_at": observed_at,
            "scan": {
                "method": str(scan_config.get("method", "hover_cache")),
                "pattern": str(scan_config.get("pattern", "sinusoidal")),
                "step_px": int(scan_config.get("step_px", 0) or 0),
                "raw_element_count": raw_element_count,
                "actionable_element_count": len(elements),
                "stats": scan_config.get("stats", {}),
            },
            "children": [],
        }
        node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
        window_nodes: dict[str, dict[str, Any]] = {}
        hwnd_to_window_id: dict[int, str] = {}
        focused_window_id = ""

        for window in windows:
            token = str(window.get("token") or "")
            if not token or token == "W0":
                continue
            title = str(window.get("title") or window.get("name") or "")
            node = {
                "id": token,
                "parent_id": "W0",
                "role": "Window",
                "name": title,
                "title": title,
                "hwnd": int(window.get("hwnd") or 0),
                "process_id": int(window.get("process_id") or 0),
                "class_name": str(window.get("class_name") or ""),
                "rect": window.get("rect", {}),
                "focused": bool(focused_title and title == focused_title),
                "source": "win32_enum_windows",
                "children": [],
            }
            if node["focused"]:
                focused_window_id = token
            window_nodes[token] = node
            hwnd_to_window_id[node["hwnd"]] = token
            root["children"].append(node)
            node_index[token] = {k: v for k, v in node.items() if k != "children"}

        direct_elements: list[dict[str, Any]] = []
        for element_id, element in elements.items():
            px = int(element.get("px") or 0)
            py = int(element.get("py") or 0)
            hwnd = int(element.get("hwnd") or 0)
            parent_id = hwnd_to_window_id.get(hwnd, "")
            if not parent_id:
                containing = [n for n in window_nodes.values() if cls._contains_point(n.get("rect", {}), px, py)]
                if containing:
                    containing.sort(key=lambda n: cls._rect_area(n.get("rect", {})))
                    parent_id = str(containing[0]["id"])
            if not parent_id:
                parent_id = "W0"
            node = {
                "id": element_id,
                "parent_id": parent_id,
                "role": element.get("role", ""),
                "name": element.get("name", ""),
                "action": element.get("action", ""),
                "px": px,
                "py": py,
                "hwnd": hwnd,
                "rect": element.get("rect", {}),
                "enabled": bool(element.get("enabled", False)),
                "focused": bool(element.get("focused", False)),
                "automation_id": element.get("automation_id", ""),
                "class_name": element.get("class_name", ""),
                "runtime_id": element.get("runtime_id", []),
                "source": "hover_cache",
                "confidence": "cache_hit",
                "children": [],
            }
            node_index[element_id] = {k: v for k, v in node.items() if k != "children"}
            if parent_id == "W0":
                direct_elements.append(node)
            else:
                window_nodes[parent_id]["children"].append(node)

        root["children"].extend(direct_elements)
        cls._sort_children(root)
        return {
            "id": "W0",
            "role": "Screen",
            "fresh_scan": True,
            "observed_at": observed_at,
            "focused_title": focused_title,
            "focused_window_id": focused_window_id,
            "root": root,
            "node_index": node_index,
            "window_count": len(window_nodes),
            "element_count": len(elements),
        }

    @classmethod
    def semantic(cls, full_tree: dict[str, Any]) -> dict[str, Any]:
        root = cls._semantic_node(full_tree.get("root", {}) if isinstance(full_tree.get("root"), dict) else {})
        return {"id": "W0", "role": "Screen", "focused_title": full_tree.get("focused_title", ""), "root": root}

    @classmethod
    def _semantic_node(cls, node: dict[str, Any]) -> dict[str, Any]:
        semantic: dict[str, Any] = {
            "id": node.get("id", ""),
            "role": node.get("role", ""),
            "name": node.get("name", "") or node.get("title", ""),
        }
        if "action" in node:
            semantic["action"] = node.get("action")
        if node.get("focused"):
            semantic["focused"] = True
        children = node.get("children") if isinstance(node.get("children"), list) else []
        semantic["children"] = [cls._semantic_node(child) for child in children if isinstance(child, dict)]
        return semantic

    @classmethod
    def render_text(cls, semantic_tree: dict[str, Any], text_hints: dict[str, str] | None = None) -> str:
        hints = text_hints or {}
        lines: list[str] = []

        def clean_label(value: Any) -> str:
            return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())

        def render_node(node: dict[str, Any], indent: int = 0) -> None:
            prefix = "  " * indent
            node_id = str(node.get("id", ""))
            role = str(node.get("role", ""))
            name = clean_label(node.get("name", "") or node.get("title", ""))
            action = str(node.get("action", ""))
            parts: list[str] = []
            if node_id:
                parts.append(f"({node_id})")
            if role:
                parts.append(role)
            if name:
                parts.append(name)
            if action:
                parts.append(f"[{action}]")
            if node.get("focused") and role == "Window":
                parts.append("[FOCUSED]")
            hint = hints.get(node_id, "")
            if hint and hint not in name:
                parts.append(f"~{hint}")
            lines.append(f"{prefix}{' '.join(parts)}")
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    render_node(child, indent + 1)

        root = semantic_tree.get("root", {})
        if not isinstance(root, dict):
            return ""
        sid, srole, sname = root.get("id", "W0"), root.get("role", "Screen"), clean_label(root.get("name", "Desktop"))
        screen_parts: list[str] = []
        if sid:
            screen_parts.append(f"({sid})")
        if srole:
            screen_parts.append(srole)
        if sname:
            screen_parts.append(sname)
        lines.append(" ".join(screen_parts))
        for child in root.get("children") or []:
            if isinstance(child, dict):
                render_node(child, 1)
        return "\n".join(lines)

    @classmethod
    def action_index(cls, full_tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
        full_index = full_tree.get("node_index") if isinstance(full_tree.get("node_index"), dict) else {}
        out: dict[str, dict[str, Any]] = {}
        for node_id, node in full_index.items():
            if not isinstance(node, dict):
                continue
            out[str(node_id)] = {
                "id": node.get("id", node_id),
                "parent_id": node.get("parent_id"),
                "role": node.get("role"),
                "name": node.get("name") or node.get("title"),
                "title": node.get("title"),
                "action": node.get("action"),
                "px": node.get("px"),
                "py": node.get("py"),
                "hwnd": node.get("hwnd"),
                "rect": node.get("rect"),
                "enabled": node.get("enabled"),
                "focused": node.get("focused"),
                "automation_id": node.get("automation_id"),
                "class_name": node.get("class_name"),
                "runtime_id": node.get("runtime_id"),
            }
        return out