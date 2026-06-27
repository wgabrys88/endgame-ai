"""Observe desktop with wiring-configured retry."""
if state.get("no_desktop"):
    screen = state.get("screen") or wiring.get("context", {}).get("screen_disabled", "(desktop observation disabled)")
    meta = {}
else:
    obs_cfg = wiring.get("observe", {}) or {}
    min_elements = int(obs_cfg.get("min_elements", 0) or 0)
    retries = int(obs_cfg.get("wait_retries", 0) or 0)
    wait_ms = int(obs_cfg.get("wait_ms", 500) or 500)
    screen = observe_screen()
    meta = last_observation_snapshot()
    def action_count(text, snapshot):
        if isinstance(snapshot, dict) and isinstance(snapshot.get("elements"), list):
            return len(snapshot["elements"])
        return sum(1 for line in (text or "").splitlines() if re.match(r"\s*\[?\d+\]?", line))
    for _ in range(retries):
        if not min_elements or action_count(screen, meta) >= min_elements:
            break
        time.sleep(wait_ms / 1000.0)
        screen = observe_screen()
        meta = last_observation_snapshot()
patch = {"screen": screen}
if meta:
    patch["screen_meta"] = meta
signals = ["screen_ready"]
