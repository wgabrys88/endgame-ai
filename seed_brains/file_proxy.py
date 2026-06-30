"""File / human handoff brain node: request.json -> response.json."""
req_path = _root_path(cfg.get("request_path"), "comms/request.json")
resp_path = _root_path(cfg.get("response_path"), "comms/response.json")
archive = _root_path(cfg.get("archive_dir"), "comms/archive")
for p in (req_path.parent, archive):
    p.mkdir(parents=True, exist_ok=True)
rid = f"egai-{int(time.time()*1000)}-{os.getpid()}-{threading.get_ident() % 100000}"
request_obj = {
    "id": rid,
    "status": "pending",
    "created_at": time.time(),
    "transport": "file_proxy",
    "model": cfg.get("model"),
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    "system": system,
    "user": user,
}
_atomic_write_json(req_path, request_obj)
brain._log_raw(seq, "request", "file_proxy", {"request_path": str(req_path), "body": request_obj},
               rod_feedback="ROD_REASONING_CONTENT" in user)
started = time.time()
poll = max(0.05, int(cfg.get("poll_interval_ms", 1000)) / 1000.0)
deadline = started + brain._timeout(cfg)
while time.time() < deadline:
    if resp_path.exists():
        try:
            resp = json.loads(resp_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            time.sleep(poll)
            continue
        if resp.get("id") in (None, "", rid):
            content = _proxy_content(resp)
            reasoning = str(resp.get("reasoning") or resp.get("reasoning_content") or "") if isinstance(resp, dict) else ""
            brain._log_raw(seq, "response", "file_proxy", {
                "response_path": str(resp_path),
                "body": resp,
                "id": rid,
            }, elapsed_s=round(time.time() - started, 3))
            try:
                shutil.move(str(resp_path), str(archive / f"response.{rid}.json"))
            except OSError:
                pass
            break
    time.sleep(poll)
else:
    raise TimeoutError(f"file_proxy brain timed out waiting for {resp_path}")
