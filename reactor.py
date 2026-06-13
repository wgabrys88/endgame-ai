"""Reactor — breeder core. Spawns personality-driven agents across LM hosts."""
from __future__ import annotations
import glob
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

import config
import log
from llm import discover_hosts

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 10
BUDGET = 999999
slots: dict[int, dict[str, Any]] = {}


def _host_label(url: str) -> str:
    h = urlparse(url).hostname
    return "local" if h in ("localhost", "127.0.0.1", "::1") else (h or url)


def _healthy_hosts() -> list[str]:
    return discover_hosts(list(config.LMS_CANDIDATE_HOSTS)) or list(config.LMS_CANDIDATE_HOSTS)


_cached_healthy: list[str] = []
_cached_healthy_at: float = 0.0


def pick_host() -> str | None:
    global _cached_healthy, _cached_healthy_at
    now = time.time()
    if not _cached_healthy or now - _cached_healthy_at > 60:
        _cached_healthy = _healthy_hosts()
        _cached_healthy_at = now
    healthy = _cached_healthy
    if not healthy:
        return None
    counts = {h: 0 for h in healthy}
    for s in slots.values():
        url = str(s.get("host_url", "")).rstrip("/")
        if url in counts:
            counts[url] += 1
    cap = config.LMS_MAX_SLOTS_PER_HOST
    for host in sorted(healthy, key=lambda h: counts.get(h, 0)):
        if cap <= 0 or counts.get(host, 0) < cap:
            return host
    return healthy[0]


def is_alive(slot_id: int) -> bool:
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    if not os.path.exists(ef):
        return False
    try:
        with open(ef, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 4096))
            tail = fh.read().decode("utf-8", errors="ignore")
        for line in reversed(tail.splitlines()):
            if line.strip():
                try:
                    if json.loads(line).get("phase") == "stop":
                        return False
                except (json.JSONDecodeError, ValueError):
                    pass
                break
        return True
    except OSError:
        return True


def spawn(slot_id: int, host_url: str) -> int:
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    try:
        os.remove(ef)
    except OSError:
        pass
    personality = config.ROSTER.get(slot_id, "")
    goal = ""
    if personality:
        pfile = os.path.join(BASE, "prompts", "personalities", f"{personality}.txt")
        if os.path.exists(pfile):
            goal = open(pfile, encoding="utf-8").read().strip()
    env = os.environ.copy()
    host_url = host_url.rstrip("/")
    env["ENDGAME_LMS_HOST"] = host_url
    env["ENDGAME_LMS_HOSTS"] = ",".join(config.LMS_CANDIDATE_HOSTS)
    env["ENDGAME_PERSONALITY"] = personality
    env["ENDGAME_SLOT"] = str(slot_id)
    backend = os.environ.get("ENDGAME_BACKEND", "lmstudio")
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", backend, "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env, creationflags=0x08000000)
    slots[slot_id] = {"pid": proc.pid, "host_url": host_url, "personality": personality}
    return proc.pid


if __name__ == "__main__":
    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()
    healthy = _healthy_hosts()
    print(f"REACTOR | {config.REACTOR_SLOTS} slots")
    print(f"  hosts: {', '.join(config.LMS_CANDIDATE_HOSTS)}")
    print(f"  healthy: {', '.join(healthy) or 'none (will retry)'}")
    for sid, p in config.ROSTER.items():
        print(f"  n{sid}: {p}")
    print()

    for sid in range(1, config.REACTOR_SLOTS + 1):
        host = pick_host()
        if not host:
            break
        pid = spawn(sid, host)
        print(f"  BOOT n{sid} [{_host_label(host)}] {config.ROSTER.get(sid, '')} PID={pid}")
        time.sleep(2)

    print(f"\nREACTOR CRITICAL. {len(slots)} rods loaded.\n")
    while True:
        time.sleep(CONTROL_INTERVAL)
        dead = [sid for sid in list(slots) if not is_alive(sid)]
        for sid in dead:
            del slots[sid]
        for sid in dead:
            host = pick_host()
            if host:
                spawn(sid, host)
        k_fissions = 0
        for f in glob.glob(os.path.join(BASE, "events-child-*.jsonl")):
            try:
                k_fissions += sum(1 for l in open(f) if '"fission"' in l)
            except OSError:
                pass
        hosts_map = {}
        for s in slots.values():
            lbl = _host_label(str(s.get("host_url", "")))
            hosts_map[lbl] = hosts_map.get(lbl, 0) + 1
        ts = time.strftime("%H:%M:%S")
        print(f"{ts} k={k_fissions / max(len(slots), 1):.2f} hosts={' '.join(f'{k}={v}' for k, v in hosts_map.items())} F={k_fissions}" + (f" reaped={dead}" if dead else ""))
