"""Copy the full endgame-ai codebase snapshot to the OS clipboard."""
ok, info = copy_codebase_to_clipboard()
patch = {"codebase_snapshot": info, "last_error": "" if ok else info.get("message", "copy failed")}
signals = ["copied" if ok else "copy_failed"]
