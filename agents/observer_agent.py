from __future__ import annotations
from typing import Any

from config import SCREEN_STAGNATION_LOOKBACK, SCREEN_HASH_HISTORY_LIMIT


class ObserverAgent:
    name: str = "observer"
    reads: list[str] = ["screen_hash", "screen_stagnation", "recent_hashes"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from observer import observe
        try:
            obs = observe()
        except Exception as e:
            return {
                "writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1},
                "next": "stagnation",
                "phase": "observe",
                "data": {"error": str(e)[:200]},
            }

        old_hash = str(ctx.get("screen_hash", ""))
        old_stag = int(ctx.get("screen_stagnation", 0))
        recent: list[str] = ctx.get("recent_hashes", [])

        if obs.semantic_hash == old_hash:
            return {
                "writes": {"screen_stagnation": old_stag + 1},
                "next": "planner",
                "phase": "observe",
                "data": {"hash": obs.semantic_hash, "stagnant": True},
            }

        new_hashes = list(recent)
        new_hashes.append(obs.semantic_hash)
        if len(new_hashes) > SCREEN_HASH_HISTORY_LIMIT:
            new_hashes = new_hashes[-SCREEN_HASH_HISTORY_LIMIT:]

        if obs.semantic_hash in recent[-SCREEN_STAGNATION_LOOKBACK:]:
            new_screen_stag = old_stag + 1
        else:
            new_screen_stag = 0

        return {
            "writes": {
                "screen": obs.context_text,
                "screen_hash": obs.semantic_hash,
                "screen_elements": obs.book,
                "focused_window": obs.focused_title,
                "desktop_summary": obs.desktop_summary,
                "recent_hashes": new_hashes,
                "screen_stagnation": new_screen_stag,
            },
            "next": "planner",
            "phase": "observe",
            "data": {"hash": obs.semantic_hash, "focused": obs.focused_title, "chars": len(obs.context_text)},
        }
