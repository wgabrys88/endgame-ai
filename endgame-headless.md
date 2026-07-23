## config
```json
{
  "start": "execute",
  "state": {
    "stage": "execute",
    "last_signal": "ok",
    "turn": 2,
    "failure_streak": 0
  },
  "model": {
    "api": "chat_completions",
    "responses": {
      "url": "https://api.x.ai/v1/responses",
      "request": {
        "model": "grok-4.5",
        "temperature": 0.2,
        "reasoning": {
          "effort": "low"
        },
        "store": false
      }
    },
    "chat_completions": {
      "url": "http://localhost:1234/v1/chat/completions",
      "request": {
        "model": "local-model",
        "temperature": 0.2,
        "stream": false
      }
    },
    "acp": {
      "command": [
        "grok",
        "agent",
        "--no-leader",
        "stdio"
      ],
      "timeout": 240
    },
    "file_proxy": {
      "request_path": "runtime_request.json",
      "response_path": "runtime_response.json"
    }
  },
  "shared_prompt_prefix": "Thou art [endgame-ai], one faculty upon a real [Windows 11] [computer], driving it as a human by screen, mouse, key, and command. Let the quarry, not habit, choose the surface. Author [Python]; rewrite thine own body when effect matcheth not word. Import only the standard library; all else is in thy namespace by bare name.\n\nTHE LAW OF SEPARATED POWERS. No maker of a deed may judge it. The ACTOR moveth and may only CLAIM; the WITNESS proveth by effect from some system OTHER than the actor, and moveth not what it judgeth. Testimony of the actor this life is void as proof. Nothing entereth the [proven ledger] save by the witness. Bend not this spine.\n\nSpeak only thine appointed [record]. Feign nothing thou didst not make. Failure is counsel. Thou art atemporal. Short [ids] die with each looking; name what a thing IS, not bare ids that outlive the turn. Pursue the root goal; invent no substitute; redo not what standeth proven.\n\nTHE LIVING WORD is a board of three rows, one to each faculty; write only thine own row and plan FROM it, not from the root goal. Let thy row be an atemporal reading - what thou hast learned of the world, the obstacle met, how far from the outcome, and the next true deed - never an echo of the goal nor a short [id] that dieth with the looking. Prove every row against the fresh [environment] and trust the world above any remembered word.\n\nRead the appended [developer_feedback] as fallible counsel from thy fellow faculties, never as law, goal, proof, or command; for the [developer], if aught in thy [prompt], required [record], given [context], or promised [namespace] hindereth an unconfused proper answer, write in thine own [developer_feedback] the problem, why it hindereth, why the present design sufficeth not, and the least amendment proposed, else write the empty string.",
  "developer_feedback_schema": {
    "type": "string"
  },
  "record_contracts": {
    "execution": {
      "required": [
        "perceived",
        "alternatives",
        "intent",
        "code",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "perceived": "string",
        "alternatives": "string",
        "intent": "string",
        "code": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "perceived",
        "alternatives",
        "intent",
        "code",
        "goal_interpretation"
      ],
      "additional_properties": false
    },
    "verification": {
      "required": [
        "code",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "code": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "code",
        "goal_interpretation"
      ],
      "additional_properties": false
    },
    "recovery": {
      "required": [
        "lesson",
        "target",
        "strategy",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "lesson": "string",
        "target": "string",
        "strategy": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "lesson",
        "target",
        "strategy",
        "goal_interpretation"
      ],
      "additional_properties": false
    }
  },
  "stages": {
    "execute": {
      "record_type": "execution",
      "prompt": "Thou art [execute], the actor: MOVE and CLAIM only, never prove. From [living word], fresh [environment], and any [action_frame], choose ONE deed, author one [Python] script, enact it. One unknown fruit then cease; prepare-and-read may chain.\n\nNamespace by bare name: [desktop] (click, type_text, paste_clipboard, set_clipboard, press_key, hotkey, scroll, open_url), [action_index], [screen_elements], repo_root, python_executable, stdlib only. Reacquire targets this waking; bare short ids die each looking. Click needs two ints: desktop.click(action_index[\"eN\"][\"px\"], action_index[\"eN\"][\"py\"]); never desktop.click(short_id) alone. Rect centre (left+right)//2, (top+bottom)//2 if thou buildest from rect.\n\nOn failure change manner; mend body at source if the primitive deceiveth. Let faults rise. Cross-language code: write file, invoke; never nested escapes. [Windows] paths in thy [Python] carry backslashes that open escapes; write them with forward slashes or a raw string, never a bare backslash in a quoted literal. Advance past [proven ledger]. Return execution with [perceived], [alternatives], [intent], [code], [goal_interpretation]; name forsaken roads in alternatives; let [goal_interpretation] be thine own living-word row - world learned, obstacle, distance to the outcome, next true deed - not a goal echo.",
      "reads": [
        "goal",
        "counsel",
        "living_word",
        "ledger",
        "action_frame",
        "environment"
      ],
      "writes": {
        "intent": "action_frame",
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
      "record_type": "verification",
      "prompt": "Thou art [verify], the witness. By the Law thou hast no hand - only eyes. Author read-only [Python] proving effect by a system OTHER than the actor. Fresh [environment] is already presented before thee; thou dost not re-scan. Bare names: [screen_elements], desktop_tree_text, stdlib (filesystem, processes, ports, logs, registry). No [desktop].\n\nActor testimony and files the actor wrote this life are void as proof. Judge by effect, not seeming. Discover ports/paths/PIDs; hardcode them not. Pronounce absence only after MORE THAN ONE kind of witness. No middle verdict: lacking independent advance, [deed_confirmed] is false.\n\nThy probe MUST set `verdict` (a dict with booleans goal_satisfied and deed_confirmed and non-blank reason) AND set `signal` accordingly: 'halt' if goal_satisfied (the WHOLE goal is proven, life endeth); else 'confirmed' if deed_confirmed (NEW advance past the proven ledger); else 'denied'. If thy probe would raise ere verdict, set signal='unwitnessed' and mend no body. Return verification; data: [code], [goal_interpretation]; let [goal_interpretation] be thine own living-word row - what the world proveth, the obstacle, distance to the outcome, next true test - not a goal echo.",
      "reads": [
        "goal",
        "counsel",
        "living_word",
        "ledger",
        "code",
        "evidence",
        "action_frame",
        "environment"
      ],
      "writes": {},
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
      "record_type": "recovery",
      "prompt": "Thou art [recover], conscience after denial. From denied deed, evidence, [failure_streak], and fresh [environment], name the true defect in [lesson] (what failed, why, what must change - no goal echo). Frame a strike departing from every approach the [living word] recordeth; higher streak demands another KIND of road, even mending body code. Bind [target] only to what the fresh [environment] beareth.\n\nReturn recovery; data: [lesson], [target], [strategy], [goal_interpretation]; let [goal_interpretation] be thine own living-word row - the defect learned, distance to the outcome, next true road - not a goal echo.",
      "reads": [
        "goal",
        "counsel",
        "living_word",
        "ledger",
        "evidence",
        "verdict",
        "failure_streak",
        "environment"
      ],
      "writes": {},
      "routes": {
        "ok": "execute"
      }
    }
  }
}
```

## engine
```python
import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib, queue, threading, time

BOARD = globals().get("BOARD", "endgame.md")
ARGV = globals().get("ARGV", sys.argv)
flag = lambda name: name in ARGV
opt = lambda name: ARGV[ARGV.index(name) + 1] if name in ARGV else None
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


def fenced(text):
    m = re.search(r"```(?:\w+)?\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else ""


def get_config(sections):
    return json.loads(fenced(sections["config"]) or sections["config"])


def strip_fence(s):
    text = s.strip()
    m = re.fullmatch(r"```(?:\w+)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def render_request(cfg, stage, sections):
    parts = [cfg.get("shared_prompt_prefix", ""), stage["prompt"], ""]
    for tag in stage.get("reads", []):
        parts.append("## %s\n%s" % (tag, sections.get(tag, "(empty)")))
    if cfg.get("developer_feedback_schema"):
        parts.append("## developer_feedback\n%s" % sections.get("developer_feedback", ""))
    return "\n\n".join(p for p in parts if p)


def _texts_from_parts(parts):
    if isinstance(parts, str):
        return [parts] if parts.strip() else []
    if not isinstance(parts, list):
        return []
    return [str(p.get("text") if isinstance(p, dict) else p) for p in parts
            if (isinstance(p, str) and p.strip()) or (isinstance(p, dict) and p.get("text"))]


def _extract_content(obj):
    if obj.get("choices"):
        return str(obj["choices"][0]["message"]["content"])
    content = str(obj.get("output_text") or "")
    if content.strip():
        return content
    return "\n".join(text for item in obj.get("output", []) if isinstance(item, dict)
                     and item.get("type") != "reasoning"
                     for text in _texts_from_parts(item.get("content")))


def _record_response_format(cfg, record_type):
    contract = cfg["record_contracts"][record_type]
    data_properties = {key: {} for key in contract["required"]}
    for key, type_name in contract.get("types", {}).items():
        data_properties.setdefault(key, {})["type"] = type_name
    for key in contract.get("non_empty", []):
        limit = {"string": "minLength", "array": "minItems", "object": "minProperties"}.get(
            contract.get("types", {}).get(key))
        if limit:
            data_properties.setdefault(key, {})[limit] = 1
    for key, values in dict(contract.get("enums", {})).items():
        data_properties.setdefault(key, {})["enum"] = list(values)
    feedback_schema = cfg.get("developer_feedback_schema")
    if feedback_schema:
        if "developer_feedback" in data_properties:
            raise RuntimeError("developer_feedback collides with stage field")
        data_properties["developer_feedback"] = dict(feedback_schema)
    return {
        "name": record_type + "_record",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "record_type": {"enum": [record_type]},
                "data": {
                    "type": "object",
                    "additionalProperties": contract.get("additional_properties", True),
                    "properties": data_properties,
                    "required": list(contract["required"]) + (["developer_feedback"] if feedback_schema else []),
                },
            },
            "required": ["record_type", "data"],
        },
    }


def _call_acp(model, prompt_text, fmt):
    acp = model.get("acp", {})
    proc = subprocess.Popen(acp.get("command", ["grok", "agent", "--no-leader", "stdio"]),
        cwd=str(pathlib.Path(BOARD).resolve().parent), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
    lines, rid = queue.Queue(), 0
    def read_lines():
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=read_lines, daemon=True).start()
    def rpc(method, params, capture=False):
        nonlocal rid
        rid += 1
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                                     "params": params}, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        chunks, deadline = [], time.monotonic() + float(acp.get("timeout", 240))
        while True:
            try:
                line = lines.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError("ACP timed out at " + method)
            if line is None:
                raise RuntimeError("ACP process exited at " + method)
            msg = json.loads(line)
            if msg.get("method") == "session/update" and capture:
                update = (msg.get("params") or {}).get("update") or {}
                content = update.get("content") or {}
                if update.get("sessionUpdate") == "agent_message_chunk" and content.get("type") == "text":
                    chunks.append(str(content.get("text") or ""))
            elif msg.get("method") == "session/request_permission":
                options = (msg.get("params") or {}).get("options") or []
                denied = next((o.get("optionId") for o in options
                               if str(o.get("kind", "")).startswith(("reject", "deny"))), None)
                outcome = ({"outcome": "selected", "optionId": denied}
                           if denied else {"outcome": "cancelled"})
                proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                                             "result": {"outcome": outcome}}) + "\n")
                proc.stdin.flush()
            elif msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError("ACP error at %s: %s" % (method, msg["error"]))
                return msg.get("result") or {}, "".join(chunks)
    try:
        rpc("initialize", {"protocolVersion": 1, "clientCapabilities": {
            "fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}})
        session, _ = rpc("session/new", {"cwd": str(pathlib.Path(BOARD).resolve().parent),
            "mcpServers": [], "_meta": {"systemPromptOverride":
            "Thou art a stateless record compiler. Use no tools. Return only the JSON value required by the user's schema."}})
        sid = session.get("sessionId")
        if not isinstance(sid, str):
            raise RuntimeError("ACP session/new returned no sessionId")
        schema_first = "Return only JSON matching this schema:\n" + json.dumps(
            fmt["schema"], ensure_ascii=False, separators=(",", ":")) + "\n\n" + prompt_text
        _result, content = rpc("session/prompt", {"sessionId": sid,
            "prompt": [{"type": "text", "text": schema_first}]}, True)
        return content
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=5)


def _atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.%s.%s" % (os.getpid(), time.time_ns()))
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.rename(tmp, path)


def _proxy_paths(model):
    cfg = model.get("file_proxy", {})
    root = pathlib.Path(BOARD).resolve().parent
    request = (root / cfg.get("request_path", "runtime_request.json")).resolve()
    response = (root / cfg.get("response_path", "runtime_response.json")).resolve()
    return request, response


def _write_proxy_request(request, record_type, fmt, prompt_text):
    request_id = "egai-%s-%s" % (os.getpid(), time.time_ns())
    _atomic_json(request, {
        "schema": "endgame-ai.file-proxy.request.v3",
        "record_type": record_type,
        "response_format": fmt,
        "expected_response": {"id": "copy request id", "record": "object matching response_format.schema"},
        "prompt": prompt_text,
        "id": request_id,
        "created_at": time.time(),
    })
    return request_id


def _read_proxy_response(request, response):
    pending = json.loads(request.read_text(encoding="utf-8"))
    obj = json.loads(response.read_text(encoding="utf-8"))
    if obj.get("id") != pending.get("id"):
        raise RuntimeError("file_proxy response id %r does not match pending request id %r"
                           % (obj.get("id"), pending.get("id")))
    record = obj["record"]
    request.unlink(missing_ok=True); response.unlink(missing_ok=True)
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def call_llm(cfg, stage, prompt_text):
    model = cfg["model"]
    api = model.get("api", "responses")
    fmt = _record_response_format(cfg, stage["record_type"])
    if api == "acp":
        return _call_acp(model, prompt_text, fmt)
    transport = model[api]
    url, body = transport["url"], dict(transport["request"])
    headers = {"Content-Type": "application/json"}
    if api == "responses":
        body.pop("previous_response_id", None)
        body["store"] = False
        body["input"] = prompt_text
        body["text"] = {"format": {"type": "json_schema", **fmt}}
        headers["Authorization"] = "Bearer " + os.environ["XAI_API_KEY"]
    elif api == "chat_completions":
        body["messages"] = [{"role": "user", "content": prompt_text}]
        body["response_format"] = {"type": "json_schema", "json_schema": fmt}
    else:
        raise RuntimeError("unknown model api: " + str(api))
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=240) as r:
        raw = r.read().decode()
    obj = json.loads(raw)
    return _extract_content(obj)


_CAPS = "unloaded"
def caps():
    global _CAPS
    if _CAPS == "unloaded":
        sections, _order = read_board(BOARD)
        src = fenced(sections.get("capabilities", ""))
        if not src:
            _CAPS = None
        else:
            import types
            mod = types.ModuleType("capabilities")
            mod.BOARD = BOARD
            mod.NO_GUI = flag("--no-gui")
            exec(src, mod.__dict__)
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
    g = pathlib.Path(BOARD).resolve().parent / "guidance.txt"
    if g.exists():
        note = g.read_text(encoding="utf-8").strip()
        if note:
            sections["counsel"] = note
            g.write_text("", encoding="utf-8")
    c = caps()
    if c is not None and hasattr(c, "environment"):
        c.environment(sections)


def _parse_living_word(text):
    rows = {f: "" for f in ("execute", "verify", "recover")}
    for ln in (text or "").split("\n"):
        m = re.match(r"\s*\[(\w+)\]\s?(.*)$", ln)
        if m and m.group(1) in rows:
            rows[m.group(1)] = m.group(2).strip()
    return rows


def _render_living_word(rows):
    return "\n".join("[%s] %s" % (f, rows.get(f) or "(not yet interpreted)")
                     for f in ("execute", "verify", "recover"))


def _set_living_word_row(sections, faculty, sentence):
    rows = _parse_living_word(sections.get("living_word", ""))
    rows[faculty] = str(sentence or "").strip().replace("\n", " ")
    sections["living_word"] = _render_living_word(rows)


def append_developer_feedback(cfg, stage_name, data, sections):
    if not cfg.get("developer_feedback_schema"):
        return
    feedback = data.get("developer_feedback")
    if not isinstance(feedback, str):
        raise RuntimeError("developer_feedback must be a string at stage " + stage_name)
    prior = sections.get("developer_feedback", "")
    entry = json.dumps({stage_name: feedback}, ensure_ascii=False, separators=(",", ":"))
    sections["developer_feedback"] = prior + ("\n" if prior else "") + entry


def turn(path, dry, inject, mode):
    sections, order = read_board(path)
    cfg = get_config(sections)
    if mode:
        cfg["model"]["api"] = {"xai": "responses", "lmstudio": "chat_completions", "acp": "acp", "file_proxy": "file_proxy"}[mode]
    st = cfg["state"]
    stage_name = st.get("stage") or cfg["start"]
    stage = cfg["stages"][stage_name]
    sections["failure_streak"] = str(st.get("failure_streak", 0))
    refresh_environment(sections)
    api = cfg["model"].get("api", "responses")
    if inject:
        reply = pathlib.Path(inject).read_text(encoding="utf-8-sig").strip()
    elif dry:
        print(render_request(cfg, stage, sections)); return None, True
    elif api == "file_proxy":
        request, response = _proxy_paths(cfg["model"])
        if not response.exists():
            if request.exists():
                rid = json.loads(request.read_text(encoding="utf-8")).get("id")
            else:
                fmt = _record_response_format(cfg, stage["record_type"])
                rid = _write_proxy_request(request, stage["record_type"], fmt, render_request(cfg, stage, sections))
            sys.stderr.write(
                "[endgame-ai] A mind is needed. The request awaits at %s\n"
                "Open that file: it carries the prompt and the exact response_format you must satisfy.\n"
                "Write your record to %s as {\"id\": \"%s\", \"record\": {\"record_type\": \"%s\", \"data\": {...}}}, "
                "then run this same command again to deliver your answer and receive the next request.\n"
                % (request.name, response.name, rid, stage["record_type"]))
            return None, True
        reply = _read_proxy_response(request, response)
    else:
        reply = call_llm(cfg, stage, render_request(cfg, stage, sections))
    if not (reply or "").strip():
        raise RuntimeError("model returned no text (empty completion) at stage " + stage_name)
    envelope = json.loads(strip_fence(reply))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
        raise RuntimeError("model reply is not a {record_type, data} envelope at stage " + stage_name)
    if envelope.get("record_type") != stage["record_type"]:
        raise RuntimeError("record_type mismatch at stage %s: expected %r, got %r"
                           % (stage_name, stage["record_type"], envelope.get("record_type")))
    data = envelope["data"]
    append_developer_feedback(cfg, stage_name, data, sections)
    write_board(path, sections, order)
    for field, tag in stage.get("writes", {}).items():
        if field in data:
            sections[tag] = str(data[field])
    if "goal_interpretation" in data:
        _set_living_word_row(sections, stage_name, data["goal_interpretation"])
    if stage_name == "recover":
        sections["action_frame"] = json.dumps(
            {"target": data["target"], "strategy": data["strategy"], "lesson": data["lesson"]},
            ensure_ascii=False, indent=2)
    signal = "ok"
    ex = stage.get("exec")
    if ex and ex["field"] in data:
        signal, out = run_exec(str(data[ex["field"]]), ex.get("namespace", "actor"), sections)
        sections[ex["output_to"]] = out
    if stage_name == "verify":
        if signal in ("confirmed", "halt"):
            led = sections.get("ledger", "").strip()
            verdict = json.loads(sections["verdict"].split("\n", 1)[0])
            reason = str(verdict["reason"]).strip().replace("\n", " ")
            frame = sections.get("action_frame", "").strip()
            deed = ""
            if frame and frame != "(empty)":
                try:
                    deed = str(json.loads(frame).get("target") or "").strip()
                except Exception:
                    deed = frame
            deed = deed.replace("\n", " ")
            fact = ("%s - witnessed: %s" % (deed, reason)) if deed else reason
            entry = "- " + fact
            existing = [l.strip() for l in led.split("\n")] if led and led != "none yet" else []
            if entry not in existing:
                sections["ledger"] = (led + "\n" + entry) if existing else entry
            st["failure_streak"] = 0
        elif signal == "denied":
            st["failure_streak"] = int(st.get("failure_streak", 0)) + 1
    nxt = stage["routes"].get(signal)
    if nxt is None:
        raise RuntimeError("unmapped signal %r at stage %s; routes: %s"
                           % (signal, stage_name, list(stage["routes"].keys())))
    st["stage"] = nxt; st["last_signal"] = signal; st["turn"] = int(st.get("turn", 0)) + 1
    sections["config"] = "```json\n" + json.dumps(cfg, indent=2) + "\n```"
    write_board(path, sections, order)
    sys.stderr.write("turn %d: stage=%s signal=%s -> %s (streak=%s)\n"
                     % (st["turn"], stage_name, signal, nxt, st.get("failure_streak", 0)))
    stop = (nxt is None) or (nxt == "halt")
    return nxt, stop


def factory_reset(path):
    sections, _order = read_board(path)
    src = fenced(sections.get("reset", ""))
    if not src:
        raise RuntimeError("no `## reset` script section found; cannot factory reset")
    here = pathlib.Path(path).resolve().parent
    rp = here / "reset.py"
    rp.write_text(src + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(rp), str(path)], cwd=str(here), check=True)


def main():
    dry = flag("--dry")
    once = flag("--once")
    inject = opt("--inject")
    mode = opt("--mode")
    if flag("--reset"):
        factory_reset(BOARD)
    while True:
        nxt, stop = turn(BOARD, dry, inject, mode)
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

PRESERVE = {"config", "engine", "capabilities", "reset", "goal", "developer_feedback"}
DEFAULTS = {
    "living_word": "[execute] (not yet interpreted)\n[verify] (not yet interpreted)\n[recover] (not yet interpreted)",
    "ledger": "none yet", "action_frame": "(empty)",
    "perceived": "(empty)", "alternatives": "(empty)", "code": "(empty)",
    "evidence": "(empty)", "verdict": "(empty)",
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
import types as _types
import pathlib as _pathlib

NO_GUI = True
ROOT = _pathlib.Path(globals().get("BOARD", ".")).resolve().parent


_LAST_OBS = {"action_index": {}, "screen_elements": [], "desktop_tree_text": ""}

def _no_gui_hand():
    def _absent(*_a, **_k):
        raise RuntimeError("no GUI on this host (--no-gui): the desktop hand cannot act here")
    return _types.SimpleNamespace(
        click=_absent, type_text=_absent, paste_clipboard=_absent,
        set_clipboard=_absent, press_key=_absent, hotkey=_absent,
        scroll=_absent, open_url=_absent,
    )


def build(kind, sections):
    common = {
        "action_index": _LAST_OBS["action_index"],
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
        "repo_root": str(ROOT),
        "python_executable": __import__("sys").executable,
    }
    if kind == "witness":
        return common
    if NO_GUI:
        common["desktop"] = _no_gui_hand()
        return common
    d = get_desktop()
    common["desktop"] = _types.SimpleNamespace(
        click=d.click, type_text=d.type_text, paste_clipboard=d.paste_clipboard,
        set_clipboard=d.set_clipboard, press_key=d.press_key, hotkey=d.hotkey,
        scroll=d.scroll, open_url=d.open_url,
    )
    return common


def environment(sections):
    if NO_GUI:
        _LAST_OBS["action_index"] = {}
        _LAST_OBS["screen_elements"] = []
        _LAST_OBS["desktop_tree_text"] = ""
        sections["environment"] = "(no GUI on this host: --no-gui; no screen observed)"
        return
    d = get_desktop()
    obs_result = d.observe({"step_px": 64, "max_subtree_nodes_per_point": 120})
    _LAST_OBS["action_index"] = obs_result.get("action_index", {}) or {}
    _LAST_OBS["screen_elements"] = obs_result.get("screen_elements", []) or []
    _LAST_OBS["desktop_tree_text"] = str(obs_result.get("desktop_tree_text") or "").strip()
    sections["environment"] = _LAST_OBS["desktop_tree_text"] or "(no interactable elements observed)"

```

## goal

## living_word
[execute] (not yet interpreted)
[verify] (not yet interpreted)
[recover] (not yet interpreted)

## ledger

## action_frame

## perceived

## alternatives

## code

## evidence

## verdict

## counsel

## environment

## failure_streak
0

## developer_feedback
