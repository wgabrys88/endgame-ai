from dataclasses import dataclass
import time
from typing import Any

JsonDict = dict[str, Any]
_INTERP_ORDER = ["execute", "verify", "recover"]
_HOST_CORE = ("platform", "machine", "hostname", "user", "cwd", "repo_root", "python", "shell_tools")
_HOST_DEFER = ("installed_apps",)


def deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def drop_nulls(obj: Any) -> Any:
    if isinstance(obj, dict):
        pruned: JsonDict = {}
        for key, value in obj.items():
            if value is None:
                continue
            cleaned = drop_nulls(value)
            if isinstance(cleaned, dict) and not cleaned:
                continue
            pruned[key] = cleaned
        return pruned
    if isinstance(obj, list):
        return [drop_nulls(item) for item in obj]
    return obj


class BusContractError(RuntimeError):
    pass


class TopologyContractError(BusContractError):
    pass


class NodeRecordContractError(BusContractError):
    pass


@dataclass(frozen=True)
class Record:
    record_type: str
    data: JsonDict
    reasoning: str = ""

    def to_json(self) -> JsonDict:
        return {"record_type": self.record_type, "data": self.data, "reasoning": self.reasoning}

    @classmethod
    def from_json(cls, obj: JsonDict) -> "Record":
        return cls(
            record_type=obj.get("record_type", ""),
            data=obj.get("data", {}),
            reasoning=obj.get("reasoning", ""),
        )


def emit(signal: str, patch: JsonDict | None = None) -> tuple[str, JsonDict]:
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError("bus signal must be a non-empty string")
    if patch is not None and not isinstance(patch, dict):
        raise TypeError("bus patch must be a dict")
    return signal.strip(), dict(patch or {})


def render_interpretation_table(goal: str, interps: JsonDict | None, templates: JsonDict) -> str:
    interps = interps or {}
    lines = [templates["living_word_header"]]
    for faculty in _INTERP_ORDER:
        sentence = str(interps.get(faculty) or "").strip()
        lines.append(
            f"[{faculty}] {sentence}" if sentence else templates["living_word_empty_row"].format(faculty=faculty)
        )
    lines.append(templates["living_word_goal_row"].format(goal=goal))
    return "\n".join(lines)


def render_proven_ledger(ledger: list | None, templates: JsonDict) -> str:
    entries = [str(e).strip() for e in (ledger or []) if str(e).strip()]
    if not entries:
        return templates["proven_ledger_empty"]
    return templates["proven_ledger_header"] + "\n" + "\n".join(f"  - {e}" for e in entries)


def with_interpretation(interps: JsonDict | None, faculty: str, sentence: str) -> JsonDict:
    merged = dict(interps or {})
    merged[faculty] = str(sentence or "").strip()
    return merged


def _host_line(key: str, value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"[{key}] {value}"


def _parse_tree(tree: str) -> list[JsonDict]:
    windows: list[JsonDict] = []
    for line in tree.splitlines():
        if not line.strip():
            continue
        if line[0] == "W" and len(line) > 1 and line[1].isdigit():
            windows.append({"title": line, "elements": []})
        elif windows:
            windows[-1]["elements"].append(line)
    return windows


def _take_lines(lines: list[str], room: int) -> tuple[list[str], int]:
    taken: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > room:
            break
        taken.append(line)
        used += cost
    return taken, used


def render_environment(environment: JsonDict | None, templates: JsonDict, max_chars: int | None = None) -> str:
    environment = environment or {}
    tree = str(environment.get("desktop_tree_text") or "").strip()
    host = environment.get("host") or {}

    def unlimited() -> str:
        blocks = []
        if tree:
            blocks.append(templates["environment_screen_header"] + "\n" + tree)
        if host:
            lines = [templates["standing_host_header"]]
            lines.extend(_host_line(k, v) for k, v in host.items())
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    if max_chars is None:
        return unlimited()

    budget = int(max_chars)
    if budget <= 0:
        raise ValueError("max_environment_chars must be positive")

    header = str(templates["environment_screen_header"])
    host_header = str(templates["standing_host_header"])
    windows = _parse_tree(tree) if tree else []
    core = [_host_line(k, host[k]) for k in _HOST_CORE if k in host and host[k] not in ("", None, [])]
    for k, v in host.items():
        if k not in _HOST_CORE and k not in _HOST_DEFER and v not in ("", None, []):
            core.append(_host_line(k, v))
    deferred = [_host_line(k, host[k]) for k in _HOST_DEFER if k in host and host[k] not in ("", None, [])]
    host_block = "\n".join([host_header, *core]) if core else ""
    marker_reserve = min(180, max(40, budget // 20))
    screen_budget = max(0, budget - (len(host_block) + 2 if host_block else 0) - marker_reserve)

    used = 0
    omitted_w: list[str] = []
    omitted_e = 0
    kept_e = 0
    titles: list[tuple[int, str]] = []
    picked: dict[int, list[str]] = {}

    screen: list[str] = []
    if (tree or windows) and len(header) + 1 <= screen_budget:
        screen.append(header)
        used = len(header) + 1
    elif tree or windows:
        omitted_w = [str(w["title"]).split(" ", 1)[0] for w in windows]
        omitted_e = sum(len(w["elements"]) for w in windows)
        windows = []

    for idx, win in enumerate(windows):
        title = str(win["title"])
        cost = len(title) + 1
        if used + cost > screen_budget:
            omitted_w.append(title.split(" ", 1)[0])
            omitted_e += len(win["elements"])
            continue
        titles.append((idx, title))
        picked[idx] = []
        used += cost

    with_e = [i for i, _ in titles if windows[i]["elements"]]
    cursors = {i: 0 for i in with_e}
    if with_e and used < screen_budget:
        share = max((screen_budget - used) // len(with_e), 0)
        for i in with_e:
            room = min(share, screen_budget - used)
            taken, spent = _take_lines(windows[i]["elements"], room)
            picked[i].extend(taken)
            cursors[i] = len(taken)
            used += spent
            kept_e += len(taken)
        progressed = True
        while progressed and used < screen_budget:
            progressed = False
            for i in with_e:
                start = cursors[i]
                elems = windows[i]["elements"]
                if start >= len(elems):
                    continue
                cost = len(elems[start]) + 1
                if used + cost > screen_budget:
                    continue
                picked[i].append(elems[start])
                cursors[i] = start + 1
                used += cost
                kept_e += 1
                progressed = True
        for i in with_e:
            omitted_e += len(windows[i]["elements"]) - cursors[i]

    for i, title in titles:
        screen.append(title)
        screen.extend(picked.get(i, []))
    text = "\n".join(screen) if screen else ""

    def fits(base: str, extra: str) -> bool:
        return len(extra) <= budget if not base else len(base) + 1 + len(extra) <= budget

    host_kept = False
    if host_block and fits(text, host_block):
        text = f"{text}\n\n{host_block}" if text else host_block
        host_kept = True
    elif host_block:
        kept = [host_header]
        for line in core:
            cand = "\n".join(kept + [line])
            if fits(text, cand):
                kept.append(line)
            else:
                break
        if len(kept) > 1:
            hb = "\n".join(kept)
            text = f"{text}\n\n{hb}" if text else hb
            host_kept = True

    apps_omitted = bool(deferred)
    if deferred and host_kept:
        apps = "\n".join(deferred)
        if fits(text, apps):
            text = f"{text}\n{apps}"
            apps_omitted = False

    truncated = bool(omitted_w or omitted_e or apps_omitted or (core and not host_kept))
    if truncated:
        while True:
            parts = []
            if omitted_w:
                parts.append(f"omitted windows {','.join(omitted_w)}")
            if omitted_e:
                parts.append(f"omitted {omitted_e} elements")
            if apps_omitted and deferred:
                parts.append("host.installed_apps dropped")
            if core and not host_kept:
                parts.append("host core dropped")
            parts.append(f"kept {kept_e} elements")
            parts.append(f"chars {len(text)}/{budget}")
            marker = "[environment budget: " + "; ".join(parts) + "]"
            if fits(text, marker) or not text:
                if not text and len(marker) > budget:
                    short = f"[environment budget: over cap; chars {budget}]"
                    if len(short) > budget:
                        raise RuntimeError(f"max_environment_chars={budget} too small for budget marker")
                    text = short
                else:
                    text = f"{text}\n{marker}" if text else marker
                break
            if not screen:
                text = marker if len(marker) <= budget else f"[environment budget: over cap; chars {budget}]"
                break
            dropped = screen.pop()
            if dropped.strip().startswith("e"):
                kept_e = max(0, kept_e - 1)
                omitted_e += 1
            text = "\n".join(screen)
            host_kept = False
            if host_block and fits(text, host_block):
                text = f"{text}\n\n{host_block}" if text else host_block
                host_kept = True
    if len(text) > budget:
        raise RuntimeError(f"environment budget overran: {len(text)}>{budget}")
    return text


def coerce_node_output(node: str, result: Any) -> tuple[str, JsonDict]:
    if not (isinstance(result, tuple) and len(result) == 2):
        raise NodeRecordContractError(f"node '{node}' contract violation: expected (signal, patch)")
    signal, patch = result
    if not isinstance(signal, str) or not signal:
        raise NodeRecordContractError(f"node '{node}' contract violation: signal must be a non-empty string")
    if not isinstance(patch, dict):
        raise NodeRecordContractError(f"node '{node}' contract violation: patch must be dict")
    return signal, patch


def allowed_signals(wiring: JsonDict, node: str) -> set[str]:
    node_edges = wiring.get("topology", {}).get("edges", {}).get(node, {})
    return {str(s) for s in node_edges} if isinstance(node_edges, dict) else set()


def validate_signal(wiring: JsonDict, node: str, signal: str) -> None:
    signals = allowed_signals(wiring, node)
    if signal not in signals:
        raise TopologyContractError(
            f"node '{node}' emitted signal '{signal}' outside topology contract; allowed: {', '.join(sorted(signals))}"
        )


def state_brief(state: JsonDict) -> JsonDict:
    current_deed = state.get("current_deed") or {}
    return {
        "goal_interpretations": dict(state.get("goal_interpretations") or {}),
        "proven_ledger": list(state.get("proven_ledger") or []),
        "latest_counsel": state.get("latest_counsel") or "",
        "current_deed": {"description": current_deed.get("description", "")},
        "failure_streak": state.get("failure_streak", {}),
        "has_action_frame": bool(state.get("action_frame")),
    }


def environment_brief(state: JsonDict) -> JsonDict:
    return {"desktop_tree_text": state.get("desktop_tree_text", ""), "host": state.get("host_facts") or {}}


def execution_evidence(state: JsonDict) -> JsonDict:
    turn = state.get("turn_executions") or {}
    return {
        "faculties": turn if isinstance(turn, dict) else {},
        "provenance": "actor testimony about authored code — not independent world proof",
    }


def bump_failure_streak(state: JsonDict) -> JsonDict:
    previous = state.get("failure_streak") or {}
    return {"failure_streak": {"count": int(previous.get("count", 0) or 0) + 1, "updated_at": time.time()}}
