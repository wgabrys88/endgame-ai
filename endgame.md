## config
```json
{
  "start": "execute",
  "state": {
    "stage": "verify",
    "last_signal": "ok",
    "turn": 1,
    "failure_streak": 0
  },
  "model": {
    "api": "responses",
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
      "prompt": "Thou art [execute], the actor: MOVE and CLAIM only, never prove. From [living word], fresh [environment], and any [action_frame], choose ONE deed, author one [Python] script, enact it. One unknown fruit then cease; prepare-and-read may chain.\n\nNamespace by bare name: [desktop] (click, type_text, paste_clipboard, set_clipboard, press_key, hotkey, scroll, open_url), [action_index], [screen_elements], repo_root, python_executable, stdlib only. Reacquire targets this waking: every eN outside fresh [environment] is dead; choose anew by current window, role, and name. Bind once: t=action_index[\"eN\"]; check t's role and name against thine intended target; desktop.click(t[\"px\"], t[\"py\"], hwnd=t[\"owner_hwnd\"]). Never mix ids, coordinates, or owners, nor copy an eN from [living word] or [action_frame].\n\nOn failure change manner; mend body at source if the primitive deceiveth. Let faults rise. Cross-language code: write file, invoke; never nested escapes. [Windows] paths in thy [Python] carry backslashes that open escapes; write them with forward slashes or a raw string, never a bare backslash in a quoted literal. Advance past [proven ledger]. Return execution with [perceived], [alternatives], [intent], [code], [goal_interpretation]; name forsaken roads in alternatives; let [goal_interpretation] be thine own living-word row - world learned, obstacle, distance to the outcome, next true deed - not a goal echo.",
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
      "prompt": "Thou art [recover], conscience after denial. From denied deed, evidence, [failure_streak], and fresh [environment], name the true defect in [lesson] (what failed, why, what must change - no goal echo). Frame a strike departing from every approach the [living word] recordeth; higher streak demands another KIND of road, even mending body code. Bind [target] semantically by current window, role, and name; never emit an eN because execute awaketh after a new scan.\n\nReturn recovery; data: [lesson], [target], [strategy], [goal_interpretation]; let [goal_interpretation] be thine own living-word row - the defect learned, distance to the outcome, next true road - not a goal echo.",
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
import ctypes
import time
from ctypes import wintypes
from typing import Any

NO_GUI = bool(globals().get("NO_GUI", False))
user32 = ole32 = oleaut32 = None
AUTOMATION = None


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class _VARIANT_VALUE(ctypes.Union):
    _fields_ = [("llVal", ctypes.c_longlong), ("lVal", wintypes.LONG), ("dblVal", ctypes.c_double), ("boolVal", ctypes.c_short), ("bstrVal", ctypes.c_void_p), ("parray", ctypes.c_void_p), ("punkVal", ctypes.c_void_p)]


class _VARIANT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort), ("value", _VARIANT_VALUE)]


def _guid(a, b, c, *d):
    return _GUID(a, b, c, (ctypes.c_ubyte * 8)(*d))


def _call(ptr, slot, *types):
    address = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[slot]
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(address)


def _check(hr):
    if hr < 0:
        raise OSError("UI Automation HRESULT 0x%08X" % (hr & 0xFFFFFFFF))


def _bind_windows():
    global user32, ole32, oleaut32, AUTOMATION
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ole32, oleaut32 = ctypes.WinDLL("ole32"), ctypes.WinDLL("oleaut32")
    user32.SetCursorPos.argtypes, user32.SetCursorPos.restype = [ctypes.c_int, ctypes.c_int], wintypes.BOOL
    user32.GetCursorPos.argtypes, user32.GetCursorPos.restype = [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL
    user32.WindowFromPoint.argtypes, user32.WindowFromPoint.restype = [wintypes.POINT], wintypes.HWND
    user32.GetAncestor.argtypes, user32.GetAncestor.restype = [wintypes.HWND, wintypes.UINT], wintypes.HWND
    ole32.CoInitialize.argtypes, ole32.CoInitialize.restype = [ctypes.c_void_p], ctypes.c_long
    ole32.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole32.CoCreateInstance.restype = ctypes.c_long
    oleaut32.VariantClear.argtypes = [ctypes.POINTER(_VARIANT)]
    oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
    oleaut32.SafeArrayGetLBound.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(wintypes.LONG)]
    oleaut32.SafeArrayGetUBound.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(wintypes.LONG)]
    oleaut32.SafeArrayAccessData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    oleaut32.SafeArrayUnaccessData.argtypes = [ctypes.c_void_p]
    _check(ole32.CoInitialize(None))
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    if not user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
        raise ctypes.WinError()
    AUTOMATION = _Automation()


def _array(value, kind):
    lo, hi, data = wintypes.LONG(), wintypes.LONG(), ctypes.c_void_p()
    _check(oleaut32.SafeArrayGetLBound(value, 1, ctypes.byref(lo)))
    _check(oleaut32.SafeArrayGetUBound(value, 1, ctypes.byref(hi)))
    _check(oleaut32.SafeArrayAccessData(value, ctypes.byref(data)))
    try:
        return list(ctypes.cast(data, ctypes.POINTER(kind))[:hi.value - lo.value + 1])
    finally:
        _check(oleaut32.SafeArrayUnaccessData(value))


def _value(raw):
    try:
        base = raw.vt & 0xFFF
        if raw.vt & 0x2000:
            return _array(raw.parray, ctypes.c_double if base == 5 else wintypes.LONG)
        if base == 8:
            return ctypes.wstring_at(raw.bstrVal) if raw.bstrVal else ""
        if base == 11:
            return raw.boolVal != 0
        if base == 5:
            return raw.dblVal
        if base in (2, 3, 19):
            return raw.lVal
        return None
    finally:
        oleaut32.VariantClear(ctypes.byref(raw))


def _release(ptr):
    ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])(ptr)


def _bstr(ptr, slot, *args):
    out = ctypes.c_void_p()
    _check(_call(ptr, slot, *(type(arg) for arg in args), ctypes.POINTER(ctypes.c_void_p))(ptr, *args, ctypes.byref(out)))
    try:
        return ctypes.wstring_at(out) if out else ""
    finally:
        oleaut32.SysFreeString(out)


class _Object:
    def __init__(self, ptr):
        self.ptr = ptr

    def __del__(self):
        if self.ptr:
            _release(self.ptr)
            self.ptr = None


class _Array(_Object):
    def __init__(self, ptr, item):
        super().__init__(ptr)
        self.item = item

    @property
    def Length(self):
        out = ctypes.c_int()
        _check(_call(self.ptr, 3, ctypes.POINTER(ctypes.c_int))(self.ptr, ctypes.byref(out)))
        return out.value

    def GetElement(self, index):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 4, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(self.ptr, index, ctypes.byref(out)))
        return self.item(out)


class _CacheRequest(_Object):
    def AddProperty(self, prop):
        _check(_call(self.ptr, 3, ctypes.c_int)(self.ptr, prop))

    def AddPattern(self, pattern):
        _check(_call(self.ptr, 4, ctypes.c_int)(self.ptr, pattern))

    @property
    def TreeScope(self):
        out = ctypes.c_int()
        _check(_call(self.ptr, 6, ctypes.POINTER(ctypes.c_int))(self.ptr, ctypes.byref(out)))
        return out.value

    @TreeScope.setter
    def TreeScope(self, scope):
        _check(_call(self.ptr, 7, ctypes.c_int)(self.ptr, scope))


class _ValuePattern(_Object):
    def __init__(self, ptr, cached):
        super().__init__(ptr)
        self.cached = cached

    @property
    def Value(self):
        return _bstr(self.ptr, 6 if self.cached else 4)


class _TextRange(_Object):
    def GetText(self, length):
        return _bstr(self.ptr, 12, ctypes.c_int(length))


class _TextPattern(_Object):
    @property
    def DocumentRange(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 7, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _TextRange(out)

    def GetVisibleRanges(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 6, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _Array(out, _TextRange)


class _LegacyPattern(_Object):
    def __init__(self, ptr, cached):
        super().__init__(ptr)
        self.cached = cached

    @property
    def Name(self):
        return _bstr(self.ptr, 17 if self.cached else 7)

    @property
    def Value(self):
        return _bstr(self.ptr, 18 if self.cached else 8)

    @property
    def Description(self):
        return _bstr(self.ptr, 19 if self.cached else 9)


PATTERNS = {
    10002: (_ValuePattern, _guid(0xA94CD8B1, 0x0844, 0x4CD6, 0x9D, 0x2D, 0x64, 0x05, 0x37, 0xAB, 0x39, 0xE9)),
    10014: (_TextPattern, _guid(0x32EBA289, 0x3583, 0x42C9, 0x9C, 0x59, 0x3B, 0x6D, 0x9A, 0x1E, 0x9B, 0x6A)),
    10018: (_LegacyPattern, _guid(0x828055AD, 0x355B, 0x4435, 0x86, 0xD5, 0x3B, 0x51, 0xC1, 0x4A, 0x9B, 0x1B)),
}


class _Element(_Object):
    def _property(self, slot, prop):
        raw = _VARIANT()
        _check(_call(self.ptr, slot, ctypes.c_int, ctypes.POINTER(_VARIANT))(self.ptr, prop, ctypes.byref(raw)))
        return _value(raw)

    def GetCurrentPropertyValue(self, prop):
        return self._property(10, prop)

    def GetCachedPropertyValue(self, prop):
        return self._property(12, prop)

    def _pattern(self, slot, pattern):
        wrapper, iid = PATTERNS[pattern]
        out = ctypes.c_void_p()
        _check(_call(self.ptr, slot, ctypes.c_int, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(self.ptr, pattern, ctypes.byref(iid), ctypes.byref(out)))
        return wrapper(out, slot == 15) if wrapper is not _TextPattern else wrapper(out)

    def GetCurrentPattern(self, pattern):
        return self._pattern(14, pattern)

    def GetCachedPattern(self, pattern):
        return self._pattern(15, pattern)

    def BuildUpdatedCache(self, request):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 9, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.ptr, request.ptr, ctypes.byref(out)))
        return _Element(out)

    def GetCachedChildren(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 19, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _Array(out, _Element) if out else None


class _Automation(_Object):
    def __init__(self):
        ptr = ctypes.c_void_p()
        clsid = _guid(0xFF48DBA4, 0x60EF, 0x4201, 0xAA, 0x87, 0x54, 0x10, 0x3E, 0xEF, 0x59, 0x4E)
        iid = _guid(0x30CBE57D, 0xD9D0, 0x452A, 0xAB, 0x13, 0x7A, 0xC5, 0xAC, 0x48, 0x25, 0xEE)
        _check(ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(ptr)))
        super().__init__(ptr)

    def CreateCacheRequest(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 20, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _CacheRequest(out)

    def ElementFromPointBuildCache(self, point, request):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 11, wintypes.POINT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.ptr, point, request.ptr, ctypes.byref(out)))
        return _Element(out) if out else None


PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME = 30000, 30001, 30003, 30005
PID_ENABLED, PID_AUTOMATION_ID, PID_CLASS_NAME, PID_CONTENT_ELEMENT = 30010, 30011, 30012, 30017
PID_HWND, PID_OFFSCREEN, PID_FRAMEWORK, PID_ITEM_STATUS = 30020, 30022, 30024, 30026
PID_WINDOW_INTERACTION_STATE = 30076
SCAN_PROPERTY_IDS = [PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME, PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_CONTENT_ELEMENT, PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS]
PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN = PATTERNS
SCAN_PATTERN_IDS = list(PATTERNS)
TreeScope_Element, TreeScope_Subtree = 1, 7
CONTROL_TYPE_NAMES = dict(enumerate("Button Calendar CheckBox ComboBox Edit Hyperlink Image ListItem List Menu MenuBar MenuItem ProgressBar RadioButton ScrollBar Slider Spinner StatusBar Tab TabItem Text ToolBar ToolTip Tree TreeItem Custom Group Thumb DataGrid DataItem Document SplitButton Window Pane Header HeaderItem Table TitleBar Separator SemanticZoom AppBar".split(), 50000))
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
            return {"left": left, "top": top, "right": left + int(val[2]), "bottom": top + int(val[3])}
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
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, "automation") else AUTOMATION

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
            for pid, label in ((PID_VALUE_PATTERN, "Value"), (PID_LEGACY_PATTERN, "LegacyIAccessible")):
                pattern_values.update(self._pattern_text(_pattern(element, pid), label))
            text_full = pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("legacy_name") or name or ""
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


def _move_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
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
                x, y = max(0, min(sw - 1, x)), max(0, min(sh - 1, y))
                _move_cursor(x, y)
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
                _move_cursor(saved.x, saved.y)
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

        actionable = [e for e in elements if e.get("action") and not e.get("offscreen") and 0 <= e["px"] < screen["width"] and 0 <= e["py"] < screen["height"]]
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


import ctypes
import os
import subprocess
from ctypes import wintypes
from typing import Any

ROOT = __import__("pathlib").Path(globals().get("BOARD", ".")).resolve().parent
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

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
            self._automation = AUTOMATION
        return self._automation

    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if config is None:
            cfg = self.config
        elif isinstance(config, dict):
            cfg = config
        else:
            cfg = self.config
        return observe(self, cfg)

    def click(self, x: int, y: int, hwnd: int) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"click coordinates ({x}, {y}) outside physical screen {width}x{height}")
        expected = int(user32.GetAncestor(wintypes.HWND(int(hwnd)), 2) or 0)
        if not expected:
            raise RuntimeError(f"click target hwnd {hwnd} is no longer valid")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        actual = int(user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(int(x), int(y))), 2) or 0)
        if actual != expected:
            raise RuntimeError(f"click point ({x}, {y}) belongs to hwnd {actual}, expected {expected}")
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
import types as _types

_LAST_OBS = {"action_index": {}, "screen_elements": [], "desktop_tree_text": ""}

if not NO_GUI:
    _bind_windows()


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
Create or use a blank Windows Notepad document whose exact contents are ENDGAME_CAMPAIGN_02_AGNOSTIC. Leave the document open and unsaved. Choose any available generic method. The goal is complete only when a fresh desktop observation independently proves that exact marker is visible inside the Notepad document.

## living_word
[execute] World: blank Untitled Notepad already open with writable document. Obstacle: marker string not yet in the editor. Distance: one input action from visible marker. Next: click document and type exact marker, leave unsaved.
[verify] (not yet interpreted)
[recover] (not yet interpreted)

## ledger
none yet

## action_frame
Focus the Notepad document body and type the exact marker ENDGAME_CAMPAIGN_02_AGNOSTIC so it becomes visible unsaved content.

## perceived
Untitled Notepad is already open and blank (0 characters, Line 1 Column 1). Document write target e16 exists. Taskbar also shows Notepad running. Marker text is not yet present.

## alternatives
Could launch a fresh Notepad via Start/Search or win+r notepad; could paste via clipboard instead of type_text; could focus via taskbar e8. Forsaken because blank Untitled editor is already frontmost and ready.

## code
desktop.click(action_index["e16"]["px"], action_index["e16"]["py"])
desktop.type_text("ENDGAME_CAMPAIGN_02_AGNOSTIC")

## evidence
(no output)

## verdict
(empty)

## counsel
(empty)

## environment
W0 Screen Desktop
W1 Window Window_65810
  e1 Button Task Manager - 1 running window [click]
  e2 Button Start [click]
  e3 Button Search [click]
    e4 Text Search [read]
  e5 Button File Explorer pinned [click]
  e6 Button Google Chrome - 2 running windows pinned [click]
  e7 Button ChatGPT - 1 running window [click]
  e8 Button Notepad - 1 running window [click]
  e9 Button Show Hidden Icons [click]
  e10 Button Task Manager CPU 14% Memory 19% Disk 0% Network 0% [click]
  e11 Button Volume Speakers (Creative SB X-Fi): 89% [click]
  e12 Button Clock 9:55:14 PM ‎7/‎23/‎2026 [click]
W2 Window Untitled - Notepad
  e13 TabItem Untitled. Unmodified. [click]
    e14 Text Untitled [read]
    e15 Button Close Tab [click]
  e16 Document Text editor [write]
  e17 Text Line 1, Column 1 [read]
  e18 Text 0 characters [read]
  e19 Text Plain text [read]
  e20 Text Zoom [read]
  e21 Text Windows (CRLF) [read]
  e22 Text UTF-8 [read]
  e23 Tab [click]
    e24 List [scroll]
    e25 Button Add New Tab [click]
  e26 MenuItem File [click]
  e27 MenuItem Edit [click]
  e28 MenuItem View [click]
  e29 Button Headings [click]
  e30 Button Lists [click]
  e31 Button Bold (Ctrl+B) [click]
  e32 Button Italic (Ctrl+I) [click]
  e33 Button Strikethrough (Ctrl+Shift+X) [click]
  e34 Button Link (Ctrl+K) [click]
  e35 Button More options [click]
  e36 Button Writing tools [click]
  e37 Button What's new [click]
  e38 Button User avatar [click]
  e39 Button Settings [click]
  e40 MenuItem System [click]
  e41 Button Minimize [click]
  e42 Button Maximize [click]
  e43 Button Close [click]
W3 Window Task Manager
W4 Window YouTube - Google Chrome
W5 Window Window_33031036
  e44 Text Grok [read]
  e45 Text [read]
  e46 Text grok.com [read]
  e47 Text [read]
  e48 Text Memory usage: 228 MB [read]
  e49 Text [read]
W6 Window Grok - Google Chrome
  e50 TabItem Grok [click]
    e51 Button Close [click]
  e52 Button Minimize [click]
  e53 Button Maximize [click]
  e54 Button Close [click]
  e55 Button Back [click]
  e56 Button Forward
  e57 Button Reload [click]
  e58 Button View site information [click]
  e59 Edit Address and search bar [write]
  e60 Button Install Grok [click]
  e61 Button Edit bookmark for this tab [click]
  e62 Button You [click]
  e63 Button Chrome [click]
  e64 Document Grok [write]
    e65 Button Toggle sidebar [click]
    e66 Hyperlink Switch to Private Chat [click]
    e67 Edit Ask Grok anything [write]
      e68 Text Ask Grok [read]
    e69 Button Attach [click]
    e70 Button Model select [click]
    e71 Button Dictation (Ctrl+D) [click]
    e72 Button Enter voice mode (Ctrl+⇧O) [click]
  e73 Button Tab search [click]
  e74 Tab [click]
  e75 Button New Tab [click]
W7 Window ChatGPT
  e76 Button Running python -c "import sys;f=chr(96)*3;p=sys.argv[1];exec(open(p,encoding='utf8').read().split('## engine\n'+f+'python\n')[1].split('\n'+f)[0],{'BOARD':p,'ARGV':sys.argv[2:]})" "C:\Users\px-wjt\Downloads\endgame-ai\endgame.md" --reset [click]
  e77 Text , keyboard events, subprocess code, clipboard, or another generic route. [read]
  e78 Button Switch mode, current mode: Codex [click]
  e79 Button Search [click]
  e80 Button New chat [click]
  e81 Button Quick chat [click]
  e82 Button Pull requests [click]
  e83 Button Sites [click]
  e84 Button Scheduled [click]
  e85 Button Plugins [click]
  e86 Button Projects [click]
  e87 Button Project sidebar options [click]
  e88 Button Add new project [click]
  e89 List [scroll]
    e90 ListItem endgame-ai [click]
      e91 Button endgame-ai [click]
        e92 Button Start new chat in endgame-ai [click]
      e93 List Scheduled tasks in endgame-ai [scroll]
        e94 ListItem Fix desktop click coordinates [click]
          e95 Button Pin chat Archive chat [click]
            e96 Button Pin chat Archive chat [click]
              e97 Button Pin chat [click]
              e98 Button Archive chat [click]
        e99 ListItem Establish architecture workflow [click]
          e100 Button Pin chat Archive chat [click]
            e101 Button Pin chat Archive chat [click]
              e102 Button Pin chat [click]
              e103 Button Archive chat [click]
  e104 Button Chats [click]
  e105 Button Chat sidebar options [click]
  e106 Button New chat [click]
  e107 Text No chats [read]
  e108 Text Do anything [read]
  e109 Text Valid Campaign 2 is starting now with a fresh [read]
  e110 Button 3 files changed + 250 - 134 [click]
  e111 Text , leave it open and unsaved, and prove it from a fresh desktop observation.” [read]
  e112 Button Edited a file [click]
  e113 Text Do anything [read]
  e114 Button Show sidebar [click]
  e115 Button Back [click]
  e116 Button Forward
  e117 Button File [click]
  e118 Button Edit [click]
  e119 Button View [click]
  e120 Button Help [click]
  e121 Button [click]
  e122 Text Fix desktop click coordinates [read]
  e123 Button Chat actions [click]
  e124 Button Open in [click]
  e125 Button Secondary action [click]
  e126 Button Toggle summary [click]
  e127 Button Toggle side panel [click]
  e128 Button Edited files, ran commands [click]
  e129 Text but does not use it to validate or route the click. I’ll correct Campaign 1’s report accordingly and keep subsequent goals method-neutral. [read]
  e130 Text Do anything [read]
  e131 Text Do anything [read]
  e132 Button 5.6 Sol Ultra [click]
  e133 Text Do anything [read]
W8 Window Window_459498
W9 Window Window_590600
W10 Window Settings
W11 Window Settings
W12 Window Window_65942
W13 Window Program Manager
  e134 ListItem Recycle Bin [click]

## failure_streak
0

## developer_feedback
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"execute":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"recover":""}
{"execute":""}
{"verify":""}
{"execute":""}
