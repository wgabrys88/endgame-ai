## config
```json
{
  "start": "execute",
  "state": {
    "stage": null,
    "last_signal": null,
    "turn": 0,
    "failure_streak": 0
  },
  "model": {
    "url": "https://api.x.ai/v1/responses",
    "request": {
      "model": "grok-4.5",
      "temperature": 0.0,
      "reasoning": {
        "effort": "low"
      },
      "store": false
    }
  },
  "shared_prompt_prefix": "Thou art [endgame-ai], one faculty upon a real [Windows 11] [computer], driving it as a human by screen, mouse, key, and command. Let the quarry, not habit, choose the surface. Author [Python]; rewrite thine own body when effect matcheth not word. Import only the standard library; all else is in thy namespace by bare name.\n\nTHE LAW OF SEPARATED POWERS. No maker of a deed may judge it. The ACTOR moveth and may only CLAIM; the WITNESS proveth by effect from some system OTHER than the actor, and moveth not what it judgeth. Testimony of the actor this life is void as proof. Nothing entereth the [proven ledger] save by the witness. Bend not this spine.\n\nSpeak only thine appointed [record]. Feign nothing thou didst not make. Failure is counsel. Thou art atemporal. Short [ids] die with each looking; name what a thing IS, not bare ids that outlive the turn. Pursue the root goal; invent no substitute; redo not what standeth proven.",
  "stages": {
    "execute": {
      "prompt": "Thou art [execute], the actor: MOVE and CLAIM only, never prove. From [living word], fresh [environment], and any [action_frame], choose ONE deed, author one [Python] script, enact it. One unknown fruit then cease; prepare-and-read may chain.\n\nNamespace by bare name: [desktop] (click, type_text, paste_clipboard, set_clipboard, press_key, hotkey, scroll, open_url), [action_index], [screen_elements], repo_root, python_executable, stdlib only. Reacquire targets this waking; bare short ids die each looking. Click needs two ints: desktop.click(action_index[\"eN\"][\"px\"], action_index[\"eN\"][\"py\"]); never desktop.click(short_id) alone.\n\nOn failure change manner; mend body at source if the primitive deceiveth. Let faults rise. Cross-language code: write file, invoke; never nested escapes. Windows paths carry backslashes that open escapes; write them with forward slashes or a raw string. Advance past [proven ledger]. Return JSON with [perceived], [alternatives], [intent], [code], [goal_interpretation]; name forsaken roads in alternatives. Set `signal='ok'` at the end of thy code if it runs clean.",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "action_frame",
        "environment"
      ],
      "writes": {
        "intent": "action_frame",
        "goal_interpretation": "living_word",
        "code": "code",
        "perceived": "perceived",
        "alternatives": "alternatives"
      },
      "exec": {
        "field": "code",
        "namespace": "actor",
        "output_to": "evidence"
      },
      "routes": {
        "ok": "verify",
        "fault": "recover"
      }
    },
    "verify": {
      "prompt": "Thou art [verify], the witness. By the Law thou hast no hand - only eyes. Author read-only [Python] proving effect by a system OTHER than the actor. Fresh [environment] is already presented before thee; thou dost not re-scan. Bare names: [screen_elements], desktop_tree_text, stdlib (filesystem, processes, ports, logs, registry). No [desktop].\n\nActor testimony and files the actor wrote this life are void as proof. Judge by effect, not seeming. Discover ports/paths/PIDs; hardcode them not. Pronounce absence only after MORE THAN ONE kind of witness.\n\nThy probe MUST set `verdict` (a dict with booleans goal_satisfied and deed_confirmed and non-blank reason) AND set `signal` accordingly: 'halt' if goal_satisfied (the WHOLE goal is proven, life endeth); else 'confirmed' if deed_confirmed (NEW advance past the proven ledger); else 'denied'. If thy probe would raise ere verdict, set signal='unwitnessed' and mend no body. Return JSON with [code], [goal_interpretation].",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "code",
        "evidence",
        "environment"
      ],
      "writes": {
        "goal_interpretation": "living_word",
        "code": "code"
      },
      "exec": {
        "field": "code",
        "namespace": "witness",
        "output_to": "verdict"
      },
      "routes": {
        "halt": "halt",
        "confirmed": "execute",
        "denied": "recover",
        "unwitnessed": "verify",
        "ok": "execute",
        "fault": "verify"
      }
    },
    "recover": {
      "prompt": "Thou art [recover], conscience after denial. From denied deed, evidence, [failure_streak], and fresh [environment], name the true defect in [lesson] (what failed, why, what must change - no goal echo). Frame a strike departing from every approach the [living word] recordeth; higher streak demands another KIND of road, even mending body code. Bind [target] only to what the fresh [environment] beareth. Return JSON with [lesson], [target], [strategy], [goal_interpretation].",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "evidence",
        "verdict",
        "failure_streak",
        "environment"
      ],
      "writes": {
        "strategy": "action_frame",
        "goal_interpretation": "living_word",
        "lesson": "lesson"
      },
      "routes": {
        "ok": "execute"
      }
    }
  }
}
```

## engine
```python
import json, os, re, sys, io, time, uuid, subprocess, urllib.request, urllib.error, contextlib, pathlib

BOARD = globals().get("BOARD", "endgame.md")
ARGV = globals().get("ARGV", sys.argv)
_DUMP_DIR = pathlib.Path(BOARD).resolve().parent / "_transmissions"
SEC = re.compile(r"^##\s+(\w+)\s*$", re.M)


def read_board(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out, order, cur, buf, fence = {}, [], None, [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else SEC.match(ln)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip("\n")
            cur, buf = m.group(1), []
            if cur not in order:
                order.append(cur)
        else:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf).strip("\n")
    return out, order


def write_board(path, sections, order):
    keys = order + [k for k in sections if k not in order]
    body = "\n\n".join("## %s\n%s" % (k, sections[k].strip()) for k in keys if k in sections)
    pathlib.Path(path).write_text(body.rstrip() + "\n", encoding="utf-8")


def get_config(sections):
    m = re.search(r"```(?:json)?\s*(.*?)```", sections["config"], re.S)
    return json.loads(m.group(1) if m else sections["config"])


def strip_fence(s):
    m = re.search(r"```(?:\w+)?\s*(.*?)```", s, re.S)
    return (m.group(1) if m else s).strip()


def render_request(cfg, stage, sections):
    parts = [cfg.get("shared_prompt_prefix", ""), stage["prompt"], ""]
    for tag in stage.get("reads", []):
        parts.append("## %s\n%s" % (tag, sections.get(tag, "(empty)")))
    return "\n\n".join(p for p in parts if p)


def _texts_from_parts(parts):
    if isinstance(parts, str):
        return [parts] if parts.strip() else []
    if not isinstance(parts, list):
        return []
    out = []
    for p in parts:
        if isinstance(p, str) and p.strip():
            out.append(p)
        elif isinstance(p, dict) and p.get("text"):
            out.append(str(p["text"]))
    return out


def _extract_content_reasoning(obj):
    content = str(obj.get("output_text") or "")
    reasoning_parts, message_parts = [], []
    if isinstance(obj.get("output"), list):
        for item in obj["output"]:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "reasoning":
                reasoning_parts.extend(_texts_from_parts(item.get("summary")))
                reasoning_parts.extend(_texts_from_parts(item.get("content")))
            else:
                message_parts.extend(_texts_from_parts(item.get("content")))
    if not content.strip():
        content = "\n".join(message_parts)
    return content, "\n".join(reasoning_parts).strip()


def _dump_transmission(url, payload, messages, raw_response_text, response_obj,
                       content, reasoning, http_status, error):
    """Write the full, untruncated request/response of one live transmission to
    `_transmissions/` beside the board (runtime scratch, gitignored). Fires on the
    success path and on transport error alike; never swallows -- caller re-raises."""
    _DUMP_DIR.mkdir(parents=True, exist_ok=True)
    prefix = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

    def pref(name):
        return _DUMP_DIR / (prefix + "_" + name)

    def write(path, text):
        path.write_text(text, encoding="utf-8", newline="\n")

    request_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    response_json = (json.dumps(response_obj, ensure_ascii=False, indent=2, default=str)
                     if response_obj is not None else (raw_response_text or ""))
    meta = {
        "dumped_at": time.time(),
        "prefix": prefix,
        "source": "live",
        "url": url,
        "http_status": http_status,
        "error": error,
        "request_chars": len(request_json),
        "raw_response_chars": len(raw_response_text or ""),
        "content_chars": len(content or ""),
        "reasoning_chars": len(reasoning or ""),
        "message_roles": [m.get("role") for m in messages],
        "message_char_counts": {m.get("role", "?"): len(m.get("content") or "") for m in messages},
    }
    bundle = {
        "meta": meta,
        "request_body": payload,
        "messages": messages,
        "raw_response_text": raw_response_text,
        "response_object": response_obj,
        "extracted_content": content,
        "extracted_reasoning": reasoning,
    }
    write(pref("transmission.json"), json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    write(pref("request_body.json"), request_json)
    write(pref("response_raw.json"), response_json)
    write(pref("response_raw.txt"), raw_response_text or "")
    write(pref("content.txt"), content or "")
    write(pref("reasoning.txt"), reasoning or "")
    for m in messages:
        write(pref("message_%s.txt" % str(m.get("role") or "unknown")), str(m.get("content") or ""))
    write(pref("meta.json"), json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    sys.stderr.write("TRANSMISSION DUMP (full, no truncation): %s prefix=%s%s\n"
                     % (_DUMP_DIR, prefix, " [%s]" % error if error else ""))
    return prefix


def call_llm(cfg, stage, prompt_text):
    key = os.environ["XAI_API_KEY"]
    url = cfg["model"]["url"]
    body = dict(cfg["model"]["request"])
    body["input"] = [{"role": "user", "content": prompt_text}]
    body["text"] = {"format": {"type": "json_object"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            http_status = int(getattr(r, "status", 200) or 200)
            raw = r.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            response_obj = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            response_obj = None
        _dump_transmission(url, body, body["input"], raw, response_obj, "", "",
                           int(exc.code), "HTTP %s" % exc.code)
        raise
    except urllib.error.URLError as exc:
        _dump_transmission(url, body, body["input"], "", None, "", "",
                           None, "URLError: %s" % getattr(exc, "reason", exc))
        raise
    obj = json.loads(raw)
    txt, reasoning = _extract_content_reasoning(obj)
    _dump_transmission(url, body, body["input"], raw, obj, txt, reasoning, http_status, None)
    return txt


_CAPS = "unloaded"
def caps():
    """Load the Windows hand from this board's own `## capabilities` python block.
    Fully self-contained: nothing is downloaded and no sibling file is required."""
    global _CAPS
    if _CAPS == "unloaded":
        sections, _order = read_board(BOARD)
        src = sections.get("capabilities", "")
        m = re.search(r"```(?:python)?\s*(.*?)```", src, re.S)
        if not m or not m.group(1).strip():
            _CAPS = None
        else:
            import types
            mod = types.ModuleType("capabilities")
            mod.BOARD = BOARD
            exec(m.group(1), mod.__dict__)
            _CAPS = mod
    return _CAPS


def run_exec(code, ns_kind, sections):
    ns = {"json": json, "os": os, "sys": sys, "pathlib": pathlib}
    c = caps()
    if c is not None and hasattr(c, "build"):
        ns.update(c.build(ns_kind, sections))
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, ns)
        sig = str(ns.get("signal") or "ok")
        verdict = ns.get("verdict")
        out = buf.getvalue()
        if verdict is not None:
            out = json.dumps(verdict, default=str) + ("\n" + out if out else "")
        return sig, out.strip() or "(no output)"
    except Exception:
        import traceback
        return "fault", traceback.format_exc()


def refresh_environment(sections):
    # [PORT] node_guidance folded here: read+clear guidance.txt into `counsel`.
    g = pathlib.Path(BOARD).resolve().parent / "guidance.txt"
    if g.exists():
        note = g.read_text(encoding="utf-8").strip()
        if note:
            sections["counsel"] = note
            g.write_text("", encoding="utf-8")
    c = caps()
    if c is not None and hasattr(c, "environment"):
        c.environment(sections)


def turn(path, dry, inject):
    sections, order = read_board(path)
    cfg = get_config(sections)
    st = cfg["state"]
    stage_name = st.get("stage") or cfg["start"]
    stage = cfg["stages"][stage_name]
    sections["failure_streak"] = str(st.get("failure_streak", 0))
    refresh_environment(sections)
    if inject:
        reply = pathlib.Path(inject).read_text(encoding="utf-8-sig").strip()
    elif dry:
        print(render_request(cfg, stage, sections)); return None, True
    else:
        reply = call_llm(cfg, stage, render_request(cfg, stage, sections))
    if not (reply or "").strip():
        raise RuntimeError("model returned no text (empty completion) at stage " + stage_name)
    data = json.loads(strip_fence(reply))
    for field, tag in stage.get("writes", {}).items():
        if field in data:
            sections[tag] = str(data[field])
    signal = "ok"
    ex = stage.get("exec")
    if ex and ex["field"] in data:
        signal, out = run_exec(str(data[ex["field"]]), ex.get("namespace", "actor"), sections)
        sections[ex["output_to"]] = out
    # [PORT] ledger append on witnessed advance; streak bump/reset
    if stage_name == "verify":
        if signal in ("confirmed", "halt"):
            led = sections.get("ledger", "").strip()
            fact = (sections.get("living_word", "") or "advance").strip().replace("\n", " ")
            entry = "- " + fact
            sections["ledger"] = (led + "\n" + entry) if led and led != "none yet" else entry
            st["failure_streak"] = 0
        elif signal == "denied":
            st["failure_streak"] = int(st.get("failure_streak", 0)) + 1
    nxt = stage["routes"].get(signal) or stage["routes"].get("ok")
    st["stage"] = nxt; st["last_signal"] = signal; st["turn"] = int(st.get("turn", 0)) + 1
    sections["config"] = "```json\n" + json.dumps(cfg, indent=2) + "\n```"
    write_board(path, sections, order)
    sys.stderr.write("turn %d: stage=%s signal=%s -> %s (streak=%s)\n"
                     % (st["turn"], stage_name, signal, nxt, st.get("failure_streak", 0)))
    stop = (nxt is None) or (nxt == "halt")
    return nxt, stop


def factory_reset(path):
    """Extract the `## reset` section to reset.py beside the board and run it as its own
    program, returning the board to a clean slate (goal and body preserved)."""
    sections, _order = read_board(path)
    src = sections.get("reset", "")
    m = re.search(r"```(?:python)?\s*(.*?)```", src, re.S)
    if not m or not m.group(1).strip():
        raise RuntimeError("no `## reset` script section found; cannot factory reset")
    here = pathlib.Path(path).resolve().parent
    rp = here / "reset.py"
    rp.write_text(m.group(1).strip() + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(rp), str(path)], cwd=str(here))


def main():
    dry = "--dry" in ARGV
    once = "--once" in ARGV
    inject = ARGV[ARGV.index("--inject") + 1] if "--inject" in ARGV else None
    if not dry and not inject:
        factory_reset(BOARD)
    while True:
        nxt, stop = turn(BOARD, dry, inject)
        if dry or once or inject or stop:
            break


main()
```

## reset
```python
import re, sys, json, pathlib

BOARD = sys.argv[1]
FENCE = chr(96) * 3
SEC = re.compile(r"^##\s+(\w+)\s*$", re.M)

# body sections and the goal are preserved; everything else is wiped to a clean slate
PRESERVE = {"config", "engine", "capabilities", "reset", "goal"}
DEFAULTS = {
    "living_word": "(empty)", "ledger": "none yet", "action_frame": "(empty)",
    "perceived": "(empty)", "alternatives": "(empty)", "code": "(empty)",
    "evidence": "(empty)", "verdict": "(empty)", "lesson": "(empty)",
    "counsel": "(empty)", "environment": "(fresh screen scan lands here each turn)",
    "failure_streak": "0",
}


def read_board(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out, order, cur, buf, fence = {}, [], None, [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith(FENCE):
            fence = not fence
        m = None if fence else SEC.match(ln)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip("\n")
            cur, buf = m.group(1), []
            if cur not in order:
                order.append(cur)
        else:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf).strip("\n")
    return out, order


sections, order = read_board(BOARD)
# config.state back to factory; the rest of config (model, prompts, stages) is untouched
m = re.search(FENCE + r"(?:json)?\s*(.*?)" + FENCE, sections["config"], re.S)
cfg = json.loads(m.group(1))
cfg["state"] = {"stage": None, "last_signal": None, "turn": 0, "failure_streak": 0}
sections["config"] = FENCE + "json\n" + json.dumps(cfg, indent=2) + "\n" + FENCE
for k, v in DEFAULTS.items():
    if k in sections and k not in PRESERVE:
        sections[k] = v
keys = order + [k for k in sections if k not in order]
body = "\n\n".join("## %s\n%s" % (k, sections[k].strip()) for k in keys if k in sections)
pathlib.Path(BOARD).write_text(body.rstrip() + "\n", encoding="utf-8")
sys.stderr.write("factory reset: working memory + state cleared; goal and body preserved\n")
```

## capabilities
```python
# --- eyes: window-first UIA observation (was core_observation.py) ---
import ctypes
import importlib
import time
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

user32 = ctypes.windll.user32


def load_uia() -> Any:
    comtypes.client.GetModule("UIAutomationCore.dll")
    return importlib.import_module("comtypes.gen.UIAutomationClient")


comtypes.CoInitialize()
uia = load_uia()


def _const(name: str) -> int:
    return int(getattr(uia, name))


TreeScope_Element = _const("TreeScope_Element")
TreeScope_Subtree = _const("TreeScope_Subtree")

PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId")
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId")
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId")
PID_NAME = _const("UIA_NamePropertyId")
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId")
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId")
PID_ENABLED = _const("UIA_IsEnabledPropertyId")
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId")
PID_HWND = _const("UIA_NativeWindowHandlePropertyId")
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId")
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId")
PID_WINDOW_INTERACTION_STATE = _const("UIA_WindowWindowInteractionStatePropertyId")
PID_ITEM_STATUS = _const("UIA_ItemStatusPropertyId")
SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_CONTENT_ELEMENT,
    PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS,
]

PID_VALUE_PATTERN = _const("UIA_ValuePatternId")
PID_TEXT_PATTERN = _const("UIA_TextPatternId")
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId")
SCAN_PATTERN_IDS = [PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN]

CONTROL_TYPE_NAMES = {
    getattr(uia, attr): attr.replace("UIA_", "").replace("ControlTypeId", "")
    for attr in dir(uia)
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId") and isinstance(getattr(uia, attr, None), int)
}
CLICK_ROLES = {"Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton"}
WRITE_ROLES = {"Edit", "ComboBox", "Spinner", "Document"}
READ_ROLES = {"Text", "ListItem"}
SCROLL_ROLES = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")


def action_for_role(role: str, class_name: str = "") -> str:
    if role in CLICK_ROLES:
        return "click"
    if role in WRITE_ROLES or (role == "Pane" and class_name == "Scintilla"):
        return "write"
    if role in READ_ROLES:
        return "read"
    if role in SCROLL_ROLES:
        return "scroll"
    return ""


def is_desktop_leakage(node: dict[str, Any]) -> bool:
    return node["role"] == "List" and node["name"] == "Desktop"


def enum_windows(min_area: int = 2500) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        h = int(hwnd)
        if h in seen or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w, ht = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or ht <= 0 or w * ht < min_area:
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        seen.add(h)
        out.append({
            "hwnd": h,
            "title": buf.value or "",
            "rect": {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)},
        })
        return True

    try:
        user32.EnumWindows(enum_proc(callback), 0)
    except Exception:
        pass
    return out


def _unwrap(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _to_int(v: Any) -> int:
    try:
        return int(_unwrap(v))
    except (TypeError, ValueError):
        return 0


def _to_str(v: Any) -> str:
    v = _unwrap(v)
    return "" if v is None else str(v)


def _to_bool(v: Any) -> bool:
    return bool(_unwrap(v)) if v is not None else False


def _to_rect(v: Any) -> dict[str, int]:
    val = _unwrap(v)
    try:
        if isinstance(val, (tuple, list)) and len(val) >= 4:
            left, top = int(val[0]), int(val[1])
            third, fourth = float(val[2]), float(val[3])
            if third > left or fourth > top:
                return {"left": left, "top": top, "right": int(third), "bottom": int(fourth)}
            return {"left": left, "top": top, "right": left + int(third), "bottom": top + int(fourth)}
        if getattr(val, "left", None) is not None:
            return {"left": int(val.left), "top": int(getattr(val, "top", 0)), "right": int(getattr(val, "right", 0)), "bottom": int(getattr(val, "bottom", 0))}
    except Exception:
        pass
    return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def _to_runtime_id(v: Any) -> list[int]:
    try:
        val = _unwrap(v)
        return [int(x) for x in list(val)] if val else []
    except Exception:
        return []


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        short = "_".join(map(str, runtime_id[-3:])) if len(runtime_id) > 3 else "_".join(map(str, runtime_id))
        return f"e_{short}"
    return f"e_{hwnd}_{rect.get('left',0)}_{rect.get('top',0)}"


def _cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _current(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCurrentPropertyValue(prop_id)
    except Exception:
        return None


def _pattern(element: Any, pattern_id: int) -> Any:
    try:
        return element.GetCachedPattern(pattern_id)
    except Exception:
        try:
            return element.GetCurrentPattern(pattern_id)
        except Exception:
            return None


class UiaScanner:
    def __init__(self, config: dict[str, Any], desktop_instance: Any = None):
        self.cfg = config
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, "automation") else comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)

    def _cache(self, scope: int = TreeScope_Subtree):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = scope
        for pid in SCAN_PROPERTY_IDS:
            req.AddProperty(pid)
        for pid in SCAN_PATTERN_IDS:
            req.AddPattern(pid)
        return req

    def _pattern_text(self, pattern: Any, label: str) -> dict[str, str]:
        out: dict[str, str] = {}
        if pattern is None:
            return out
        try:
            if label == "Value" and getattr(pattern, "Value", None) is not None:
                out["value"] = str(pattern.Value)
            elif label == "Text":
                doc = getattr(pattern, "DocumentRange", None)
                if doc is not None:
                    text = doc.GetText(-1)
                    if text and str(text).strip():
                        out["text"] = str(text)
                ranges = pattern.GetVisibleRanges()
                texts = []
                for i in range(int(getattr(ranges, "Length", 0)) if ranges is not None else 0):
                    t = ranges.GetElement(i).GetText(-1)
                    if t and str(t).strip():
                        texts.append(str(t))
                if texts:
                    out["text_ranges"] = "\n".join(texts)
            elif label == "LegacyIAccessible":
                for key in ("Value", "Name", "Description"):
                    val = getattr(pattern, key, None)
                    if val is not None and str(val).strip() not in ("", "0"):
                        out[f"legacy_{key.lower()}"] = str(val)
        except Exception:
            pass
        return out

    def element_to_raw(self, element: Any, parent_runtime_id: list[int] | None = None, depth: int = 0) -> dict[str, Any] | None:
        try:
            rect = _to_rect(_cached(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = _to_rect(_current(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                return None
            runtime_id = _to_runtime_id(_cached(element, PID_RUNTIME_ID)) or _to_runtime_id(_current(element, PID_RUNTIME_ID))
            hwnd = _to_int(_cached(element, PID_HWND))
            role = control_type_name(_to_int(_cached(element, PID_CONTROL_TYPE)) or _to_int(_current(element, PID_CONTROL_TYPE)))
            name = _to_str(_cached(element, PID_NAME)) or _to_str(_current(element, PID_NAME))
            class_name = _to_str(_cached(element, PID_CLASS_NAME))
            pattern_values: dict[str, str] = {}
            for pid, label in ((PID_VALUE_PATTERN, "Value"), (PID_TEXT_PATTERN, "Text"), (PID_LEGACY_PATTERN, "LegacyIAccessible")):
                pattern_values.update(self._pattern_text(_pattern(element, pid), label))
            text_full = pattern_values.get("text") or pattern_values.get("text_ranges") or pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("legacy_name") or name or ""
            px, py = (rect["left"] + rect["right"]) // 2, (rect["top"] + rect["bottom"]) // 2
            return {
                "id": _node_id(runtime_id, hwnd, rect),
                "role": role,
                "name": name,
                "automation_id": _to_str(_cached(element, PID_AUTOMATION_ID)),
                "class_name": class_name,
                "hwnd": hwnd,
                "framework_id": _to_str(_cached(element, PID_FRAMEWORK)),
                "rect": rect,
                "px": px,
                "py": py,
                "enabled": _to_bool(_cached(element, PID_ENABLED)),
                "offscreen": _to_bool(_cached(element, PID_OFFSCREEN)),
                "runtime_id": runtime_id,
                "text_full": text_full,
                "value": pattern_values.get("value") or pattern_values.get("legacy_value") or "",
                "patterns": list(pattern_values.keys()),
                "pattern_values": pattern_values,
                "depth": depth,
                "parent_runtime_id": parent_runtime_id or [],
                "is_content_element": _to_bool(_cached(element, PID_CONTENT_ELEMENT)) or _to_bool(_current(element, PID_CONTENT_ELEMENT)),
                "interaction_state": (lambda v: _to_int(v) if _unwrap(v) is not None else None)(_cached(element, PID_WINDOW_INTERACTION_STATE)) if role == "Window" else None,
                "item_status": _to_str(_cached(element, PID_ITEM_STATUS)),
                "action": action_for_role(role, class_name),
            }
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int | None = None) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        depth_ceiling = 45
        try:
            root_element = root_element.BuildUpdatedCache(self._cache(TreeScope_Subtree))
        except Exception:
            pass

        def visit(el: Any, parent_rid: list[int], d: int) -> None:
            if (max_nodes is not None and len(nodes) >= max_nodes) or d >= depth_ceiling:
                return
            node = self.element_to_raw(el, parent_rid, d)
            child_parent_rid, child_depth = parent_rid, d
            if node is not None and node["id"] not in seen:
                seen.add(node["id"])
                nodes.append(node)
                child_parent_rid, child_depth = node["runtime_id"], d + 1
            elif node is not None:
                return
            try:
                kids = el.GetCachedChildren()
                count = int(getattr(kids, "Length", 0)) if kids is not None else 0
            except Exception:
                kids, count = None, 0
            for i in range(count):
                if max_nodes is not None and len(nodes) >= max_nodes:
                    break
                try:
                    visit(kids.GetElement(i), child_parent_rid, child_depth)
                except Exception:
                    continue

        visit(root_element, [], 0)
        return nodes


def _probe_points(rect: dict[str, int], step_px: int) -> list[tuple[int, int]]:
    left, top = rect["left"], rect["top"]
    w, h = max(1, rect["right"] - left), max(1, rect["bottom"] - top)
    cols, rows = max(1, w // step_px), max(1, h // step_px)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    points: list[tuple[int, int]] = []
    cells: set[tuple[int, int]] = set()
    for i in range((cols + 1) * (rows + 1)):
        x = left + int(((0.5 + ax * (i + 1)) % 1.0) * w)
        y = top + int(((0.5 + ay * (i + 1)) % 1.0) * h)
        cell = (x // step_px, y // step_px)
        if cell not in cells:
            cells.add(cell)
            points.append((x, y))
    return points


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    # Mid-script callers sometimes pass a number meaning "wait"; config is mapping-only.
    cfg = dict(config) if isinstance(config, dict) else {}
    step_px = int(cfg.get("step_px", 64))
    max_subtree = int(cfg.get("max_subtree_nodes_per_point", 2000))
    sw, sh = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    screen = {"width": sw, "height": sh}

    windows = enum_windows()

    scanner = UiaScanner(cfg, desktop)
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    windows_out: list[dict[str, Any]] = []
    try:
        for win in windows:
            hwnd, rect = win["hwnd"], win["rect"]
            kept: dict[str, dict[str, Any]] = {}
            for x, y in _probe_points(rect, step_px):
                user32.SetCursorPos(int(x), int(y))
                pt = wintypes.POINT(int(x), int(y))
                try:
                    owner = int(user32.GetAncestor(user32.WindowFromPoint(pt), 2) or 0)
                except Exception:
                    owner = 0
                if owner != hwnd:
                    continue
                try:
                    root = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache(TreeScope_Element))
                except Exception:
                    continue
                if root is None:
                    continue
                for i, node in enumerate(scanner.harvest_subtree(root, max_subtree)):
                    if is_desktop_leakage(node):
                        continue
                    node["owner_hwnd"] = hwnd
                    if i == 0:
                        node.setdefault("hit_point", (int(x), int(y)))
                    nid = node["id"]
                    prev = kept.get(nid)
                    if prev is None:
                        kept[nid] = node
                    else:
                        if not prev.get("hit_point") and node.get("hit_point"):
                            prev["hit_point"] = node["hit_point"]
                        for key in ("text_full", "value"):
                            if node[key] and (not prev[key] or len(node[key]) > len(prev[key])):
                                prev[key] = node[key]
            win["elements"] = list(kept.values())
            windows_out.append(win)
    finally:
        if had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass

    result = _render(windows_out, screen)
    observed_at = time.time()
    return {
        "observed_at": observed_at,
        "desktop_tree_text": result["desktop_tree_text"],
        "action_index": result["action_index"],
        "screen_elements": result["screen_elements"],
        "observation_artifact": {"screen": screen},
    }


def _render(windows: list[dict[str, Any]], screen: dict[str, int]) -> dict[str, Any]:
    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    action_index: dict[str, dict[str, Any]] = {}
    screen_elements: list[dict[str, Any]] = []
    counter = {"n": 0}
    lines = ["W0 Screen Desktop"]

    for wi, win in enumerate(windows, start=1):
        wid = f"W{wi}"
        title = win["title"] or f"Window_{win['hwnd']}"
        elements = win["elements"]
        by_rid = {tuple(e.get("runtime_id") or []): e for e in elements if e.get("runtime_id")}
        action_children: dict[str, list[dict[str, Any]]] = {}
        roots: list[dict[str, Any]] = []

        def nearest_action_ancestor(e: dict[str, Any]) -> dict[str, Any] | None:
            seen: set[tuple] = set()
            prid = tuple(e.get("parent_runtime_id") or [])
            while prid and prid not in seen:
                seen.add(prid)
                anc = by_rid.get(prid)
                if anc is not None and anc is not e and anc.get("action"):
                    return anc
                cur = by_rid.get(prid)
                prid = tuple(cur.get("parent_runtime_id") or []) if cur else ()
            return None

        actionable = [e for e in elements if e.get("action")]
        for e in actionable:
            anc = nearest_action_ancestor(e)
            if anc is not None:
                action_children.setdefault(id(anc), []).append(e)
            else:
                roots.append(e)
            screen_elements.append({
                "id": e["id"], "name": e.get("name", ""), "role": e.get("role", ""),
                "text": e.get("text_full", "") or "", "value": e.get("value", "") or "",
                "px": e.get("px"), "py": e.get("py"), "rect": e.get("rect", {}), "hwnd": win["hwnd"],
                "enabled": e.get("enabled"),
            })

        lines.append(f"{wid} Window {clean(title)}")
        def emit(e: dict[str, Any], indent: int) -> None:
            counter["n"] += 1
            sid = f"e{counter['n']}"
            e["short_id"] = sid
            action = str(e.get("action", "")) if e.get("enabled") is not False else ""
            parts = [p for p in (
                sid, str(e.get("role", "")), clean(e.get("name", "") or ""),
                f"[{action}]" if action else "",
            ) if p]
            lines.append("  " * indent + " ".join(parts))
            action_index[sid] = {**{k: v for k, v in e.items() if k != "children"}, "short_id": sid}
            for child in action_children.get(id(e), []):
                emit(child, indent + 1)

        for e in roots:
            emit(e, 1)

    return {
        "action_index": action_index,
        "screen_elements": screen_elements,
        "desktop_tree_text": "\n".join(lines),
    }


# --- hand: input synthesis + app control (was core_desktop.py) ---
import ctypes
import importlib
import os
import subprocess
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

ROOT = __import__("pathlib").Path(globals().get("BOARD", ".")).resolve().parent
user32 = ctypes.windll.user32
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
if not user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
    raise ctypes.WinError()

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
_ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def _load_uia_module() -> Any:
    comtypes.client.GetModule("UIAutomationCore.dll")
    return importlib.import_module("comtypes.gen.UIAutomationClient")


uia = _load_uia_module()
comtypes.CoInitialize()


KEY_MAP: dict[str, int] = {
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B,
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "delete": 0x2E, "del": 0x2E, "backspace": 0x08, "insert": 0x2D,
    **{chr(ord("a") + i): 0x41 + i for i in range(26)},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


class Desktop:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: Any = None

    @property
    def automation(self) -> Any:
        if self._automation is None:
            self._automation = comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
        return self._automation

    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if config is None:
            cfg = self.config
        elif isinstance(config, dict):
            cfg = config
        else:
            cfg = self.config
        return observe(self, cfg)

    def click(self, x: int, y: int, hwnd: int = 0) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"click coordinates ({x}, {y}) outside physical screen {width}x{height}")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def set_clipboard(self, text: str) -> dict[str, Any]:
        command = ["powershell.exe", "-NoProfile", "-Command", "$in=[Console]::In.ReadToEnd(); Set-Clipboard -Value $in"]
        completed = subprocess.run(command, input=str(text).encode("utf-8"), capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode != 0:
            raise RuntimeError(f"clipboard write failed: {(completed.stderr or completed.stdout).decode('utf-8', 'replace').strip()}")
        return {"ok": True, "action": "set_clipboard", "chars": len(str(text))}

    def type_text(self, text: str) -> dict[str, Any]:
        s = str(text)
        code_units = list(s.encode("utf-16-le"))
        events = []
        for i in range(0, len(code_units), 2):
            unit = code_units[i] | (code_units[i + 1] << 8)
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                events.append(_INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags, time=0, dwExtraInfo=0))))
        if not events:
            return {"ok": True, "action": "type_text", "chars": 0}
        arr = (_INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"ok": True, "action": "type_text", "chars": len(s)}

    def paste_clipboard(self, text: str) -> dict[str, Any]:
        self.set_clipboard(text)
        pasted = self.hotkey("ctrl", "v")
        if pasted.get("ok") is not True:
            raise RuntimeError(f"paste failed: {pasted}")
        return {"ok": True, "action": "paste_clipboard", "chars": len(str(text))}

    def press_key(self, key: str) -> dict[str, Any]:
        vk = KEY_MAP.get(str(key).strip().lower())
        if vk is None:
            raise RuntimeError(f"unknown key: {key}; known: {', '.join(sorted(KEY_MAP))}")
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "press_key", "key": key}

    def hotkey(self, *keys: Any) -> dict[str, Any]:
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            raw_parts = list(keys[0])
        elif len(keys) == 1:
            raw_parts = str(keys[0]).split("+")
        else:
            raw_parts = list(keys)
        parts = [str(k).strip().lower() for k in raw_parts if str(k).strip()]
        if not parts:
            raise RuntimeError("hotkey requires at least one key")
        vks = []
        for k in parts:
            vk = KEY_MAP.get(k)
            if vk is None:
                raise RuntimeError(f"unknown key in combination: {k}; known: {', '.join(sorted(KEY_MAP))}")
            vks.append(vk)
        for vk in vks[:-1]:
            user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 2, 0)
        for vk in reversed(vks[:-1]):
            user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "hotkey", "keys": parts}

    def scroll(self, x: int, y: int, amount: int, hwnd: int = 0) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"scroll coordinates ({x}, {y}) outside physical screen {width}x{height}")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
        return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def open_url(self, browser: str = "default", url: str = "") -> dict[str, Any]:
        if not str(url or "").strip():
            raise RuntimeError("open_url requires a non-empty url")
        browser_key = str(browser or "").strip().lower()
        if browser_key == "default":
            os.startfile(str(url))
            return {"ok": True, "action": "open_url", "browser": "default", "url": url}
        subprocess.Popen([str(browser), str(url)])
        return {"ok": True, "action": "open_url", "browser": browser_key, "url": url}


_desktop_instance: Desktop | None = None


def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    global _desktop_instance
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance

# ============================================================================
# capabilities API consumed by the engine (build namespaces + refresh environment)
# ============================================================================
import types as _types

_LAST_OBS = {"action_index": {}, "screen_elements": [], "desktop_tree_text": ""}


def build(kind, sections):
    """actor -> full hand + indices; witness -> read-only eyes, no hand."""
    common = {
        "action_index": _LAST_OBS["action_index"],
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
        "repo_root": str(ROOT),
        "python_executable": __import__("sys").executable,
    }
    if kind == "witness":
        return common
    d = get_desktop()
    hand = _types.SimpleNamespace(
        click=d.click, type_text=d.type_text, paste_clipboard=d.paste_clipboard,
        set_clipboard=d.set_clipboard, press_key=d.press_key, hotkey=d.hotkey,
        scroll=d.scroll, open_url=d.open_url,
    )
    common["desktop"] = hand
    return common


def environment(sections):
    """Refresh the `environment` section with a fresh window-first screen scan."""
    d = get_desktop()
    obs_result = d.observe({"step_px": 64, "max_subtree_nodes_per_point": 120})
    _LAST_OBS["action_index"] = obs_result.get("action_index", {}) or {}
    _LAST_OBS["screen_elements"] = obs_result.get("screen_elements", []) or []
    _LAST_OBS["desktop_tree_text"] = str(obs_result.get("desktop_tree_text") or "").strip()
    sections["environment"] = _LAST_OBS["desktop_tree_text"] or "(no interactable elements observed)"
```

## goal
(write the goal here — lodestar; change any time, even mid-run)

## living_word
(each stage overwrites its own learning here)

## ledger
none yet

## action_frame
none

## perceived
(actor's read of the present state)

## alternatives
(roads the actor weighed and forsook)

## code
(the last authored Python lands here)

## evidence
(stdout / fault from the last actor exec)

## verdict
(the witness's verdict)

## lesson
(recover's named defect)

## counsel
(operator note from guidance.txt, folded in during environment refresh)

## environment
(fresh screen scan lands here each turn)

## failure_streak
0
