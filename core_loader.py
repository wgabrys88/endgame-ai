"""Load wiring-named plugins from files; instance suffixes reuse one module."""
from __future__ import annotations

import importlib.util
from typing import Any, NamedTuple

import core_wiring as wiring

JsonDict = dict[str, Any]


class PluginKind(NamedTuple):
    paths_key: str
    module_prefix: str
    export: str


KINDS: dict[str, PluginKind] = {
    "node": PluginKind(paths_key="nodes", module_prefix="endgame_node_", export="run"),
    "transport": PluginKind(paths_key="brains", module_prefix="endgame_brain_transport_", export="call"),
}


def split_instance(name: str) -> tuple[str, str | None]:
    """Split "base:instance" -> ("base", "instance"). No colon -> (name, None)."""
    if ":" in name:
        base, instance = name.split(":", 1)
        if not base or not instance:
            raise RuntimeError(f"malformed plugin name '{name}': expected 'base:instance'")
        return base, instance
    return name, None


def load(kind: str, name: str, w: JsonDict):
    """Resolve plugin `name` of `kind` to a module exporting the kind's contract.

    Returns the loaded module. Raises hard on missing dir key, missing file,
    unloadable spec, or missing exported symbol. No fallback.
    """
    spec_kind = KINDS.get(kind)
    if spec_kind is None:
        raise RuntimeError(f"unknown plugin kind '{kind}'; known: {', '.join(sorted(KINDS))}")
    base, _instance = split_instance(name)
    plugin_dir = wiring.root_path(w["paths"][spec_kind.paths_key])
    path = plugin_dir / f"{base}.py"
    if not path.exists():
        raise RuntimeError(f"{kind} plugin '{base}' has no module at {path}; no fallback was attempted")
    spec = importlib.util.spec_from_file_location(f"{spec_kind.module_prefix}{base}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {kind} plugin module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, spec_kind.export):
        raise RuntimeError(f"{kind} plugin '{base}' does not export {spec_kind.export}(...)")
    return mod
