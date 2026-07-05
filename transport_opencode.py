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
    model = cfg.get("model") or "opencode-go/deepseek-v4-flash"
    
    prompt_parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            prompt_parts.append(f"[SYSTEM]\n{content}")
        elif role == "user":
            prompt_parts.append(f"[USER]\n{content}")
        elif role == "assistant":
            prompt_parts.append(f"[ASSISTANT]\n{content}")
        else:
            prompt_parts.append(f"[{role.upper()}]\n{content}")
    prompt = "\n\n".join(prompt_parts)

    args = ["run", "-m", model, "--format", "json"]
    extra_args = cfg.get("extra_args")
    if extra_args:
        args.extend(extra_args)

    env = os.environ.copy()
    env["OPENCODE_SERVER_PASSWORD"] = ""
    env["OPENCODE_SERVER_USERNAME"] = ""
    
    cp = subprocess.run(
        [exe, *args, prompt],
        capture_output=True,
        text=True,
        timeout=float(cfg.get("timeout") or 120),
        env=env
    )
    if cp.returncode != 0:
        raise RuntimeError(f"opencode exited {cp.returncode}: {cp.stderr.strip()[:2000]}")

    text = cp.stdout.strip()
    content = ""
    reasoning = ""
    try:
        for line in text.splitlines():
            obj = json.loads(line)
            if obj.get("type") == "text":
                content = obj.get("part", {}).get("text", content)
            elif obj.get("type") == "step_finish":
                pass
    except json.JSONDecodeError:
        content = text
        reasoning = ""
    
    if not content:
        content = text
    
    return {"content": content, "reasoning": reasoning, "stdout": cp.stdout, "stderr": cp.stderr}
