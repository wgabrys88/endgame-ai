from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import SCREEN_STAGNATION_LOOKBACK, SCREEN_HASH_HISTORY_LIMIT


class ObserverAgent:
    name: str = "observer"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        from observer import observe
        try:
            obs = observe()
        except Exception as e:
            return AgentResult(
                writes={"screen": f"OBSERVE_FAILED: {e}", "consecutive_failures": board.consecutive_failures + 1},
                event_phase="observe.fail",
                event_data={"error": str(e)[:200]},
            )

        writes: dict[str, Any] = {}

        if obs.semantic_hash == board.screen_hash:
            new_stag = board.screen_stagnation + 1
            writes["screen_stagnation"] = new_stag
            return AgentResult(
                writes=writes,
                event_phase="observe",
                event_data={"hash": obs.semantic_hash, "stagnant": True},
            )

        new_hashes = list(board.recent_hashes)
        new_hashes.append(obs.semantic_hash)
        if len(new_hashes) > SCREEN_HASH_HISTORY_LIMIT:
            new_hashes = new_hashes[-SCREEN_HASH_HISTORY_LIMIT:]

        if obs.semantic_hash in board.recent_hashes[-SCREEN_STAGNATION_LOOKBACK:]:
            new_screen_stag = board.screen_stagnation + 1
        else:
            new_screen_stag = 0

        writes["screen"] = obs.context_text
        writes["screen_hash"] = obs.semantic_hash
        writes["screen_elements"] = obs.book
        writes["focused_window"] = obs.focused_title
        writes["desktop_summary"] = obs.desktop_summary
        writes["recent_hashes"] = new_hashes
        writes["screen_stagnation"] = new_screen_stag

        return AgentResult(
            writes=writes,
            event_phase="observe",
            event_data={"hash": obs.semantic_hash, "focused": obs.focused_title, "chars": len(obs.context_text)},
        )
