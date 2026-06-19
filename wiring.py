"""Load endgame-ai topology from prompts/wiring.txt — the sole control-plane config."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def _coerce(value: str) -> Any:
    v = value.strip()
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low.isdigit():
        return int(low)
    try:
        if "." in v:
            return float(v)
    except ValueError:
        pass
    return v


def _split_list(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def load_wiring(prompts_dir: Path) -> dict[str, Any]:
    path = prompts_dir / "wiring.txt"
    if not path.exists():
        raise FileNotFoundError(f"Required config missing: {path}")

    limits: dict[str, Any] = {}
    slots: dict[str, dict[str, Any]] = {}
    circuits: dict[str, dict[str, Any]] = {}
    transitions: dict[str, str] = {}
    verbs: dict[str, dict[str, str]] = {}
    comms: dict[str, Any] = {}
    global_mutator: dict[str, Any] = {}
    guards: dict[str, dict[str, Any]] = {}
    prompt_swaps: dict[str, dict[int, dict[str, Any]]] = {}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid wiring line (expected key=value): {line}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        parts = key.split(".")

        if parts[0] == "limits" and len(parts) == 2:
            limits[parts[1]] = _coerce(value)
            continue

        if parts[0] == "slots" and len(parts) == 3:
            slot = slots.setdefault(parts[1], {})
            slot[parts[2]] = _coerce(value) if parts[2] == "can_desktop" else value
            continue

        if parts[0] == "circuits" and len(parts) >= 3:
            circuit = parts[1]
            circuits.setdefault(circuit, {})
            if parts[2] == "prompt":
                circuits[circuit]["prompt"] = value
            elif parts[2] == "inject":
                circuits[circuit]["inject"] = _split_list(value)
            elif parts[2] == "prompt_swap" and len(parts) == 5:
                idx = int(parts[3])
                field = parts[4]
                bucket = prompt_swaps.setdefault(circuit, {}).setdefault(idx, {})
                if field == "when":
                    bucket.setdefault("when", []).append(value)
                elif field == "prompt":
                    bucket["prompt"] = value
            continue

        if parts[0] == "transitions" and len(parts) == 2:
            transitions[parts[1]] = value
            continue

        if parts[0] == "verbs" and len(parts) == 3:
            verbs.setdefault(parts[1], {})[parts[2]] = value
            continue

        if parts[0] == "comms" and len(parts) == 2:
            comms[parts[1]] = value
            continue

        if parts[0] == "global_mutator" and len(parts) == 2:
            global_mutator[parts[1]] = value
            continue

        if parts[0] == "guards" and len(parts) == 3:
            section = guards.setdefault(parts[1], {})
            key = parts[2]
            if key.endswith("_keywords") or key.endswith("_outcomes"):
                section[key] = _split_list(value)
            else:
                section[key] = _coerce(value)
            continue

        raise ValueError(f"Unrecognized wiring key: {key}")

    for circuit, swaps in prompt_swaps.items():
        ordered = [swaps[i] for i in sorted(swaps)]
        circuits[circuit]["prompt_swap"] = ordered

    required = ("limits", "slots", "circuits", "transitions", "verbs", "comms")
    result = {"limits": limits, "slots": slots, "circuits": circuits,
              "transitions": transitions, "verbs": verbs, "comms": comms,
              "global_mutator": global_mutator, "guards": guards}
    for section in required:
        if not result[section]:
            raise ValueError(f"wiring.txt missing required section: {section}")
    if "prompt" not in comms:
        raise ValueError("wiring.txt comms.prompt is required")
    if "fallback_slot" not in comms:
        raise ValueError("wiring.txt comms.fallback_slot is required")
    if "default" not in transitions:
        raise ValueError("wiring.txt transitions.default is required")
    if "prompt" not in global_mutator:
        raise ValueError("wiring.txt global_mutator.prompt is required")
    for name, cfg in circuits.items():
        if "prompt" not in cfg:
            raise ValueError(f"wiring.txt circuit '{name}' missing prompt")
        if "inject" not in cfg:
            raise ValueError(f"wiring.txt circuit '{name}' missing inject")
    for name, cfg in slots.items():
        if "can_desktop" not in cfg:
            raise ValueError(f"wiring.txt slot '{name}' missing can_desktop")
        if "mode" not in cfg:
            raise ValueError(f"wiring.txt slot '{name}' missing mode")
    if "unified" not in guards:
        raise ValueError("wiring.txt guards.unified section is required")
    valid_phases = set(circuits) | {"idle"}
    for event, target in transitions.items():
        if event == "default":
            continue
        if target not in valid_phases:
            raise ValueError(f"transition {event} -> {target} invalid (unknown phase)")
    if transitions["default"] not in circuits:
        raise ValueError(f"transitions.default must name a circuit, got {transitions['default']}")
    return result