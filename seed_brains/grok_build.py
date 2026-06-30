"""Grok Build CLI headless brain node."""
exe = _resolve_executable(str(cfg.get("exe") or "grok"), "grok_build")
model = cfg.get("model", "grok-build")
prompt = system + "\n\n" + user
cmd = [exe, "-p", prompt]
if model:
    cmd += ["-m", str(model)]
if cfg.get("output_format"):
    cmd += ["--output-format", str(cfg["output_format"])]
if cfg.get("cwd"):
    cmd += ["--cwd", str(_root_path(cfg.get("cwd"), "."))]
if cfg.get("always_approve"):
    cmd += ["--always-approve"]
if cfg.get("no_auto_update"):
    cmd += ["--no-auto-update"]
if cfg.get("no_alt_screen"):
    cmd += ["--no-alt-screen"]
cmd += [str(x) for x in (cfg.get("extra_args") or [])]
content, reasoning = _run_cli_transport(brain, "grok_build", cmd, str(model), cfg, seq, prompt_values={prompt})
