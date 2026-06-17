"""Slot - the planner/actor/verifier/mutator loop."""
from __future__ import annotations
import json
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm import LLMClient, LLMResult
from bus import Bus, Record


@dataclass
class Task:
    id: str
    description: str
    status: str = "proposed"
    contract: str = ""
    evidence: list[str] = field(default_factory=list)


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
    last_phase: str = ""


class Circuit(ABC):
    @abstractmethod
    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        ...


class Planner(Circuit):
    def __init__(self, prompt_path: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        if not state.goal:
            return None
        context = self._build_context(state, bus)
        result = llm.call(self._system(), context)
        parsed = LLMClient.extract_json(result.text)
        if not parsed:
            return {"phase": "planner.error", "error": "invalid JSON"}
        tasks = self._extract_tasks(parsed, state)
        if not tasks:
            return {"phase": "planner.error", "error": "no tasks"}
        state.tasks = tasks
        if not state.active_task_id:
            state.tasks[0].status = "active"
            state.active_task_id = state.tasks[0].id
        bus.publish("task", "planner", state.active_task_id, {"tasks": [t.id for t in tasks]})
        return {"phase": "plan", "tasks": len(tasks), "next": "actor"}

    def _system(self) -> str:
        return self._prompt or "You are a planner. Return JSON with tasks."

    def _build_context(self, state: SlotState, bus: Bus) -> str:
        parts = [f"GOAL: {state.goal}"]
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:2000]}")
        if state.history:
            parts.append("HISTORY:\n" + "\n".join(
                f"  {json.dumps(h, ensure_ascii=False)[:200]}" for h in state.history[-6:]
            ))
        bus_ctx = bus.format_context(limit=6)
        if bus_ctx:
            parts.append(bus_ctx)
        parts.append(
            'Return JSON: {"tasks":[{"id":"t1","description":"...","contract":"observable condition"}]}'
        )
        return "\n".join(parts)

    def _extract_tasks(self, parsed: dict[str, Any], state: SlotState) -> list[Task]:
        raw_tasks = parsed.get("tasks") or parsed.get("records") or []
        if isinstance(raw_tasks, list):
            tasks = []
            for i, t in enumerate(raw_tasks[:6]):
                if isinstance(t, dict):
                    data = t.get("data", t)
                    tasks.append(Task(
                        id=str(data.get("id", f"t{i+1}")),
                        description=str(data.get("description", "")),
                        contract=str(data.get("contract", data.get("done_when", ""))),
                    ))
            return [t for t in tasks if t.description]
        return []


class Actor(Circuit):
    def __init__(self, prompt_path: Path, workspace: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
        self._workspace = workspace

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        task = self._active_task(state)
        if not task:
            return None
        if self._is_exec(task.description):
            return self._run_exec(task, state, bus)
        context = self._build_context(task, state)
        result = llm.call(self._system(), context)
        parsed = LLMClient.extract_json(result.text)
        if not parsed:
            return {"phase": "actor.error", "error": "invalid JSON"}
        conclusion = str(parsed.get("conclusion", "EXECUTE"))
        if conclusion == "DONE":
            task.status = "claimed_done"
            bus.publish("claim", "actor", task.id, {"statement": "actor claims done"})
            return {"phase": "actor", "conclusion": "DONE", "next": "verifier"}
        if conclusion == "CANNOT":
            task.status = "blocked"
            state.history.append({"blocked": task.description, "reason": "actor cannot"})
            return {"phase": "actor", "conclusion": "CANNOT", "next": "planner"}
        return {"phase": "actor", "conclusion": "EXECUTE", "actions": parsed.get("actions", []), "next": "verifier"}

    def _run_exec(self, task: Task, state: SlotState, bus: Bus) -> dict[str, Any]:
        code = task.description
        for prefix in ("exec:", "exec "):
            if code.lower().startswith(prefix):
                code = code[len(prefix):].strip()
                break
        try:
            kwargs: dict[str, Any] = {
                "cwd": str(self._workspace), "capture_output": True,
                "text": True, "timeout": 60,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = 0x08000000
            proc = subprocess.run([sys.executable, "-c", code], **kwargs)
            output = (proc.stdout or "").strip()
            error = (proc.stderr or "").strip()
            success = proc.returncode == 0
            obs = output or error or f"exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            success, obs = False, "timeout"
        except Exception as e:
            success, obs = False, str(e)
        task.evidence.append(obs[:1000])
        bus.publish("evidence", "tool", task.id, {"output": obs[:1000], "success": success})
        if success:
            task.status = "claimed_done"
            state.history.append({"exec": task.description[:100], "ok": True, "obs": obs[:200]})
            return {"phase": "actor", "ok": True, "obs": obs[:200], "next": "verifier"}
        task.status = "blocked"
        state.history.append({"exec": task.description[:100], "ok": False, "obs": obs[:200]})
        return {"phase": "actor", "ok": False, "obs": obs[:200], "next": "planner"}

    def _active_task(self, state: SlotState) -> Task | None:
        return next((t for t in state.tasks if t.status == "active"), None)

    def _is_exec(self, text: str) -> bool:
        low = text.strip().lower()
        return low.startswith("exec:") or low.startswith("exec ")

    def _system(self) -> str:
        return self._prompt or "You are an actor. Return JSON with actions."

    def _build_context(self, task: Task, state: SlotState) -> str:
        parts = [f"GOAL: {state.goal}", f"TASK: {task.description}"]
        if task.contract:
            parts.append(f"CONTRACT: {task.contract}")
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:2000]}")
        parts.append(
            'Return JSON: {"actions":[{"verb":"click|write|press|hotkey|scroll|focus","target":"id","value":""}],"conclusion":"EXECUTE|DONE|CANNOT"}'
        )
        return "\n".join(parts)


class Verifier(Circuit):
    def __init__(self, prompt_path: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        task = next((t for t in state.tasks if t.status == "claimed_done"), None)
        if not task:
            return None
        context = self._build_context(task, state, bus)
        result = llm.call(self._system(), context, max_tokens=512)
        parsed = LLMClient.extract_json(result.text)
        verdict = str((parsed or {}).get("verdict", "UNKNOWN")).upper()
        because = str((parsed or {}).get("because", result.text[:300]))
        bus.publish("verdict", "verifier", task.id, {"verdict": verdict, "because": because})
        if verdict == "DONE":
            task.status = "verified_done"
            state.fissions += 1
            state.active_task_id = ""
            state.history.append({"verified": task.description, "verdict": "DONE"})
            return {"phase": "verify", "verdict": "DONE", "next": "planner"}
        if verdict == "NOT_DONE":
            task.status = "active"
            state.history.append({"denied": task.description, "reason": because[:200]})
            return {"phase": "verify", "verdict": "NOT_DONE", "because": because, "next": "planner"}
        task.status = "active"
        return {"phase": "verify", "verdict": "UNKNOWN", "next": "actor"}

    def _system(self) -> str:
        return self._prompt or "You are a verifier. Return JSON verdict."

    def _build_context(self, task: Task, state: SlotState, bus: Bus) -> str:
        evidence = bus.query(record_type="evidence", task_id=task.id, limit=5)
        parts = [
            f"TASK: {task.description}",
            f"CONTRACT: {task.contract}",
            f"SCREEN:\n{state.screen[:1500]}" if state.screen else "",
        ]
        if evidence:
            parts.append("EVIDENCE:")
            for r in evidence:
                parts.append(f"  {json.dumps(r.data, ensure_ascii=False)[:300]}")
        if task.evidence:
            parts.append("TASK EVIDENCE:")
            for e in task.evidence[-3:]:
                parts.append(f"  {e[:300]}")
        parts.append('Return JSON: {"verdict":"DONE|NOT_DONE|UNKNOWN","because":"..."}')
        return "\n".join(p for p in parts if p)


class Mutator(Circuit):
    def __init__(self, prompt_path: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
        self._failures = 0

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        denials = sum(1 for h in state.history[-10:] if isinstance(h, dict) and h.get("denied"))
        if denials < 2:
            return None
        context = (
            f"GOAL: {state.goal}\n"
            f"RECENT DENIALS: {denials}\n"
            f"HISTORY: {json.dumps(state.history[-4:], ensure_ascii=False)[:1000]}\n"
            "Suggest a prompt improvement for the actor or verifier."
        )
        result = llm.call(self._system(), context, max_tokens=512)
        bus.publish("mutation", "mutator", state.active_task_id or "", {"suggestion": result.text[:500]})
        return {"phase": "mutate", "suggestion": result.text[:200]}

    def _system(self) -> str:
        return self._prompt or "You are a mutator. Suggest prompt improvements."


class Slot:
    """One autonomous planner->actor->verifier->mutator loop."""

    def __init__(self, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path):
        self.llm = llm
        self.bus = bus
        self.state = SlotState()
        self.planner = Planner(prompts_dir / "planner.txt")
        self.actor = Actor(prompts_dir / "actor.txt", workspace)
        self.verifier = Verifier(prompts_dir / "verifier.txt")
        self.mutator = Mutator(prompts_dir / "mutator.txt")

    def set_goal(self, goal: str):
        self.state.goal = goal
        self.state.tasks = []
        self.state.active_task_id = ""

    def step(self) -> dict[str, Any] | None:
        self.state.cycles += 1
        active = next((t for t in self.state.tasks if t.status == "active"), None)
        claimed = next((t for t in self.state.tasks if t.status == "claimed_done"), None)
        if claimed:
            return self.verifier.run(self.state, self.llm, self.bus)
        if active:
            return self.actor.run(self.state, self.llm, self.bus)
        self.mutator.run(self.state, self.llm, self.bus)
        result = self.planner.run(self.state, self.llm, self.bus)
        if result and result.get("next") == "actor":
            self.state.last_phase = "plan"
        return result

    def observe(self, screen: str, elements: dict[str, Any]):
        self.state.screen = screen
        self.state.screen_elements = elements
