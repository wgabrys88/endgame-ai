from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess


def _exe(value):
    raw = os.path.expandvars(os.path.expanduser(str(value or "grok")))
    p = pathlib.Path(raw)
    if p.exists():
        return str(p)
    found = shutil.which(raw)
    if found:
        return found
    raise RuntimeError(f"grok_build executable missing: {raw}; no fallback was attempted")


def call(messages, cfg):
    exe = _exe(cfg.get("executable") or "grok")
    args = list(cfg.get("args") or ["-p"])
    prompt = json.dumps({"messages": messages}, ensure_ascii=False)
    cp = subprocess.run([exe, *args, prompt], capture_output=True, text=True, timeout=float(cfg.get("timeout") or 120))
    if cp.returncode != 0:
        raise RuntimeError(f"grok_build exited {cp.returncode}: {cp.stderr.strip()[:2000]}")
    return {"content": cp.stdout.strip(), "reasoning": "", "stdout": cp.stdout, "stderr": cp.stderr}
