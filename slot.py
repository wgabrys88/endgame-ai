"""Slot - the planner/actor/verifier/reflector/mutator loop. Unified record schema."""
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

MAX_TASK_ATTEMPTS = 5


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
    last_phase: str = ""
    diagnosis: str = ""


def run_script(code: str, workspace: Path, timeout: int = 60) -> tuple[bool, str]:
    """Execute a Python script once. Returns (success, output)."""
    try:
        kwargs: dict[str, Any] = {
            "cwd": str(workspace), "capture_output": True, "text": True, "timeout": timeout,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000
        proc = subprocess.run([sys.executable, "-c", code], **kwargs)
        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        return proc.returncode == 0, (output or error or f"exit {proc.returncode}")[:1000]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:500]


def _parse_record(result: LLMResult) -> dict[str, Any] | None:
    """Parse LLM output as unified record {record_type, data}."""
    parsed = LLMClient.extract_json(result.text)
    if not parsed:
        return None
    if "record_type" in parsed and "data" in parsed:
        return parsed
    # Fallback: wrap non-schema output for backward compat with models that ignore schema
    if "tasks" in parsed:
        return {"record_type": "task", "data": parsed}
    if "verdict" in parsed:
        return {"record_type": "verdict", "data": parsed}
    if "actions" in parsed or "conclusion" in parsed:
        return {"record_type": "action", "data": parsed}
    if "diagnosis" in parsed:
        return {"record_type": "diagnosis", "data": parsed}
    if "code" in parsed:
        return {"record_type": "mutation", "data": parsed}
    return {"record_type": "unknown", "data": parsed}


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
        parts = [f"GOAL: {state.goal}"]
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:2000]}")
        if state.history:
            parts.append("HISTORY:\n" + "\n".join(
                f"  {json.dumps(h, ensure_ascii=False)[:200]}" for h in state.history[-6:]))
        bus_ctx = bus.format_context(limit=6)
        if bus_ctx:
            parts.append(bus_ctx)
        result = llm.call(self._prompt or "You are a planner. Create one actionable task.", "\n".join(parts))
        record = _parse_record(result)
        if not record or record["record_type"] != "task":
            return {"phase": "planner.error", "error": "invalid response"}
        data = record["data"]
        raw = data.get("tasks", [])
        tasks = []
        for i, t in enumerate(raw[:6] if isinstance(raw, list) else []):
            if isinstance(t, dict):
                d = t.get("data", t)
                desc = str(d.get("description", ""))
                if desc:
                    tasks.append(Task(
                        id=str(d.get("id", f"t{i+1}")), description=desc,
                        contract=str(d.get("contract", d.get("done_when", ""))),
                    ))
        if not tasks:
            return {"phase": "planner.error", "error": "no tasks"}
        state.tasks = tasks
        state.tasks[0].status = "active"
        state.active_task_id = state.tasks[0].id
        bus.publish("task", "planner", state.active_task_id, data)
        return {"phase": "plan", "tasks": len(tasks), "next": "actor"}


class Actor(Circuit):
    def __init__(self, prompt_path: Path, workspace: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
        self._workspace = workspace

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        task = next((t for t in state.tasks if t.status == "active"), None)
        if not task:
            return None
        task.attempts += 1
        if task.attempts > MAX_TASK_ATTEMPTS:
            task.status = "blocked"
            state.history.append({"blocked": task.description, "reason": f"exceeded {MAX_TASK_ATTEMPTS} attempts"})
            bus.publish("runtime_event", "runtime", task.id, {"event": "task_abandoned"})
            return {"phase": "actor", "ok": False, "reason": "max_attempts", "next": "planner"}
        if task.description.strip().lower().startswith("exec"):
            code = task.description
            for prefix in ("exec:", "exec "):
                if code.lower().startswith(prefix):
                    code = code[len(prefix):].strip()
                    break
            success, obs = run_script(code, self._workspace)
            task.evidence.append(obs)
            bus.publish("evidence", "tool", task.id, {"output": obs, "success": success})
            state.history.append({"exec": task.description[:100], "ok": success, "obs": obs[:200]})
            if success:
                task.status = "claimed_done"
                return {"phase": "actor", "ok": True, "obs": obs[:200], "next": "verifier"}
            task.status = "blocked"
            return {"phase": "actor", "ok": False, "obs": obs[:200], "next": "planner"}
        parts = [f"GOAL: {state.goal}", f"TASK: {task.description}"]
        if task.contract:
            parts.append(f"CONTRACT: {task.contract}")
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:2000]}")
        result = llm.call(self._prompt or "You are an actor. Execute the task.", "\n".join(parts))
        record = _parse_record(result)
        if not record or record["record_type"] != "action":
            return {"phase": "actor.error", "error": "invalid response"}
        data = record["data"]
        conclusion = str(data.get("conclusion", "EXECUTE"))
        if conclusion == "DONE":
            task.status = "claimed_done"
            bus.publish("claim", "actor", task.id, data)
            return {"phase": "actor", "conclusion": "DONE", "next": "verifier"}
        if conclusion == "CANNOT":
            task.status = "blocked"
            state.history.append({"blocked": task.description, "reason": "cannot"})
            return {"phase": "actor", "conclusion": "CANNOT", "next": "planner"}
        bus.publish("action", "actor", task.id, data)
        return {"phase": "actor", "conclusion": "EXECUTE", "actions": data.get("actions", []), "next": "verifier"}


class Verifier(Circuit):
    def __init__(self, prompt_path: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        task = next((t for t in state.tasks if t.status == "claimed_done"), None)
        if not task:
            return None
        parts = [f"TASK: {task.description}", f"CONTRACT: {task.contract}"]
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:1500]}")
        evidence = bus.query(record_type="evidence", task_id=task.id, limit=5)
        if evidence:
            parts.append("EVIDENCE:\n" + "\n".join(
                f"  {json.dumps(r.data, ensure_ascii=False)[:300]}" for r in evidence))
        if task.evidence:
            parts.append("TASK OUTPUT:\n" + "\n".join(f"  {e[:300]}" for e in task.evidence[-3:]))
        result = llm.call(self._prompt or "You are a verifier. Judge evidence against contract.", "\n".join(parts), max_tokens=512)
        record = _parse_record(result)
        if not record or record["record_type"] != "verdict":
            return {"phase": "verify", "verdict": "UNKNOWN", "because": "invalid response", "next": "actor"}
        data = record["data"]
        verdict = str(data.get("verdict", "UNKNOWN")).upper()
        because = str(data.get("because", ""))[:300]
        bus.publish("verdict", "verifier", task.id, data)
        if verdict == "DONE":
            task.status = "verified_done"
            state.fissions += 1
            state.active_task_id = ""
            state.history.append({"verified": task.description, "verdict": "DONE"})
            return {"phase": "verify", "verdict": "DONE", "next": "planner"}
        if verdict == "NOT_DONE":
            task.status = "active"
            state.history.append({"denied": task.description, "reason": because})
            return {"phase": "verify", "verdict": "NOT_DONE", "because": because, "next": "reflector"}
        task.status = "active"
        return {"phase": "verify", "verdict": "UNKNOWN", "next": "actor"}


class Reflector(Circuit):
    """Diagnoses what went wrong. Feeds diagnosis to Mutator."""

    def __init__(self, prompt_path: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        denials = [h for h in state.history[-6:] if isinstance(h, dict) and h.get("denied")]
        if not denials:
            return None
        parts = [f"GOAL: {state.goal}",
                 "DENIALS:\n" + "\n".join(f"  {json.dumps(d, ensure_ascii=False)[:200]}" for d in denials[-3:])]
        if state.screen:
            parts.append(f"SCREEN:\n{state.screen[:800]}")
        result = llm.call(self._prompt or "Diagnose the root cause of failure.", "\n".join(parts), max_tokens=512)
        record = _parse_record(result)
        if record and record["record_type"] == "diagnosis":
            diagnosis = str(record["data"].get("diagnosis", ""))[:500]
        else:
            diagnosis = result.text[:500]
        state.diagnosis = diagnosis
        bus.publish("diagnosis", "reflector", state.active_task_id or "", {"diagnosis": diagnosis})
        return {"phase": "reflect", "diagnosis": diagnosis[:200], "next": "mutator"}


class Mutator(Circuit):
    """Writes and executes a one-shot mutation script based on reflector diagnosis."""

    def __init__(self, prompt_path: Path, workspace: Path):
        self._prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
        self._workspace = workspace

    def run(self, state: SlotState, llm: LLMClient, bus: Bus) -> dict[str, Any] | None:
        if not state.diagnosis:
            return None
        parts = [f"DIAGNOSIS: {state.diagnosis}", f"GOAL: {state.goal}",
                 f"WORKSPACE: {self._workspace}", f"PROMPTS DIR: {self._workspace / 'prompts'}"]
        result = llm.call(self._prompt or "Write a one-shot Python fix script.", "\n".join(parts),
                          max_tokens=1024, schema=False)
        # Mutator returns raw code, not JSON record
        code = result.text.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        # If schema was enforced anyway, extract code from data field
        parsed = LLMClient.extract_json(code)
        if parsed and "code" in parsed:
            code = str(parsed["code"])
        if not code:
            return {"phase": "mutate", "ok": False, "reason": "empty script"}
        success, obs = run_script(code, self._workspace)
        bus.publish("mutation", "mutator", state.active_task_id or "",
                    {"code": code[:500], "success": success, "output": obs[:300]})
        state.diagnosis = ""
        return {"phase": "mutate", "ok": success, "obs": obs[:200]}


class Slot:
    """One autonomous planner->actor->verifier->reflector->mutator loop."""

    def __init__(self, name: str, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path,
                 *, can_act_desktop: bool = True):
        self.name = name
        self.llm = llm
        self.bus = bus
        self.state = SlotState()
        self.can_act_desktop = can_act_desktop
        self._workspace = workspace
        self._personality = self._load_personality(prompts_dir, name)
        self.planner = Planner(prompts_dir / "planner.txt")
        self.actor = Actor(prompts_dir / "actor.txt", workspace)
        self.verifier = Verifier(prompts_dir / "verifier.txt")
        self.reflector = Reflector(prompts_dir / "reflector.txt")
        self.mutator = Mutator(prompts_dir / "mutator.txt", workspace)
        self._last_bus_check: float = 0

    def _load_personality(self, prompts_dir: Path, name: str) -> str:
        for path in (prompts_dir / name / "personality.txt", prompts_dir / "personalities" / f"{name}.txt"):
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        return ""

    def set_goal(self, goal: str):
        self.state.goal = goal
        self.state.tasks = []
        self.state.active_task_id = ""
        self.state.history = []
        self.state.diagnosis = ""

    def check_bus(self) -> bool:
        now = time.time()
        if now - self._last_bus_check < 3.0:
            return False
        self._last_bus_check = now
        for r in reversed(self.bus.query(record_type="route", limit=10)):
            if r.data.get("to") == self.name and r.data.get("status") == "open":
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
        if self.state.diagnosis:
            return self.mutator.run(self.state, self.llm, self.bus)
        claimed = next((t for t in self.state.tasks if t.status == "claimed_done"), None)
        if claimed:
            result = self.verifier.run(self.state, self.llm, self.bus)
            if result and result.get("next") == "reflector":
                return self.reflector.run(self.state, self.llm, self.bus) or result
            return result
        active = next((t for t in self.state.tasks if t.status == "active"), None)
        if active:
            return self.actor.run(self.state, self.llm, self.bus)
        return self.planner.run(self.state, self.llm, self.bus)

    def observe(self, screen: str, elements: dict[str, Any]):
        self.state.screen = screen
        self.state.screen_elements = elements
