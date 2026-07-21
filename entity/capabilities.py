"""The hands. This file is the ONE native dependency the Entity needs on a target machine.

It does not contain the hand code. It DOWNLOADS the body files from GitHub raw (once, then
cached beside this file) and imports them. So the organism logic ships as `entity.md`; the
Windows hand ships as a pointer to raw.githubusercontent, fetched on first use.

build(kind, sections) -> namespace injected into the engine's exec:
    actor  namespace: desktop (the hand) + action_index + repo helpers
    witness namespace: read-only stdlib only (no desktop)
environment(sections): refresh the `environment` section with a fresh window-first screen scan.
"""
from __future__ import annotations
import importlib.util
import pathlib
import sys
import urllib.request

# Pin the body to a repo + branch. Change these two lines to point the Entity at a different body.
_REPO = "wgabrys88/endgame-ai"
_BRANCH = "running-repair"
_BODY_FILES = ["core_desktop.py", "core_observation.py"]

_HERE = pathlib.Path(__file__).parent
_CACHE = _HERE / ".body_cache"
_loaded: dict[str, object] = {}


def _raw_url(name: str) -> str:
    return f"https://raw.githubusercontent.com/{_REPO}/{_BRANCH}/{name}"


def _ensure_body() -> None:
    """Download each body file once; reuse the local copy if already present."""
    _CACHE.mkdir(exist_ok=True)
    if str(_CACHE) not in sys.path:
        sys.path.insert(0, str(_CACHE))
    for name in _BODY_FILES:
        dest = _CACHE / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        sys.stderr.write(f"capabilities: downloading {name} from {_BRANCH}\n")
        with urllib.request.urlopen(_raw_url(name), timeout=60) as r:
            dest.write_bytes(r.read())


def _import(name: str):
    if name in _loaded:
        return _loaded[name]
    _ensure_body()
    mod_name = name[:-3]
    spec = importlib.util.spec_from_file_location(mod_name, _CACHE / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore
    _loaded[name] = mod
    return mod


def _desktop():
    return _import("core_desktop.py").get_desktop()


def build(kind: str, sections: dict) -> dict:
    if kind == "witness":
        return {}  # read-only: stdlib only, no hand
    d = _desktop()
    import types
    hand = types.SimpleNamespace(
        click=d.click, type_text=d.type_text, paste_clipboard=d.paste_clipboard,
        set_clipboard=d.set_clipboard, press_key=d.press_key, hotkey=d.hotkey,
        scroll=d.scroll, open_url=d.open_url,
    )
    return {"desktop": hand, "action_index": _ACTION_INDEX, "repo_root": str(_HERE)}


_ACTION_INDEX: dict = {}


def environment(sections: dict) -> None:
    """Refresh the `environment` section with a fresh screen scan + host facts."""
    global _ACTION_INDEX
    try:
        d = _desktop()
        obs = d.observe({"step_px": 64, "max_subtree_nodes_per_point": 100, "max_environment_chars": 1200})
    except Exception as e:  # no display / not Windows: leave a note, do not crash the turn
        sections["environment"] = f"(environment scan unavailable: {e})"
        return
    _ACTION_INDEX = obs.get("action_index", {}) or {}
    tree = str(obs.get("desktop_tree_text") or "").strip()
    sections["environment"] = tree or "(no interactable elements observed)"
