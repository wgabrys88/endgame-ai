import json, time
from pathlib import Path

BASE = Path(__file__).parent
LESSONS = BASE / "lessons.json"

def _load():
    if LESSONS.exists():
        d = json.loads(LESSONS.read_text())
        return d if isinstance(d, list) else d.get("lessons", [])
    return []

def _save(items):
    LESSONS.write_text(json.dumps(items[-200:], indent=1))

def reflect(action, result, score=5, note=""):
    items = _load()
    items.append({"action": action[:200], "result": result[:200], "score": score, "note": note, "ts": time.time()})
    _save(items)
    return score >= 7

def get_relevant(keyword="", n=5):
    items = _load()
    if keyword:
        items = [i for i in items if keyword.lower() in json.dumps(i).lower()]
    return items[-n:]

if __name__ == "__main__":
    reflect("test", "ok", 8)
    print(f"reflect OK, {len(_load())} lessons")
