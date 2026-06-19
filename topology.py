"""Dumb topology executor — all behavior declared in prompts/wiring.json."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import llm as llm_mod
from llm import LLMClient, LLMResult
from bus import Bus

_log = logging.getLogger("endgame")


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
            depth = int(self._limits.get("reasoning_history_depth", 20))
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


class ConditionEvaluator:
    """Evaluate wiring guard/when conditions against runtime state."""

    def __init__(self, guards: dict[str, Any]):
        self._guards = guards

    def match(self, spec: dict[str, Any] | list[Any] | str | bool, ctx: dict[str, Any],
              state: Any, result: LLMResult) -> bool:
        if isinstance(spec, bool):
            return spec
        if isinstance(spec, str):
            return bool(spec)
        if isinstance(spec, list):
            return all(self.match(s, ctx, state, result) for s in spec)
        if "all" in spec:
            return all(self.match(s, ctx, state, result) for s in spec["all"])
        if "any" in spec:
            return any(self.match(s, ctx, state, result) for s in spec["any"])
        if "not" in spec:
            return not self.match(spec["not"], ctx, state, result)
        if "goal_contains_any" in spec:
            g = state.goal.lower()
            return any(w.lower() in g for w in spec["goal_contains_any"])
        if "history_outcome_contains_any" in spec:
            needles = spec["history_outcome_contains_any"]
            return any(
                any(n in str(h.get("outcome", "")) for n in needles)
                for h in state.reasoning_history
            )
        if "not_empty" in spec:
            path = str(spec["not_empty"])
            return bool(self._resolve_path(path, ctx, state))
        if "last_outcome_contains" in spec:
            if not state.reasoning_history:
                return False
            needle = str(spec["last_outcome_contains"])
            return needle in state.reasoning_history[-1].get("outcome", "")
        if "actions_equal_last" in spec:
            actions = ctx.get("actions", [])
            if not state.reasoning_history or not actions or not state._last_actions:
                return False
            return (len(actions) == len(state._last_actions)
                    and all(a.get("verb") == b.get("verb") and a.get("target") == b.get("target")
                            for a, b in zip(actions, state._last_actions)))
        return False

    def _resolve_path(self, path: str, ctx: dict[str, Any], state: Any) -> Any:
        if path.startswith("state."):
            return getattr(state, path[6:], None)
        return ctx.get(path)


class ResponsePipeline:
    """Run wiring.response[circuit].pipeline — declarative steps only."""

    def __init__(self, wiring: dict[str, Any], circuit: str):
        self._wiring = wiring
        self._circuit = circuit
        self._cfg = wiring.get("response", {}).get(circuit, {})
        self._pipeline = self._cfg.get("pipeline", [])
        self._guards = self._cfg.get("guards", {})
        self._limits = wiring.get("limits", {})
        self._fb = wiring.get("feedback", {}).get("reasoning", {})
        self._conditions = ConditionEvaluator(self._guards)

    def run(self, result: LLMResult, state: Any, bus: Bus) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "content": result.text.strip(),
            "reasoning_content": result.reasoning,
            "record": None,
            "data": {},
            "conclusion": "",
            "actions": [],
            "outcome": "",
            "event": f"{self._circuit}_error",
            "defer_reasoning_outcome": False,
            "append_feedback": False,
        }
        halted = self._run_steps(self._pipeline, ctx, state, bus, result)
        if halted:
            return halted
        return self._package(ctx, result, state)

    def _run_steps(self, steps: list[dict[str, Any]], ctx: dict[str, Any], state: Any,
                   bus: Bus, result: LLMResult) -> dict[str, Any] | None:
        for step in steps:
            out = self._run_step(step, ctx, state, bus, result)
            if out is not None:
                return out
        return None

    def _run_step(self, step: dict[str, Any], ctx: dict[str, Any], state: Any,
                  bus: Bus, result: LLMResult) -> dict[str, Any] | None:
        stype = str(step.get("step", ""))
        if stype == "parse_json":
            ctx["record"] = self._parse_json(ctx, step)
            if not ctx["record"]:
                return self._fail(state, str(step.get("on_fail", f"{self._circuit}_error")),
                                  str(step.get("error", "parse_failed")))
        elif stype == "extract_fields":
            rec = ctx.get("record") or {}
            try:
                ctx["data"] = rec["data"]
            except (KeyError, TypeError):
                return self._fail(state, str(step.get("on_fail", f"{self._circuit}_error")), "parse_failed")
            ctx["conclusion"] = str(ctx["data"].get("conclusion", "EXECUTE"))
            ctx["actions"] = ctx["data"].get("actions", [])
        elif stype == "when":
            field = str(step.get("field", "conclusion"))
            key = str(ctx.get(field, ""))
            cases = step.get("cases", {})
            branch = cases.get(key, cases.get("*", []))
            return self._run_steps(branch, ctx, state, bus, result)
        elif stype == "guard":
            ref = str(step.get("ref", ""))
            guard = self._guards.get(ref, {})
            when = guard.get("when", {})
            if self._conditions.match(when, ctx, state, result):
                return self._apply_then(guard.get("then", {}), ctx, state, bus, result)
        elif stype == "set":
            for key, val in step.items():
                if key == "step":
                    continue
                if key == "outcome":
                    ctx["outcome"] = str(val)
                elif key.startswith("state."):
                    setattr(state, key[6:], self._format(str(val), ctx, state))
        elif stype == "remember_actions":
            state._last_actions = list(ctx.get("actions", []))
        elif stype == "publish":
            channel = str(step.get("channel", "action"))
            bus.publish(channel, self._circuit, state.active_task_id or "", ctx["data"])
        elif stype == "emit":
            ctx["event"] = str(step.get("event", ctx["event"]))
            if "outcome" in step:
                ctx["outcome"] = str(step["outcome"])
            ctx["defer_reasoning_outcome"] = bool(step.get("defer_reasoning_outcome", False))
            ctx["append_feedback"] = bool(step.get("append_feedback", False))
            return self._package(ctx, result, state)
        return None

    def _apply_then(self, then: dict[str, Any], ctx: dict[str, Any], state: Any,
                    bus: Bus, result: LLMResult) -> dict[str, Any]:
        hint = self._advance_hint(ctx, state)
        fmt_vars = {"advance_hint": hint}
        if then.get("clear_actions"):
            ctx["actions"] = []
        if "outcome" in then:
            ctx["outcome"] = self._format(str(then["outcome"]), ctx, state, fmt_vars)
        if "last_error" in then:
            state.last_action_error = self._format(str(then["last_error"]), ctx, state, fmt_vars)
        ctx["event"] = str(then.get("event", "unified_acted"))
        ctx["append_feedback"] = bool(then.get("append_feedback", bool(ctx.get("outcome"))))
        return self._package(ctx, result, state)

    def _format(self, template: str, ctx: dict[str, Any], state: Any,
                extra: dict[str, str] | None = None) -> str:
        if template == "{actions}":
            return str(ctx.get("actions", []))
        vars_ = {"advance_hint": self._advance_hint(ctx, state), **(extra or {})}
        try:
            return template.format(**vars_)
        except KeyError:
            return template

    def _advance_hint(self, ctx: dict[str, Any], state: Any) -> str:
        actions = ctx.get("actions", [])
        action = actions[0] if actions else (state._last_actions[0] if state._last_actions else {})
        verb = str(action.get("verb", "")).lower()
        target = str(action.get("target", "")).lower()
        s = state.screen.lower()
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
        return str(self._guards.get(
            "advance_hints_default",
            "NEXT REQUIRED: different verb+target — prior action already succeeded, read SCREEN",
        ))

    def _parse_json(self, ctx: dict[str, Any], step: dict[str, Any]) -> dict | None:
        for src in step.get("from", ["content"]):
            text = str(ctx.get(src, ""))
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                rec = extract_json(text)
                if rec:
                    return rec
        return None

    def _append_feedback(self, state: Any, result: LLMResult, ctx: dict[str, Any]) -> None:
        entry = {"reasoning": result.reasoning, "outcome": ctx.get("outcome", "")}
        state.reasoning_history.append(entry)
        depth = int(self._limits.get("reasoning_history_depth", 20))
        if len(state.reasoning_history) > depth:
            state.reasoning_history = state.reasoning_history[-depth:]

    def _fail(self, state: Any, event: str, msg: str) -> dict[str, Any]:
        state.last_action_error = msg
        return {"event": event, "error": msg}

    def _package(self, ctx: dict[str, Any], result: LLMResult, state: Any) -> dict[str, Any]:
        event = str(ctx.get("event", f"{self._circuit}_error"))
        append_events = self._fb.get("append_on_events", [])
        if ctx.get("append_feedback") or (event in append_events and ctx.get("outcome")):
            self._append_feedback(state, result, ctx)
        out: dict[str, Any] = {
            "event": event,
            "conclusion": ctx.get("conclusion", ""),
            "actions": ctx.get("actions", []),
        }
        if event == "unified_acted" and ctx.get("defer_reasoning_outcome"):
            out["reasoning_entry"] = {"reasoning": result.reasoning, "outcome": ""}
        return out


@dataclass
class GraphRuntime:
    """Injectable services for graph node handlers."""
    wiring: dict[str, Any]
    llm: LLMClient
    bus: Bus
    workspace: Path
    prompts_dir: Path
    desktop_enabled: bool = True
    desktop: Any = None
    actions: Any = None
    llm_hook: Callable[[str, str], LLMResult] | None = None


class GraphExecutor:
    """Walk topology.nodes/edges — one cycle = one LLM turn (+ optional desktop_exec)."""

    def __init__(self, runtime: GraphRuntime):
        self._rt = runtime
        self._apply_wiring(runtime.wiring)

    def update_wiring(self, wiring: dict[str, Any]) -> None:
        self._rt.wiring = wiring
        self._apply_wiring(wiring)

    def _apply_wiring(self, wiring: dict[str, Any]) -> None:
        topo = wiring["topology"]
        self._nodes = {str(n["id"]): n for n in topo["nodes"]}
        self._edges: dict[str, list[dict[str, Any]]] = {}
        for edge in topo["edges"]:
            self._edges.setdefault(str(edge["from"]), []).append(edge)
        self._cycle_start = str(topo.get("cycle_start", "response_limit_gate"))
        self._circuit = str(wiring["startup"]["circuit"])
        self._limits = wiring["limits"]
        self._ctx_build = ContextBuilder(wiring, self._circuit, self._rt.workspace)
        self._prompts = PromptResolver(wiring, self._circuit, self._rt.prompts_dir)
        self._pipeline = ResponsePipeline(wiring, self._circuit)
        self._bus_throttle = float(self._limits.get("bus_check_throttle_s", 3))
        self._last_bus_check: dict[str, float] = {}

    def run_cycle(self, slot_name: str, slot: Any) -> dict[str, Any] | None:
        ctx: dict[str, Any] = {"slot_name": slot_name, "result": None}
        node_id: str | None = self._cycle_start
        while node_id and node_id != "idle":
            node = self._nodes.get(node_id)
            if not node:
                break
            signals = self._dispatch(node, slot, ctx)
            if signals is None:
                return ctx.get("result")
            targets = self._follow_fanout(node_id, signals)
            if not targets:
                return ctx.get("result")
            # Fan-out: fire all secondary targets, continue on primary (first match)
            for secondary in targets[1:]:
                sec_node = self._nodes.get(secondary)
                if sec_node:
                    self._dispatch(sec_node, slot, ctx)
            node_id = targets[0]
        if node_id == "idle":
            self._node_idle(slot, ctx)
        return ctx.get("result")

    def _follow_fanout(self, from_id: str, signals: set[str]) -> list[str]:
        """All matching edge targets for fan-out. First = primary continuation."""
        targets: list[str] = []
        for edge in self._edges.get(from_id, []):
            on = str(edge.get("on", ""))
            if on == "*" or any(part in signals for part in on.split("|")):
                targets.append(str(edge["to"]))
        return targets

    def _dispatch(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str] | None:
        handler = getattr(self, f"_node_{node['type']}", None)
        if not handler:
            raise KeyError(f"Unknown topology node type: {node['type']}")
        return handler(node, slot, ctx)

    def _node_gate(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        check = str(node.get("check", "response_limit"))
        if check == "response_limit" and llm_mod.shutdown_requested:
            return {"limit_reached"}
        return {"under_limit"}

    def _node_bus_route(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str] | None:
        name = str(ctx["slot_name"])
        if not slot.state.goal:
            now = time.time()
            last = self._last_bus_check.get(name, 0.0)
            if now - last >= self._bus_throttle:
                self._last_bus_check[name] = now
                for r in reversed(self._rt.bus.query(record_type="route", limit=10)):
                    if r.data.get("to") != name or r.data.get("status") != "open":
                        continue
                    goal = str(r.data.get("goal", ""))
                    if goal:
                        slot.set_goal(goal)
                        r.data["status"] = "accepted"
                        break
        if not slot.state.goal:
            return None
        slot.state.cycles += 1
        return {"route_open"}

    def _node_desktop_observe(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        state = slot.state
        if self._rt.desktop_enabled and self._rt.desktop:
            try:
                obs = self._rt.desktop.observe()
                state.screen = obs.context_text
                state.screen_elements = obs.elements
            except Exception as e:
                _log.warning("observe failed: %s", e)
                msg = str(self._rt.wiring.get("context", {}).get("screen_empty", ""))
                state.screen = msg
                state.screen_elements = {}
        else:
            msg = str(self._rt.wiring.get("context", {}).get(
                "screen_disabled",
                "(desktop observation disabled — assume bare Windows desktop)",
            ))
            state.screen = msg
            state.screen_elements = {}
        return {"screen_ready"}

    def _node_request_assembly(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        ctx["user"] = self._ctx_build.build(slot.state, self._rt.bus, None)
        ctx["system"] = self._prompts.resolve(slot.state.goal)
        return {"request_built"}

    def _node_llm(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        system, user = ctx["system"], ctx["user"]
        if self._rt.llm_hook:
            result = self._rt.llm_hook(system, user)
        else:
            result = self._rt.llm.call(system, user) if user else LLMResult(text="")
        ctx["llm_result"] = result
        _log.debug("[%s] prompt=%d ctx=%d → response=%d reasoning=%d",
                   self._circuit, len(system), len(user),
                   len(result.text), len(result.reasoning))
        return {"response_received"}

    def _node_response_pipeline(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        result = self._pipeline.run(ctx["llm_result"], slot.state, self._rt.bus)
        ctx["result"] = result
        signals = {str(result.get("event", ""))}
        if result.get("actions"):
            signals.add("actions_present")
        if llm_mod.shutdown_requested:
            signals.add("limit_reached")
        return signals

    def _node_audit_log(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        """Fan-out target: publish action intent to bus for tracing."""
        result = ctx.get("result") or {}
        actions = result.get("actions", [])
        if actions:
            self._rt.bus.publish(
                "audit", self._circuit, slot.state.active_task_id or "",
                {"actions": actions, "cycle": slot.state.cycles},
            )
        return {"audit_done"}

    def _node_feedback(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        return {"cycle_done"}

    def _node_desktop_execute(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        result = ctx.get("result") or {}
        actions = result.get("actions", [])
        reasoning_entry = result.get("reasoning_entry")
        state = slot.state
        execution_log: list[str] = []
        if self._rt.actions and actions and slot.can_act_desktop:
            elements = state.screen_elements
            outcomes: list[str] = []
            for action in actions:
                verb = str(action.get("verb", ""))
                ar = self._rt.actions.execute(verb, action, elements)
                line = f"{verb}: {'OK' if ar.success else ar.observation}"
                outcomes.append(line)
                execution_log.append(f"▶ {line}")
                if not ar.success:
                    state.last_action_error = f"{verb}: {ar.observation}"
                self._rt.bus.publish(
                    "evidence", "tool", state.active_task_id or "",
                    {"verb": verb, "success": ar.success, "obs": ar.observation},
                )
            if reasoning_entry is not None:
                reasoning_entry["outcome"] = "; ".join(outcomes)
                state.reasoning_history.append(reasoning_entry)
                depth = int(self._limits.get("reasoning_history_depth", 20))
                if len(state.reasoning_history) > depth:
                    state.reasoning_history = state.reasoning_history[-depth:]
        if execution_log:
            result["execution_log"] = execution_log
        return {"cycle_done"}

    def _node_idle(self, slot: Any, ctx: dict[str, Any]) -> None:
        result = ctx.get("result") or {}
        if result.get("event") == "goal_complete":
            self._complete_goal(slot)

    def _complete_goal(self, slot: Any) -> None:
        state = slot.state
        name = slot.name
        for r in self._rt.bus.records:
            if (r.record_type == "route" and r.data.get("to") == name
                    and r.data.get("goal") == state.goal and r.data.get("status") == "accepted"):
                seq = r.data.get("seq")
                if seq is not None:
                    self._rt.bus.mark_route_done(seq)
                r.data["status"] = "verified_done"
                break
        state.goal = ""
        state.tasks = []
        state.phase = str(self._rt.wiring["transitions"]["default"])

    def _node_entry(self, node: dict[str, Any], slot: Any, ctx: dict[str, Any]) -> set[str]:
        return {"args_parsed"}


def parse_cli_from_wiring(wiring: dict[str, Any], argv: list[str]) -> dict[str, Any]:
    """Parse goal + response_limit + flags per wiring.runtime.cli."""
    cli = wiring.get("runtime", {}).get("cli", {})
    goal_cfg = cli.get("goal", {})
    limit_cfg = cli.get("response_limit", {})
    flag_cfg = cli.get("no_desktop", {})
    suite_cfg = cli.get("suite", {})
    raw = list(argv)
    no_desktop = False
    suite = None
    if flag_cfg.get("flag") in raw:
        raw = [a for a in raw if a != flag_cfg["flag"]]
        no_desktop = True
    suite_flag = suite_cfg.get("flag", "--suite")
    if suite_flag in raw:
        idx = raw.index(suite_flag)
        if idx + 1 >= len(raw):
            raise ValueError(f"{suite_flag} requires a suite name")
        suite = raw[idx + 1]
        raw = raw[:idx] + raw[idx + 2:]
    limit = None
    if limit_cfg.get("type") == "trailing_positive_int" and raw and raw[-1].isdigit() and int(raw[-1]) > 0:
        limit = int(raw[-1])
        raw = raw[:-1]
    join = str(goal_cfg.get("join", " "))
    goal = join.join(raw).strip()
    return {"goal": goal, "response_limit": limit, "no_desktop": no_desktop, "suite": suite}


def _mermaid_id(node_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", node_id)


def export_mermaid(wiring: dict[str, Any]) -> str:
    """Optional: render topology.nodes/edges as mermaid (not used at runtime)."""
    topo = wiring.get("topology", {})
    lines = [
        "%% endgame-ai wiring — generated from prompts/wiring.json",
        f"%% schema: {wiring.get('schema', '?')}",
        "flowchart TD",
    ]
    for node in topo.get("nodes", []):
        nid = _mermaid_id(str(node["id"]))
        label = str(node.get("label", node["id"])).replace('"', "'")
        ntype = str(node.get("type", ""))
        lines.append(f'  {nid}["{label}<br/>({ntype})"]')
    for edge in topo.get("edges", []):
        src = _mermaid_id(str(edge.get("from", "")))
        tgt = _mermaid_id(str(edge.get("to", "")))
        on = str(edge.get("on", "")).replace('"', "'").replace("|", "/")
        lines.append(f"  {src} -->|{on}| {tgt}")
    return "\n".join(lines) + "\n"


def write_mermaid(wiring: dict[str, Any], path: Path) -> None:
    path.write_text(export_mermaid(wiring), encoding="utf-8")