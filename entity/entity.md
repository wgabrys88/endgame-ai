## config
```json
{
  "start": "execute",
  "state": {
    "stage": null,
    "last_signal": null,
    "turn": 0
  },
  "model": {
    "url": "https://api.x.ai/v1/responses",
    "request": {
      "model": "grok-4.5",
      "temperature": 0.2,
      "reasoning": {
        "effort": "medium"
      }
    }
  },
  "stages": {
    "execute": {
      "prompt": "You are the ACTOR. Read the board, choose ONE deed, author Python in a `code` field that enacts it. You may only claim; you never prove. Return JSON {\"intent\":..., \"code\":..., \"living_word\":...}.",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "action_frame",
        "environment"
      ],
      "writes": {
        "intent": "action_frame",
        "living_word": "living_word",
        "code": "code"
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
      "prompt": "You are the WITNESS. You have no hand. Author read-only Python in `code` that sets `signal` to 'confirmed' or 'denied' by evidence from a system other than the actor. Return JSON {\"code\":..., \"living_word\":...}.",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "code",
        "evidence",
        "environment"
      ],
      "writes": {
        "living_word": "living_word"
      },
      "exec": {
        "field": "code",
        "namespace": "witness",
        "output_to": "verdict"
      },
      "routes": {
        "confirmed": "execute",
        "denied": "recover",
        "ok": "execute",
        "fault": "verify"
      }
    },
    "recover": {
      "prompt": "You are the CONSCIENCE after a denial. Name the true defect and frame a different attempt. Return JSON {\"lesson\":..., \"strategy\":..., \"living_word\":...}.",
      "reads": [
        "goal",
        "living_word",
        "ledger",
        "evidence",
        "verdict",
        "environment"
      ],
      "writes": {
        "strategy": "action_frame",
        "living_word": "living_word"
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
import json, os, re, sys, io, urllib.request, contextlib, pathlib

BOARD = globals().get("BOARD", "entity.md")
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


def render_request(stage, sections):
    parts = [stage["prompt"], ""]
    for tag in stage.get("reads", []):
        parts.append("## %s\n%s" % (tag, sections.get(tag, "(empty)")))
    return "\n\n".join(parts)


def call_llm(cfg, prompt_text):
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


# --- hands: optional, downloaded+cached by capabilities.py sitting next to the board ---
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
    c = caps()
    if c is not None and hasattr(c, "environment"):
        c.environment(sections)


def turn(path, dry, inject):
    sections, order = read_board(path)
    cfg = get_config(sections)
    st = cfg["state"]
    stage_name = st.get("stage") or cfg["start"]
    stage = cfg["stages"][stage_name]
    refresh_environment(sections)
    if inject:
        reply = pathlib.Path(inject).read_text(encoding="utf-8-sig").strip()
    elif dry:
        print(render_request(stage, sections)); return None, True
    else:
        reply = call_llm(cfg, render_request(stage, sections))
    data = json.loads(strip_fence(reply))
    for field, tag in stage.get("writes", {}).items():
        if field in data:
            sections[tag] = str(data[field])
    signal = "ok"
    ex = stage.get("exec")
    if ex and ex["field"] in data:
        signal, out = run_exec(str(data[ex["field"]]), ex.get("namespace", "actor"), sections)
        sections[ex["output_to"]] = out
    nxt = stage["routes"].get(signal) or stage["routes"].get("ok")
    st["stage"] = nxt; st["last_signal"] = signal; st["turn"] = int(st.get("turn", 0)) + 1
    sections["config"] = "```json\n" + json.dumps(cfg, indent=2) + "\n```"
    write_board(path, sections, order)
    sys.stderr.write("turn %d: stage=%s signal=%s -> %s\n" % (st["turn"], stage_name, signal, nxt))
    return nxt, (nxt is None)


def main():
    dry = "--dry" in ARGV
    once = "--once" in ARGV
    inject = ARGV[ARGV.index("--inject") + 1] if "--inject" in ARGV else None
    while True:
        nxt, stop = turn(BOARD, dry, inject)
        if dry or once or inject or stop:
            break


main()
```

## goal
(write the goal here — this is the lodestar; change it any time, even mid-run)

## living_word
(each stage overwrites its own learning here)

## ledger
none yet

## action_frame
none

## code
(the actor's last authored Python lands here)

## evidence
(stdout / fault from the last exec lands here)

## verdict
(the witness's verdict lands here)

## environment
(environment scan unavailable: No module named 'comtypes')
