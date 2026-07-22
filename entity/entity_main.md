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
import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib

BOARD = globals().get("BOARD", "entity_main.md")
ARGV = globals().get("ARGV", sys.argv)
SEC = re.compile(r"^##\s+(\w+)\s*$", re.M)


def read_board(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out, marks = {}, list(SEC.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[m.group(1)] = text[m.end():end].strip("\n")
    return out, [m.group(1) for m in marks]


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


def call_llm(cfg, stage, prompt_text):
    key = os.environ["XAI_API_KEY"]
    body = dict(cfg["model"]["request"])
    body["input"] = [{"role": "user", "content": prompt_text}]
    body["text"] = {"format": {"type": "json_object"}}
    req = urllib.request.Request(cfg["model"]["url"], data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    with urllib.request.urlopen(req, timeout=240) as r:
        obj = json.loads(r.read().decode())
    txt = obj.get("output_text") or ""
    if not txt and isinstance(obj.get("output"), list):
        for it in obj["output"]:
            for c in (it.get("content") or []):
                if isinstance(c, dict) and c.get("text"):
                    txt += c["text"]
    return txt


_CAPS = "unloaded"
def caps():
    global _CAPS
    if _CAPS == "unloaded":
        p = pathlib.Path(BOARD).resolve().parent / "capabilities.py"
        if not p.exists():
            _CAPS = None
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location("capabilities", p)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
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
(environment scan unavailable: No module named 'comtypes')

## failure_streak
2
