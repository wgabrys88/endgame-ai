"""Slot - generic Circuit + data-driven state machine. All wiring from config."""
from __future__ import annotations
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm import LLMClient, LLMResult
from bus import Bus

_log = logging.getLogger("endgame")


@dataclass
class Task:
    id: str
    description: str
    status: str = "proposed"
    contract: str = ""
    evidence: list[str] = field(default_factory=list)
    attempts: int = 0


@dataclass
class SlotState:
    goal: str = ""
    tasks: list[Task] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    active_task_id: str = ""
    screen: str = ""
    screen_elements: dict[str, Any] = field(default_factory=dict)
    cycles: int = 0
    fissions: int = 0
    phase: str = "planner"
    diagnosis: str = ""
    last_action_error: str = ""
    reasoning_history: list[dict[str, str]] = field(default_factory=list)
    _last_actions: list = field(default_factory=list)


def run_script(code: str, workspace: Path, timeout: int = 60) -> tuple[bool, str]:
    try:
        kwargs: dict[str, Any] = {"cwd": str(workspace), "capture_output": True, "text": True, "timeout": timeout}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000
        proc = subprocess.run([sys.executable, "-c", code], **kwargs)
        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        return proc.returncode == 0, (output or error or f"exit {proc.returncode}")
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


class Circuit:
    """Generic circuit driven by wiring config. Resolves context, calls LLM, interprets result."""

    def __init__(self, name: str, wiring: dict[str, Any], prompts_dir: Path, workspace: Path):
        self.name = name
        self._wiring = wiring
        self._workspace = workspace
        cfg = wiring["circuits"][name]
        self._inject = cfg["inject"]
        prompt_path = prompts_dir / cfg["prompt"]
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else f"You are a {name}."
        self._max_attempts = wiring["limits"]["max_attempts"]
        self._reasoning_depth = wiring["limits"]["reasoning_history_depth"]

    def _resolve_context(self, state: SlotState, bus: Bus) -> str:
        parts: list[str] = []
        task = next((t for t in state.tasks if t.status in ("active", "claimed_done")), None)
        for field_name in self._inject:
            val = self._get_field(field_name, state, task, bus)
            if val:
                parts.append(f"{field_name.upper().replace('_', ' ')}: {val}")
        return "\n".join(parts)

    def _get_field(self, name: str, state: SlotState, task: Task | None, bus: Bus) -> str:
        if name == "goal":
            return state.goal
        if name == "screen":
            return state.screen if state.screen else ""
        if name == "task":
            return task.description if task else ""
        if name == "contract":
            return task.contract if task else ""
        if name == "last_error":
            err = state.last_action_error
            if err:
                state.last_action_error = ""
            return err
        if name == "last_reasoning":
            if not state.reasoning_history:
                return ""
            entries = state.reasoning_history[-self._reasoning_depth:]
            return "\n".join(f"[attempt] {e.get('reasoning','')} → {e.get('outcome','')}" for e in entries)
        if name == "history":
            if not state.history:
                return ""
            return "\n".join(f"  {json.dumps(h, ensure_ascii=False)}" for h in state.history[-6:])
        if name == "bus_context":
            return bus.format_context(limit=6)
        if name == "evidence":
            if not task:
                return ""
            evidence = bus.query(record_type="evidence", task_id=task.id, limit=5)
            parts = [f"  {json.dumps(r.data, ensure_ascii=False)[:1000]}" for r in evidence]
            if task.evidence:
                parts += [f"  {e[:1000]}" for e in task.evidence[-3:]]
            return "\n".join(parts) if parts else ""
        if name == "denials":
            denials = [h for h in state.history[-6:] if isinstance(h, dict) and h.get("denied")]
            return "\n".join(f"  {json.dumps(d, ensure_ascii=False)[:1000]}" for d in denials[-3:]) if denials else ""
        if name == "diagnosis":
            return state.diagnosis
        if name == "workspace":
            return f"{self._workspace}\nPROMPTS DIR: {self._workspace / 'prompts'}"
        return ""

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any]:
        ctx = self._resolve_context(state, bus)
        result = llm.call(self._prompt, ctx) if ctx else LLMResult(text="")
        _log.debug("[%s] prompt=%d ctx=%d → response=%d reasoning=%d",
                   self.name, len(self._prompt), len(ctx),
                   len(result.text), len(result.reasoning))
        return self._interpret(result, state, bus)

    def _interpret(self, result: LLMResult, state: SlotState, bus: Bus) -> dict[str, Any]:
        try:
            record = json.loads(result.text)
            rtype, data = str(record["record_type"]), record["data"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return {"event": f"{self.name}_error", "error": "parse_failed"}

        if self.name == "unified":
            return self._interpret_unified(data, result, state, bus)
        if self.name == "planner":
            return self._interpret_plan(data, state, bus)
        if self.name == "actor":
            return self._interpret_action(data, result, state, bus)
        if self.name == "verifier":
            return self._interpret_verdict(data, state, bus)
        if self.name == "reflector":
            return self._interpret_reflect(data, result, state, bus)
        if self.name == "mutator":
            return self._interpret_mutate(data, result, state, bus)
        return {"event": f"{self.name}_error"}

    def _interpret_unified(self, data: dict, result: LLMResult, state: SlotState, bus: Bus) -> dict[str, Any]:
        """Unified agent: simple observe→act loop without task management."""
        reasoning_entry = {"reasoning": result.reasoning[:2000], "outcome": ""}
        conclusion = str(data.get("conclusion", "EXECUTE"))
        if conclusion == "DONE":
            # Guard: check if reasoning history shows we actually did something
            # For compound goals with "type/write", require a write action in history
            goal_lower = state.goal.lower()
            has_write_goal = any(w in goal_lower for w in ("type", "write", "enter text"))
            did_write = any("write" in str(h.get("outcome", "")) or "typed" in str(h.get("outcome", ""))
                           for h in state.reasoning_history)
            if has_write_goal and not did_write:
                # Premature DONE — override to continue
                reasoning_entry["outcome"] = "SYSTEM: goal requires typing but no write was done yet"
                state.reasoning_history.append(reasoning_entry)
                return {"event": "unified_acted", "conclusion": "EXECUTE", "actions": []}
            reasoning_entry["outcome"] = "goal complete"
            state.reasoning_history.append(reasoning_entry)
            return {"event": "goal_complete", "conclusion": "DONE"}
        if conclusion == "CANNOT":
            reasoning_entry["outcome"] = "cannot"
            state.reasoning_history.append(reasoning_entry)
            return {"event": "unified_cannot", "conclusion": "CANNOT"}
        # EXECUTE — check for repeat
        actions = data.get("actions", [])
        if state.reasoning_history and actions:
            last = state.reasoning_history[-1]
            if "OK" in last.get("outcome", "") and actions == state._last_actions:
                state.reasoning_history.append({"reasoning": "", "outcome": "SYSTEM: repeated action — move to next step"})
        state._last_actions = actions
        bus.publish("action", "unified", state.active_task_id or "", data)
        return {"event": "unified_acted", "conclusion": "EXECUTE",
                "actions": actions, "reasoning_entry": reasoning_entry}

    def _interpret_plan(self, data: dict, state: SlotState, bus: Bus) -> dict[str, Any]:
        raw = data.get("tasks", [])
        tasks: list[Task] = []
        for i, t in enumerate(raw[:6] if isinstance(raw, list) else []):
            if isinstance(t, dict):
                desc = str(t.get("description", ""))
                if desc:
                    tasks.append(Task(id=str(t.get("id", f"t{i+1}")), description=desc,
                                      contract=str(t.get("contract", ""))))
        if not tasks:
            # Empty plan after verified work = goal complete
            if state.fissions > 0 or any(h.get("verified") for h in state.history if isinstance(h, dict)):
                return {"event": "goal_complete"}
            return {"event": "planner_error", "error": "no tasks"}
        state.tasks = tasks
        state.tasks[0].status = "active"
        state.active_task_id = tasks[0].id
        state.reasoning_history = []
        bus.publish("task", "planner", state.active_task_id, data)
        return {"event": "plan_done", "tasks": len(tasks), "next": "actor"}

    def _interpret_action(self, data: dict, result: LLMResult, state: SlotState, bus: Bus) -> dict[str, Any]:
        task = next((t for t in state.tasks if t.status == "active"), None)
        if not task:
            return {"event": "execute_cannot"}
        # Store reasoning for feedback loop
        reasoning_entry = {"reasoning": result.reasoning[:2000], "outcome": ""}
        conclusion = str(data.get("conclusion", "EXECUTE"))
        if conclusion == "DONE":
            task.status = "claimed_done"
            reasoning_entry["outcome"] = "claimed done"
            state.reasoning_history.append(reasoning_entry)
            bus.publish("claim", "actor", task.id, data)
            return {"event": "execute_done", "conclusion": "DONE", "next": "verifier"}
        if conclusion == "CANNOT":
            task.status = "blocked"
            state.history.append({"blocked": task.description, "reason": "cannot"})
            reasoning_entry["outcome"] = "cannot"
            state.reasoning_history.append(reasoning_entry)
            return {"event": "execute_cannot", "conclusion": "CANNOT", "next": "planner"}
        # EXECUTE — check for repeat: if last reasoning shows same action succeeded, auto-advance
        actions = data.get("actions", [])
        if state.reasoning_history and actions:
            last = state.reasoning_history[-1]
            last_outcome = last.get("outcome", "")
            if "OK" in last_outcome and actions == state._last_actions:
                # Same action repeated after success — task is done, skip verifier
                task.status = "verified_done"
                state.fissions += 1
                reasoning_entry["outcome"] = "auto-advanced (repeated successful action)"
                state.reasoning_history.append(reasoning_entry)
                state.history.append({"verified": task.description, "verdict": "auto"})
                state.active_task_id = ""
                state._last_actions = []
                # Advance to next task or re-plan
                next_task = next((t for t in state.tasks if t.status == "proposed"), None)
                if next_task:
                    next_task.status = "active"
                    state.active_task_id = next_task.id
                    state.reasoning_history = []
                    return {"event": "verify_done_advance", "conclusion": "DONE", "next": "actor"}
                return {"event": "verify_done", "conclusion": "DONE", "next": "planner"}
        state._last_actions = actions
        bus.publish("action", "actor", task.id, data)
        return {"event": "execute_acted", "conclusion": "EXECUTE",
                "actions": actions, "reasoning_entry": reasoning_entry}

    def _interpret_verdict(self, data: dict, state: SlotState, bus: Bus) -> dict[str, Any]:
        task = next((t for t in state.tasks if t.status == "claimed_done"), None)
        if not task:
            return {"event": "verify_unknown"}
        verdict = str(data.get("verdict", "UNKNOWN")).upper()
        because = str(data.get("because", ""))[:300]
        bus.publish("verdict", "verifier", task.id, data)
        if verdict == "DONE":
            task.status = "verified_done"
            state.fissions += 1
            state.active_task_id = ""
            state.history.append({"verified": task.description, "verdict": "DONE"})
            state.reasoning_history = []
            # Auto-advance to next proposed task if one exists
            next_task = next((t for t in state.tasks if t.status == "proposed"), None)
            if next_task:
                next_task.status = "active"
                state.active_task_id = next_task.id
                return {"event": "verify_done_advance", "verdict": "DONE", "next": "actor"}
            return {"event": "verify_done", "verdict": "DONE", "next": "planner"}
        if verdict == "NOT_DONE":
            task.status = "active"
            state.history.append({"denied": task.description, "reason": because})
            return {"event": "verify_not_done", "verdict": "NOT_DONE", "because": because}
        task.status = "active"
        return {"event": "verify_unknown", "verdict": "UNKNOWN"}

    def _interpret_reflect(self, data: dict, result: LLMResult, state: SlotState, bus: Bus) -> dict[str, Any]:
        diagnosis = str(data.get("diagnosis", ""))[:1000] or "unknown failure"
        suggestion = str(data.get("suggestion", ""))[:1000]
        state.diagnosis = diagnosis
        # Store reflector reasoning for its own feedback loop
        state.reasoning_history.append({"reasoning": result.reasoning[:2000], "outcome": f"diagnosis: {diagnosis[:500]}"})
        bus.publish("diagnosis", "reflector", state.active_task_id or "", {"diagnosis": diagnosis, "suggestion": suggestion})
        return {"event": "reflect_done", "diagnosis": diagnosis[:200]}

    def _interpret_mutate(self, data: dict, result: LLMResult, state: SlotState, bus: Bus) -> dict[str, Any]:
        code = str(data.get("code", "")).strip()
        if not code:
            state.diagnosis = ""
            return {"event": "mutate_done", "ok": False, "reason": "empty script"}
        success, obs = run_script(code, self._workspace)
        bus.publish("mutation", "mutator", state.active_task_id or "",
                    {"code": code[:500], "success": success, "output": obs[:300]})
        state.diagnosis = ""
        return {"event": "mutate_done", "ok": success, "obs": obs[:200]}


class Slot:
    """Data-driven state machine. Phase transitions from wiring.json."""

    def __init__(self, name: str, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path,
                 wiring: dict[str, Any], *, can_act_desktop: bool = True):
        self.name = name
        self.llm = llm
        self.bus = bus
        self.state = SlotState()
        self.can_act_desktop = can_act_desktop
        self._wiring = wiring
        self._transitions = wiring["transitions"]
        self._max_attempts = wiring["limits"]["max_attempts"]
        self._bus_throttle = wiring["limits"]["bus_check_throttle_s"]
        self._last_bus_check: float = 0
        self._mode = wiring["slots"].get(name, {}).get("mode", "planner")
        self.circuits: dict[str, Circuit] = {
            n: Circuit(n, wiring, prompts_dir, workspace) for n in wiring["circuits"]
        }

    def set_goal(self, goal: str):
        self.state.goal = goal
        self.state.tasks = []
        self.state.active_task_id = ""
        self.state.history = []
        self.state.diagnosis = ""
        self.state.phase = self._mode  # "unified" or "planner"
        self.state.reasoning_history = []
        self.state._last_actions = []

    def check_bus(self) -> bool:
        now = time.time()
        if now - self._last_bus_check < self._bus_throttle:
            return False
        self._last_bus_check = now
        for r in reversed(self.bus.query(record_type="route", limit=10)):
            if r.data.get("to") != self.name or r.data.get("status") != "open":
                continue
            # Check dependency: if "after" is set, prerequisite must be verified_done
            after = r.data.get("after")
            if after is not None:
                prereq = next((pr for pr in self.bus.records
                               if pr.record_type == "route" and pr.data.get("seq") == after), None)
                if not prereq or prereq.data.get("status") != "verified_done":
                    continue
            goal = str(r.data.get("goal", ""))
            if goal and goal != self.state.goal:
                self.set_goal(goal)
                r.data["status"] = "accepted"
                return True
        return False

    def step(self) -> dict[str, Any] | None:
        self.check_bus()
        if not self.state.goal:
            return None
        self.state.cycles += 1
        # Check max attempts before actor runs
        task = next((t for t in self.state.tasks if t.status == "active"), None)
        if task and self.state.phase == "actor":
            task.attempts += 1
            if task.attempts > self._max_attempts:
                task.status = "blocked"
                state = self.state
                state.diagnosis = f"Task '{task.description}' failed after {self._max_attempts} attempts"
                state.history.append({"blocked": task.description, "reason": state.diagnosis})
                # Transition via wiring
                next_phase = self._transitions.get("max_attempts", "planner")
                self.state.phase = next_phase
                return {"event": "max_attempts", "phase": "actor", "ok": False, "reason": "max_attempts"}
        # Handle exec: tasks directly (no LLM call)
        if task and self.state.phase == "actor" and task.description.strip().lower().startswith("exec"):
            return self._exec_task(task)
        # Run current circuit
        circuit = self.circuits.get(self.state.phase)
        if not circuit:
            self.state.phase = "planner"
            circuit = self.circuits["planner"]
        result = circuit.run(self.state, self.llm, self.bus)
        # Handle goal_complete: mark route done, clear goal, go idle
        event = result.get("event", "")
        if event == "goal_complete":
            self._complete_goal()
            result["phase"] = "planner"
            return result
        # Transition
        next_phase = self._transitions.get(event, "planner")
        self.state.phase = next_phase
        result["phase"] = circuit.name
        return result

    def _complete_goal(self):
        """Goal achieved. Mark route done on bus, clear state, go idle."""
        for r in self.bus.records:
            if (r.record_type == "route" and r.data.get("to") == self.name
                    and r.data.get("goal") == self.state.goal and r.data.get("status") == "accepted"):
                seq = r.data.get("seq")
                if seq is not None:
                    self.bus.mark_route_done(seq)
                r.data["status"] = "verified_done"
                break
        self.state.goal = ""
        self.state.tasks = []
        self.state.phase = "planner"

    def _exec_task(self, task: Task) -> dict[str, Any]:
        code = task.description
        for prefix in ("exec:", "exec "):
            if code.lower().startswith(prefix):
                code = code[len(prefix):].strip()
                break
        success, obs = run_script(code, self._wiring.get("_workspace", Path(".")))
        task.evidence.append(obs)
        self.bus.publish("evidence", "tool", task.id, {"output": obs, "success": success})
        self.state.history.append({"exec": task.description[:100], "ok": success, "obs": obs[:200]})
        if success:
            task.status = "claimed_done"
            self.state.phase = "verifier"
            return {"phase": "actor", "event": "execute_done", "ok": True, "obs": obs[:200], "next": "verifier"}
        task.status = "blocked"
        self.state.phase = "planner"
        return {"phase": "actor", "event": "execute_cannot", "ok": False, "obs": obs[:200], "next": "planner"}

    def observe(self, screen: str, elements: dict[str, Any]):
        self.state.screen = screen
        self.state.screen_elements = elements
