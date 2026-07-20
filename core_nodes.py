from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import traceback
import types
from abc import ABC
from typing import Any, Callable

import core_brain as brain
import core_bus as bus
import core_wiring as wiring

JsonDict = dict[str, Any]
ROOT = pathlib.Path(__file__).parent.resolve()


class BaseNode(ABC):
    prompt_key: str = ""
    expected_record_type: str = ""
    contract: str = ""

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        st = ctx.get("state", {})
        return {
            "goal": st.get("goal", ctx.get("goal", "")),
            "state": bus.state_brief(st),
            "environment": bus.environment_brief(st),
        }

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: JsonDict) -> bus.Record:
        w = ctx["wiring"]
        explore(ctx)
        payload = self.build_payload(ctx)
        payload["goal"] = ctx["state"]["goal"]
        record = brain.think(
            wiring.prompt(w, self.prompt_key),
            payload,
            w,
            expected_record_type=self.expected_record_type,
            emitting_node=ctx.get("node"),
        )
        if record.get("record_type") != self.expected_record_type:
            raise bus.NodeRecordContractError(
                f"{self.prompt_key} expected record_type {self.expected_record_type!r}, "
                f"got {record.get('record_type')!r}"
            )
        return bus.Record.from_json(record)

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        record = self.think(ctx)
        return bus.emit(self.signal_from_data(record.data, ctx), self.patch_from_record(record, ctx))


class GuidanceNode:
    contract = "[node_guidance] — Thou receivest the [guidance] file."

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        path = wiring.root_path(ctx["wiring"]["paths"]["guidance"])
        counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
        if counsel:
            path.write_text("", encoding="utf-8")
        return bus.emit("attend", {"latest_counsel": counsel})


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"
    contract = "[node_execute] — Thou receivest the fresh [environment] and any [action_frame]."

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "action_frame": state.get("action_frame"),
            "prior_attempt": state.get("deed_retry") or None,
            "state": bus.state_brief(state),
            "environment": bus.environment_brief(state),
        }

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        state = ctx["state"]
        record = self.think(ctx)
        data = record.data
        code = data["code"]
        intent = str(data["intent"]).strip()
        if not intent:
            raise RuntimeError("execution requires non-empty intent")
        deed_fault = None
        ns = build_capability_runtime(ctx)
        try:
            exec(code, ns)
        except Exception:
            deed_fault = traceback.format_exc()
        base_patch: JsonDict = {
            "current_deed": {"description": intent},
            "goal_interpretations": bus.with_interpretation(
                state.get("goal_interpretations"), "execute", str(data.get("goal_interpretation") or "")
            ),
            "turn_executions": {
                "exec": {
                    "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
                    "code_chars": len(code),
                    "deed_fault": deed_fault,
                }
            },
            "last_action_at": time.time(),
            "action_frame": None,
            "last_verification": None,
        }
        if deed_fault is None:
            base_patch["deed_retry"] = None
            return bus.emit("done", base_patch)
        max_retries = int(ctx["wiring"]["exploration"]["max_deed_retries"])
        prior = state.get("deed_retry") or {}
        attempts_so_far = int(prior.get("attempts", 0))
        if attempts_so_far < max_retries:
            base_patch["deed_retry"] = {
                "attempts": attempts_so_far + 1,
                "intent": intent,
                "reasoning": str(record.reasoning or ""),
                "fault": deed_fault,
                "only_hwnds": _hwnds_referenced(code, state.get("action_index") or {}),
            }
            return bus.emit("deed_retry", base_patch)
        base_patch["deed_retry"] = None
        return bus.emit("deed_denied", base_patch)


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"
    contract = (
        "[node_verify] — Thou receivest the [goal], the last [deed] (its description and hour of action), "
        "the [state] brief, and the fresh [environment]."
    )

    def _deed(self, ctx: JsonDict) -> str:
        state = ctx["state"]
        deed = state.get("current_deed") or {}
        return deed.get("description", state["goal"])

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "deed": {"description": self._deed(ctx), "acted_at": state.get("last_action_at")},
            "state": bus.state_brief(state),
            "environment": bus.environment_brief(state),
        }

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        state = ctx["state"]
        record = self.think(ctx)
        probe_fault = None
        verdict = None
        ns = build_capability_runtime(ctx, read_only=True)
        try:
            exec(record.data["code"], ns)
            verdict = ns.get("verdict")
            if (
                not isinstance(verdict, dict)
                or not isinstance(verdict.get("goal_satisfied"), bool)
                or not isinstance(verdict.get("deed_confirmed"), bool)
                or not isinstance(verdict.get("reason"), str)
                or not verdict["reason"].strip()
            ):
                raise RuntimeError(
                    "verification probe must set verdict with boolean goal_satisfied/deed_confirmed and non-blank reason"
                )
        except Exception:
            probe_fault = traceback.format_exc()

        if probe_fault is not None:
            note = (
                "The read-only probe I authored raised ere it set a verdict, so this deed standeth "
                "UNJUDGED — this is neither the actor's failing nor a fault in any node file, for the "
                "probe is transient code I write anew each witnessing. I shall author a simpler probe "
                "that runneth, and touch no body file.\n" + probe_fault
            )
            return bus.emit(
                "unwitnessed",
                {
                    "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", note),
                    "last_verification": {"success": False, "signal": "unwitnessed", "reasoning": probe_fault},
                },
            )

        assert verdict is not None
        goal_satisfied = verdict["goal_satisfied"]
        deed_confirmed = verdict["deed_confirmed"]
        reason = verdict["reason"]
        signal = "halt" if goal_satisfied else ("deed_confirmed" if deed_confirmed else "deed_denied")
        desc = self._deed(ctx)
        confirmed = goal_satisfied or deed_confirmed
        patch: JsonDict = {
            "verification": {
                "goal_satisfied": goal_satisfied,
                "deed_confirmed": deed_confirmed,
                "reasoning": reason,
                "deed_goal": desc,
            },
            "last_verification": {"success": confirmed, "signal": signal, "reasoning": reason},
            "goal_interpretations": bus.with_interpretation(
                state.get("goal_interpretations"), "verify", str(record.data.get("goal_interpretation") or "")
            ),
        }
        if confirmed:
            patch.update({
                "failure_streak": {"count": 0},
                "action_frame": None,
                "current_deed": None,
            })
        return bus.emit(signal, patch)


class RecoverNode(BaseNode):
    prompt_key = "node_recover"
    expected_record_type = "recovery"
    contract = (
        "[node_recover] — Thou receivest the denied deed, its evidence and [failure_streak], "
        "and the fresh [environment]."
    )

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        self._streak_patch = bus.bump_failure_streak(state)
        deed = state.get("current_deed") or {}
        return {
            "goal": state["goal"],
            "deed": {"description": deed.get("description", state["goal"])},
            "state": bus.state_brief(state),
            "evidence": {
                "executions": bus.execution_evidence(state),
                "last_verification": state.get("last_verification", {}),
                "failure_streak": self._streak_patch["failure_streak"],
            },
            "environment": bus.environment_brief(state),
        }

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        return "recovered"

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        data, state = record.data, ctx["state"]
        deed = state.get("current_deed") or {}
        return {
            **self._streak_patch,
            "action_frame": {
                "target": data["target"],
                "strategy": data["strategy"],
                "lesson": data["lesson"],
            },
            "last_recovery": {
                "lesson": data["lesson"],
                "target": data["target"],
                "strategy": data["strategy"],
                "deed_goal": deed.get("description", state["goal"]),
            },
            "goal_interpretations": bus.with_interpretation(
                state.get("goal_interpretations"), "recover", str(data.get("goal_interpretation") or "")
            ),
        }


FACULTIES: dict[str, Callable[[], Any]] = {
    "node_guidance": GuidanceNode,
    "node_execute": ExecuteNode,
    "node_verify": VerifyNode,
    "node_recover": RecoverNode,
}


def node_contract(name: str) -> str:
    base = name.split(":", 1)[0]
    if base not in FACULTIES:
        raise RuntimeError(f"node '{name}' declareth no input contract")
    return str(getattr(FACULTIES[base], "contract", "") or "").strip()


def call_node(node_name: str, ctx: JsonDict) -> tuple[str, JsonDict]:
    base = node_name.split(":", 1)[0]
    if base not in FACULTIES:
        raise RuntimeError(f"unknown node '{node_name}'; known: {sorted(FACULTIES)}")
    ctx = {**ctx, "node": node_name, "node_base": base, "node_instance": None}
    signal, patch = bus.coerce_node_output(node_name, FACULTIES[base]().run(ctx))
    bus.validate_signal(ctx["wiring"], node_name, signal)
    return signal, dict(patch)


def _hwnds_referenced(code: str, action_index: dict[str, Any]) -> list[int]:
    import re

    hwnds: list[int] = []
    for sid in re.findall(r"""["']([a-zA-Z]\w*)["']""", str(code or "")):
        entry = action_index.get(sid)
        if isinstance(entry, dict):
            hwnd = entry.get("owner_hwnd") or entry.get("hwnd")
            if isinstance(hwnd, int) and hwnd and hwnd not in hwnds:
                hwnds.append(hwnd)
    return hwnds


def _host_facts() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "cwd": os.getcwd(),
        "repo_root": str(ROOT),
        "python": f"{sys.executable} ({platform.python_version()})",
        "shell_tools": sorted(
            t for t in ("powershell", "pwsh", "cmd", "git", "pip", "node", "npm", "curl") if shutil.which(t)
        ),
    }


def explore(ctx: dict[str, Any]) -> None:
    import core_desktop as desktop
    import core_exploration as exploration

    config = dict(ctx["wiring"]["exploration"])
    retry = ctx["state"].get("deed_retry") or {}
    only = retry.get("only_hwnds") if isinstance(retry, dict) else None
    if only:
        config["only_hwnds"] = list(only)
    obs = exploration.explore(desktop.get_desktop(config), config)
    ctx["state"].update({
        "observed_at": obs.get("observed_at"),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "action_index": obs.get("action_index", {}),
        "screen_elements": obs.get("screen_elements", []),
        "observation_artifact": obs.get("observation_artifact", {}),
        "host_facts": _host_facts(),
    })


def build_capability_runtime(ctx: dict[str, Any], *, read_only: bool = False) -> dict[str, Any]:
    import core_desktop as desktop

    d = desktop.get_desktop()
    state = ctx.get("state", {})
    index = state.get("action_index") or {}
    ns: dict[str, Any] = {
        "subprocess": subprocess,
        "os": os,
        "sys": sys,
        "json": json,
        "time": time,
        "pathlib": pathlib,
        "hashlib": hashlib,
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        "desktop_tree_text": str(state.get("desktop_tree_text", "")),
        "screen_elements": copy.deepcopy(state.get("screen_elements", [])),
        "environment": copy.deepcopy(bus.environment_brief(state)),
    }
    if read_only:
        # No re-exploration: environment is already injected before think; witness only reads.
        return ns

    w = ctx.get("wiring", {})

    def consult_model(prompt: str, profile: str | None = None) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w, profile=profile)
        return {"ok": True, "action": "consult_model", "profile": profile, "response": str(result["content"])}

    # Hand without re-exploration: LLM does not re-look; kernel explore() injects the environment.
    hand = types.SimpleNamespace(
        click=d.click,
        set_clipboard=d.set_clipboard,
        type_text=d.type_text,
        paste_clipboard=d.paste_clipboard,
        press_key=d.press_key,
        hotkey=d.hotkey,
        scroll=d.scroll,
        open_url=d.open_url,
    )
    ns.update({
        "desktop": hand,
        "action_index": index if isinstance(index, dict) else {},
        "consult_model": consult_model,
        "state": state,
        "wiring": w,
        "goal": ctx.get("goal", ""),
    })
    return ns
