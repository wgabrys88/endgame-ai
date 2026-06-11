"""Web sentinel plugin — fetches current UTC time as proof of connectivity."""
import json
import urllib.request
from datetime import datetime


def run(board):
    """Called each reactor cycle. Returns writes dict or None."""
    # Only fetch every ~30 cycles to avoid spam (cycle is ~0.15s)
    import time
    state = board.get("_plugin_web_sentinel", {})
    last = state.get("last_fetch", 0)
    if time.time() - last < 30:
        return None
    try:
        req = urllib.request.Request(
            "https://timeapi.io/api/Time/current/zone?timeZone=UTC",
            headers={"User-Agent": "endgame-ai-sentinel/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode()[:200]
        return {
            "writes": {"_plugin_web_sentinel": {"last_fetch": time.time(), "data": data}},
            "phase": "plugin.web_sentinel",
            "data": {"ok": True, "len": len(data)},
        }
    except Exception as e:
        return {
            "writes": {"_plugin_web_sentinel": {"last_fetch": time.time(), "error": str(e)}},
            "phase": "plugin.web_sentinel",
            "data": {"ok": False, "error": str(e)[:100]},
        }
