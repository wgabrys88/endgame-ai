"""OpenCode CLI stateless brain node."""
exe = _resolve_executable(str(cfg.get("exe") or "opencode"), "opencode")
model = cfg.get("model")
prompt = system + "\n\n" + user
cmd = [exe, "run"]
if cfg.get("command"):
    cmd += ["--command", str(cfg["command"])]
if model:
    cmd += ["--model", str(model)]
if cfg.get("agent"):
    cmd += ["--agent", str(cfg["agent"])]
if cfg.get("format"):
    cmd += ["--format", str(cfg["format"])]
if cfg.get("title"):
    cmd += ["--title", str(cfg["title"])]
if cfg.get("attach"):
    cmd += ["--attach", str(cfg["attach"])]
if cfg.get("username"):
    cmd += ["--username", str(cfg["username"])]
if cfg.get("password"):
    cmd += ["--password", str(cfg["password"])]
if cfg.get("dir"):
    cmd += ["--dir", str(cfg["dir"])]
for f in cfg.get("files", []) or []:
    cmd += ["--file", str(f)]

prompt_values = {prompt}
prompt_mode = str(cfg.get("prompt_mode", "file")).lower()
temp_path = None
try:
    if prompt_mode == "argv":
        cmd.append(prompt)
    elif prompt_mode == "file":
        temp_path = _make_prompt_file("opencode", prompt)
        cmd.append(str(cfg.get("file_message") or "Follow the attached prompt."))
        cmd += ["--file", str(temp_path)]
    else:
        raise ValueError(f"opencode prompt_mode must be 'file' or 'argv', got {prompt_mode!r}")
    cmd += [str(x) for x in (cfg.get("extra_args") or [])]
    content, reasoning = _run_cli_transport(brain, "opencode", cmd, str(model or ""), cfg, seq, prompt_values=prompt_values)
finally:
    if temp_path and not cfg.get("keep_prompt_files", False):
        try:
            temp_path.unlink()
        except OSError:
            pass
