"""Dumb topology executor — all intelligence in prompts/wiring.json."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from llm import LLMResult
from bus import Bus


def extract_json(text: str) -> dict | None:
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[i : j + 1])
                except json.JSONDecodeError:
                    break
    return None


class ContextBuilder:
    """Build USER message from wiring.request[circuit].user.blocks."""

    def __init__(self, wiring: dict[str, Any], circuit: str, workspace: Path):
        self._wiring = wiring
        self._circuit = circuit
        self._workspace = workspace
        self._req = wiring.get("request", {}).get(circuit, {})
        self._limits = wiring.get("limits", {})

    def build(self, state: Any, bus: Bus, task: Any | None) -> str:
        blocks = self._req.get("user", {}).get("blocks", [])
        lines: list[str] = []
        for block in blocks:
            val = self._resolve_block(block, state, bus, task)
            if val or block.get("always"):
                label = str(block.get("label", block.get("id", "")))
                lines.append(f"{label}: {val}" if label else str(val))
        sep = str(self._req.get("user", {}).get("separator", "\n"))
        return sep.join(lines)

    def _resolve_block(self, block: dict[str, Any], state: Any, bus: Bus, task: Any | None) -> str:
        bid = str(block.get("id", ""))
        source = str(block.get("source", bid))
        if block.get("when") == "manager_swap" and not self._manager_swap(state.goal):
            return ""
        if source == "state.goal":
            return state.goal
        if source == "state.screen":
            if state.screen:
                return state.screen
            return str(block.get("empty_template") or self._wiring.get("context", {}).get("screen_empty", ""))
        if source == "state.last_error":
            err = state.last_action_error
            if err:
                state.last_action_error = ""
            return err
        if source == "state.last_reasoning":
            fb = self._wiring.get("feedback", {}).get("reasoning", {})
            if not state.reasoning_history:
                return ""
            depth = int(fb.get("depth_from_limits", "reasoning_history_depth") and
                        self._limits.get("reasoning_history_depth", 20))
            fmt = str(fb.get("entry_format", "[attempt] {reasoning} → {outcome}"))
            entries = state.reasoning_history[-depth:]
            return "\n".join(fmt.format(reasoning=e.get("reasoning", ""), outcome=e.get("outcome", "")) for e in entries)
        if source == "state.workspace":
            return self._workspace_block(state, block)
        if source.startswith("context."):
            key = source.split(".", 1)[1]
            return str(self._wiring.get("context", {}).get(key, "")).format(**self._templates())
        return ""

    def _templates(self) -> dict[str, str]:
        role = str(self._wiring.get("instance", {}).get("role", ""))
        return {
            "role": role,
            "root": str(self._workspace),
            "prompts": str(self._workspace / "prompts"),
            "wiring": str(self._workspace / "prompts" / "wiring.json"),
        }

    def _workspace_block(self, state: Any, block: dict[str, Any]) -> str:
        t = self._templates()
        lines = [f"ROOT: {t['root']}", f"PROMPTS: {t['prompts']}", f"WIRING: {t['wiring']}"]
        if self._manager_swap(state.goal):
            prefix = str(block.get("manager_prefix", "ROLE: {role}")).format(**t)
        else:
            prefix = str(block.get("executor_prefix", "MODE: executor")).format(**t)
        lines.insert(0, prefix)
        return "\n".join(lines)

    def _manager_swap(self, goal: str) -> bool:
        swaps = self._wiring.get("circuits", {}).get(self._circuit, {}).get("prompt_swap", [])
        g = goal.lower()
        return any(any(t.lower() in g for t in s.get("when", [])) for s in swaps)


class PromptResolver:
    def __init__(self, wiring: dict[str, Any], circuit: str, prompts_dir: Path):
        self._wiring = wiring
        self._circuit = circuit
        self._prompts_dir = prompts_dir
        cfg = wiring["circuits"][circuit]
        self._default = (prompts_dir / cfg["prompt"]).read_text(encoding="utf-8").strip()
        self._swaps = cfg.get("prompt_swap", [])
        req = wiring.get("request", {}).get(circuit, {}).get("system", {})
        if req.get("file"):
            path = prompts_dir / req["file"]
            if path.exists():
                self._default = path.read_text(encoding="utf-8").strip()

    def resolve(self, goal: str) -> str:
        g = goal.lower()
        for swap in self._swaps:
            triggers = swap.get("when", [])
            alt = swap.get("prompt", "")
            if alt and any(t.lower() in g for t in triggers):
                return (self._prompts_dir / alt).read_text(encoding="utf-8").strip()
        return self._default


class ResponsePipeline:
    """Run wiring.response[circuit].pipeline — parse, guards, emit events."""

    def __init__(self, wiring: dict[str, Any], circuit: str):
        self._wiring = wiring
        self._circuit = circuit
        self._cfg = wiring.get("response", {}).get(circuit, {})
        self._pipeline = self._cfg.get("pipeline", [])
        self._guards = self._cfg.get("guards", {})
        self._limits = wiring.get("limits", {})

    def run(self, result: LLMResult, state: Any, bus: Bus) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "content": result.text.strip(),
            "reasoning_content": result.reasoning,
            "record": None,
            "data": {},
            "conclusion": "",
            "actions": [],
            "outcome": "",
        }
        event = f"{self._circuit}_error"
        for step in self._pipeline:
            stype = str(step.get("step", ""))
            if stype == "parse_json":
                ctx["record"] = self._parse_json(ctx, step)
                if not ctx["record"]:
                    event = str(step.get("on_fail", event))
                    return self._fail(state, event, step.get("error", "parse_failed"))
            elif stype == "extract_fields":
                rec = ctx.get("record") or {}
                try:
                    ctx["data"] = rec["data"]
                except (KeyError, TypeError):
                    event = str(step.get("on_fail", event))
                    return self._fail(state, event, "parse_failed")
                ctx["conclusion"] = str(ctx["data"].get("conclusion", "EXECUTE"))
                ctx["actions"] = ctx["data"].get("actions", [])
            elif stype == "branch_conclusion":
                event = self._branch_conclusion(ctx, state, bus, result)
                if event:
                    return self._package(event, ctx, result, state, bus)
            elif stype == "emit":
                event = str(step.get("event", event))
        return self._package(event, ctx, result, state, bus)

    def _parse_json(self, ctx: dict[str, Any], step: dict[str, Any]) -> dict | None:
        sources = step.get("from", ["content"])
        for src in sources:
            text = str(ctx.get(src, ""))
            rec = None
            try:
                rec = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                rec = extract_json(text)
            if rec:
                return rec
        return None

    def _branch_conclusion(self, ctx: dict[str, Any], state: Any, bus: Bus, result: LLMResult) -> str | None:
        conclusion = ctx["conclusion"]
        if conclusion == "DONE":
            g = self._guards.get("premature_done", {})
            keywords = g.get("goal_keywords", [])
            outcomes = g.get("required_outcomes", [])
            goal_lower = state.goal.lower()
            if keywords and outcomes and any(w in goal_lower for w in keywords):
                did = any(any(o in str(h.get("outcome", "")) for o in outcomes) for h in state.reasoning_history)
                if not did:
                    ctx["outcome"] = str(g.get("override_outcome", "SYSTEM: goal requires typing but no write was done yet"))
                    self._append_feedback(state, result, ctx)
                    ctx["actions"] = []
                    return "unified_acted"
            ctx["outcome"] = "goal complete"
            self._append_feedback(state, result, ctx)
            return "goal_complete"
        if conclusion == "CANNOT":
            ctx["outcome"] = "cannot"
            self._append_feedback(state, result, ctx)
            return "unified_cannot"
        # EXECUTE
        rep = self._guards.get("repeat_block", {})
        actions = ctx.get("actions", [])
        if state.reasoning_history and actions and state._last_actions:
            last = state.reasoning_history[-1]
            same = (len(actions) == len(state._last_actions)
                    and all(a.get("verb") == b.get("verb") and a.get("target") == b.get("target")
                            for a, b in zip(actions, state._last_actions)))
            if rep.get("block_if_outcome_contains", "OK") in last.get("outcome", "") and same:
                hint = self._advance_hint(state._last_actions[0], state.screen)
                ctx["outcome"] = f"SYSTEM: repeat blocked — {hint}"
                self._append_feedback(state, result, ctx)
                state.last_action_error = hint
                ctx["actions"] = []
                return "unified_acted"
        state._last_actions = actions
        bus.publish("action", self._circuit, state.active_task_id or "", ctx["data"])
        ctx["outcome"] = ""
        return "unified_acted"

    def _advance_hint(self, action: dict, screen: str) -> str:
        verb = str(action.get("verb", "")).lower()
        target = str(action.get("target", "")).lower()
        s = screen.lower()
        for rule in self._guards.get("advance_hints", []):
            rw = str(rule.get("verb", "")).lower()
            if rw and rw != verb:
                continue
            tc = rule.get("target_contains", [])
            if tc and not any(t in target for t in tc):
                continue
            sc = rule.get("screen_contains", [])
            if sc and not any(t in s for t in sc):
                continue
            sc_exclude = rule.get("screen_excludes", [])
            if sc_exclude and any(t in s for t in sc_exclude):
                continue
            return str(rule.get("hint", ""))
        return str(self._guards.get("advance_hints_default",
                    "NEXT REQUIRED: different verb+target — prior action already succeeded, read SCREEN"))

    def _append_feedback(self, state: Any, result: LLMResult, ctx: dict[str, Any]) -> None:
        fb = self._wiring.get("feedback", {}).get("reasoning", {})
        entry = {
            "reasoning": result.reasoning,
            "outcome": ctx.get("outcome", ""),
        }
        state.reasoning_history.append(entry)
        depth = int(self._limits.get("reasoning_history_depth", 20))
        if len(state.reasoning_history) > depth:
            state.reasoning_history = state.reasoning_history[-depth:]

    def _fail(self, state: Any, event: str, msg: str) -> dict[str, Any]:
        state.last_action_error = msg
        return {"event": event, "error": msg}

    def _package(self, event: str, ctx: dict[str, Any], result: LLMResult,
                 state: Any, bus: Bus) -> dict[str, Any]:
        out: dict[str, Any] = {
            "event": event,
            "conclusion": ctx.get("conclusion", ""),
            "actions": ctx.get("actions", []),
        }
        if event == "unified_acted" and ctx.get("outcome") == "":
            out["reasoning_entry"] = {"reasoning": result.reasoning, "outcome": ""}
        return out


def parse_cli_from_wiring(wiring: dict[str, Any], argv: list[str]) -> dict[str, Any]:
    """Parse goal + response_limit + flags per wiring.runtime.cli."""
    cli = wiring.get("runtime", {}).get("cli", {})
    goal_cfg = cli.get("goal", {})
    limit_cfg = cli.get("response_limit", {})
    flag_cfg = cli.get("no_desktop", {})
    raw = list(argv)
    no_desktop = False
    if flag_cfg.get("flag") in raw:
        raw = [a for a in raw if a != flag_cfg["flag"]]
        no_desktop = True
    limit = None
    if limit_cfg.get("type") == "trailing_positive_int" and raw and raw[-1].isdigit() and int(raw[-1]) > 0:
        limit = int(raw[-1])
        raw = raw[:-1]
    join = str(goal_cfg.get("join", " "))
    goal = join.join(raw).strip()
    return {"goal": goal, "response_limit": limit, "no_desktop": no_desktop}


def export_drawio(wiring: dict[str, Any], path: Path) -> None:
    """Export topology nodes/edges to draw.io mxGraphModel XML."""
    topo = wiring.get("topology", {})
    nodes = {n["id"]: n for n in topo.get("nodes", [])}
    edges = topo.get("edges", [])
    mxfile = ET.Element("mxfile", host="endgame-ai")
    diagram = ET.SubElement(mxfile, "diagram", name="wiring-topology")
    model = ET.SubElement(diagram, "mxGraphModel", dx="1200", dy="800", grid="1", gridSize="10")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    cell_id = 2
    id_map: dict[str, str] = {}
    for nid, node in nodes.items():
        d = node.get("drawio", {})
        x, y = str(d.get("x", 40)), str(d.get("y", 40))
        w, h = str(d.get("w", 160)), str(d.get("h", 50))
        label = str(node.get("label", nid))
        ntype = str(node.get("type", ""))
        style = str(d.get("style", "rounded=1;whiteSpace=wrap;html=1;"))
        cid = str(cell_id)
        id_map[nid] = cid
        cell = ET.SubElement(root, "mxCell", id=cid, value=f"{label}\n({ntype})",
                             style=style, vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry", x=x, y=y, width=w, height=h, **{"as": "geometry"})
        cell_id += 1
    for edge in edges:
        src = id_map.get(edge.get("from", ""))
        tgt = id_map.get(edge.get("to", ""))
        if not src or not tgt:
            continue
        on = str(edge.get("on", ""))
        cid = str(cell_id)
        cell = ET.SubElement(root, "mxCell", id=cid, value=on, style="edgeStyle=orthogonalEdgeStyle;html=1;",
                             edge="1", parent="1", source=src, target=tgt)
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1
    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(mxfile, encoding="unicode"),
                    encoding="utf-8")