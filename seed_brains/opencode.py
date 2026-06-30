from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess


def _resolve_executable(value):
    raw = os.path.expandvars(os.path.expanduser(str(value or "opencode")))
    p = pathlib.Path(raw)
    if p.exists():
        return str(p)
    found = shutil.which(raw)
    if found:
        return found
    raise RuntimeError(
        f"OpenCode executable missing: {raw}. Install OpenCode or intentionally change wiring.json model.transport; no fallback was attempted."
    )


def call(messages, cfg):
    exe = _resolve_executable(cfg.get("executable") or "opencode")
    args = list(cfg.get("args") or ["run", "--json"])
    prompt = json.dumps({"messages": messages}, ensure_ascii=False)
    cp = subprocess.run([exe, *args], input=prompt, capture_output=True, text=True, timeout=float(cfg.get("timeout") or 60))
    if cp.returncode != 0:
        raise RuntimeError(f"opencode exited {cp.returncode}: {cp.stderr.strip()[:2000]}")
    text = cp.stdout.strip()
    try:
        obj = json.loads(text)
        content = obj.get("content") or obj.get("message") or text
        reasoning = obj.get("reasoning") or ""
    except json.JSONDecodeError:
        content = text
        reasoning = ""
    return {"content": content, "reasoning": reasoning, "stdout": cp.stdout, "stderr": cp.stderr}
