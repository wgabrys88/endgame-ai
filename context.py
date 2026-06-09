from __future__ import annotations
from typing import Any

from config import CONTEXT_POLICY, LESSONS_PATH
import log


def render_context(board: Any, role: str, instruction: str = "") -> str:
    fields = CONTEXT_POLICY.get(role, [])
    parts: list[str] = []
    for f in fields:
        text = _render(board, f, instruction)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _render(b: Any, field: str, instruction: str) -> str:
    match field:
        case "goal":
            return f"GOAL: {b.goal}"
        case "desktop":
            return b.desktop_summary if b.desktop_summary else ""
        case "instruction":
            if not instruction:
                return ""
            parts_i = instruction.split(None, 1)
            verb_i = parts_i[0].lower() if parts_i else ""
            from actions import VERBS as _VERBS
            if verb_i in _VERBS:
                remainder = parts_i[1] if len(parts_i) > 1 else ""
                return f"INSTRUCTION: {instruction}\nDETECTED VERB: {verb_i}\nARGUMENT: {remainder}"
            return f"INSTRUCTION: {instruction}"
        case "screen":
            return f"SCREEN:\n{b.screen}" if b.screen else ""
        case "plan":
            if not b.plan_steps:
                return ""
            lines = ["PLAN:"]
            for i, step in enumerate(b.plan_steps):
                is_last = i == len(b.plan_steps) - 1
                connector = "└── " if is_last else "├── "
                if i == b.plan_index:
                    marker = ">>> "
                elif i < b.plan_index:
                    marker = "✓ "
                else:
                    marker = ""
                lines.append(f"  {connector}{marker}{step}")
            return "\n".join(lines)
        case "history":
            recent = b.history[-8:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "✓" if h["ok"] else "✗"
                lines.append(f"  {ok} {h['verb']}: {h['obs']}")
            return "\n".join(lines)
        case "budget":
            remaining = log.budget() - log.count()
            if remaining > log.budget() // 2:
                return ""
            return f"BUDGET: {remaining} events remaining. Be decisive."
        case "diverge":
            if not b.notes:
                return ""
            return "\n".join(b.notes)
        case "math":
            jac = ""
            if b.jacobian:
                top = sorted(b.jacobian.items(), key=lambda x: x[1], reverse=True)[:5]
                jac = " jacobian=[" + ",".join(f"{k}:{v:.2f}" for k, v in top) + "]"
            return (f"MATH: stagnation={b.stagnation_score:.2f} pid={b.pid_output:.2f} "
                    f"energy={b.attractor_energy:.2f} lorenz_x={b.lorenz_x:.2f}{jac}")
        case "failures":
            if b.consecutive_failures == 0 and b.verify_denied_count == 0:
                return ""
            parts_f: list[str] = []
            if b.verify_denied_count > 0:
                parts_f.append(f"Verifier DENIED {b.verify_denied_count} times. You MUST choose mode=direct and take actions.")
            if b.consecutive_failures > 0:
                parts_f.append(f"Consecutive failures: {b.consecutive_failures}. Try a different approach.")
            return "\n".join(parts_f)
        case "roles":
            if not b.last_outputs:
                return ""
            lines_r = ["OTHER AGENTS:"]
            for role_name, output in b.last_outputs.items():
                lines_r.append(f"  {role_name}: {output[:120]}")
            return "\n".join(lines_r)
        case "lessons":
            if not LESSONS_PATH.exists():
                return ""
            text_l = LESSONS_PATH.read_text(encoding="utf-8").strip()
            if not text_l:
                return ""
            lines_l = text_l.splitlines()[-10:]
            return "LESSONS:\n" + "\n".join(f"  - {l}" for l in lines_l)
        case "evidence":
            import re as _re
            from config import BASE_DIR as _BASE
            filenames = _re.findall(r'[\w\-./\\]+\.\w{1,5}', b.goal)
            if not filenames:
                return ""
            lines_e: list[str] = ["EVIDENCE:"]
            for fn in filenames:
                p = _BASE / fn
                if p.exists():
                    size = p.stat().st_size
                    lines_e.append(f"  {fn}: EXISTS ({size} bytes)")
                else:
                    lines_e.append(f"  {fn}: NOT FOUND")
            return "\n".join(lines_e)
        case _:
            return ""
