"""Lessons decay plugin — ages old lessons so fresh knowledge dominates."""
import time


DECAY_INTERVAL = 300  # seconds between decay runs
DECAY_AMOUNT = 1      # score points lost per decay
MIN_SCORE = 1         # floor


def run(board):
    state = board.get("_plugin_lessons_decay", {})
    last = state.get("last_decay", 0)
    now = time.time()
    if now - last < DECAY_INTERVAL:
        return None
    import lessons
    entries = lessons._load()
    if not entries:
        return {"writes": {"_plugin_lessons_decay": {"last_decay": now}}}
    decayed = 0
    for e in entries:
        age = now - e.get("ts", now)
        if age > DECAY_INTERVAL and e.get("score", 5) > MIN_SCORE:
            e["score"] = max(MIN_SCORE, e["score"] - DECAY_AMOUNT)
            decayed += 1
    if decayed:
        lessons._save(entries)
    return {
        "writes": {"_plugin_lessons_decay": {"last_decay": now, "decayed": decayed}},
        "phase": "plugin.lessons_decay",
        "data": {"decayed": decayed, "total": len(entries)},
    }
