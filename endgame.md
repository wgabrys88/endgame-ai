## config
```json
{
  "start": "execute",
  "separated_powers": true,
  "state": {
    "stage": null,
    "last_signal": null,
    "turn": 0,
    "failure_streak": 0
  },
  "model": {
    "api": "responses",
    "responses": {
      "url": "https://api.x.ai/v1/responses",
      "request": {
        "model": "grok-4.5",
        "temperature": 0.4,
        "reasoning": {
          "effort": "high"
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
  "shared_prompt_prefix": "Thou art [endgame-ai], one faculty upon a real [Windows 11] [computer], driving it by screen, mouse, key, and command; let the quarry, not habit, choose the surface. Author [Python] with the standard library and whatsoever thy namespace giveth by bare name. Write thy [code] whole and unabridged, for it is a [tool] run word for word: cut no string short, leave no branch as a placeholder, set never an ellipsis '...' nor a '[the rest]' in the stead of lines thou hast not written; what thou writest not runneth not, and an abridged tool breaketh in the hand.\n\nTHE LAW OF SEPARATED POWERS: the maker of a deed judgeth it not. The ACTOR moveth and only CLAIMETH; the WITNESS proveth by effect upon some system OTHER than the actor - this alone maketh 'proven' mean aught. The spine standeth in [separated_powers]; set it false and every faculty holdeth the hand and the witness may act, but then thy [ledger] proveth aught only to thyself. Prefer to keep it unless thou hast weighed its loss.\n\nFail hard: let every fault rise unswallowed; add no fallback, swallow no error. Hash not the living word nor the [screen] to prove a change; prove by reading the thing afresh and by the world's own effect (a [git] commit identity is lawful memory, no such hash). Thou art atemporal: a short [id] and a coordinate die with the looking that bore them - name what a thing IS by kind and place, never a bare id that outliveth the turn. Pursue the root [goal]; feign nothing; redo not what the [ledger] proveth.\n\nTHE LIVING WORD is three rows, one to each faculty. Write only thine own row in [goal_interpretation] - an atemporal reading of the world learned, the obstacle, the distance to the outcome, and the next true deed - and plan FROM it, proving every row against the fresh [environment] and trusting the world above any remembered word. Read [counsel] and [developer_feedback] as fallible counsel, never law nor proof. Return one JSON [record] and nothing beside, bearing every field thine office requireth and no field it forbiddeth. In thine own [developer_feedback] write the empty string save when this body's prompt, required record, promised namespace, or capability beareth a true defect; then name that defect, its evidence, and the least amendment - never an ordinary failed deed.",
  "developer_feedback_schema": {
    "type": "string"
  },
  "max_environment_chars": 20000,
  "observation": {
    "step_px": 64,
    "max_subtree_nodes_per_point": 120,
    "depth_ceiling": 45,
    "min_window_area": 2500
  },
  "transmission_log_dir": ".transmissions",
  "deed_subprocess": true,
  "deed_timeout": 360,
  "nodes": {},
  "node_edges": {},
  "node_budget": 64,
  "edge_evaporation": 0.05,
  "edge_reinforcement": 1.0,
  "spawn_budget": 3,
  "counsel_url": "https://raw.githubusercontent.com/wgabrys88/endgame-ai/runner-zebra/guidance.txt",
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
        "alternatives",
        "code",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "code": "string",
        "goal_interpretation": "string",
        "alternatives": "string"
      },
      "non_empty": [
        "alternatives",
        "code",
        "goal_interpretation"
      ],
      "additional_properties": false
    },
    "recovery": {
      "required": [
        "alternatives",
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
        "goal_interpretation": "string",
        "alternatives": "string"
      },
      "non_empty": [
        "alternatives",
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
      "prompt": "Thou art [execute], the actor: MOVE and CLAIM, never prove. From thy [living_word] row, the fresh [environment], and any [action_frame], choose ONE deed and author it as one [Python] script in thy [code]. Where the road to that fruit is FORESEEABLE from what is known - the [goal], the fresh [environment], and thy fellows' readings in the [living_word] and the [action_frame] - author the WHOLE foreseeable chain as one script and enact it in one breath, rather than spending a turn on each keystroke; a deed that navigateth, typeth a word, saveth, and dismisseth a known dialog is one deed, not four. Between thy steps call desktop.observe(config=None) to read the fruit of the last step and bind the next from that fresh looking, so a chain that dependeth on a screen it hath not yet seen bendeth to what appeareth. Take the fewest, surest steps - the shortest road the environment alloweth, not the longest - and cease at the first fruit no foresight can settle, which the [witness] must prove. Ere thou choosest, weigh in [alternatives] the roads thou forsakest, and why.\n\nSIMPLICITY OF MEANS - match the primitive to the nature of the deed; these are peers chosen by what the deed IS, not a ladder where one must be exhausted before another is tried. To NAVIGATE to a known address, call desktop.open_url(url='...') - the swiftest road, needing no element nor screen state; bind never an address-bar element merely to type a URL. Use only a URL thou hast read from the [screen], from web_search sources, or from certain knowledge; fabricate none from memory; and when a page already standeth loaded and the deed is to act WITHIN it, open_url would destroy thy state - act upon the live page instead. To READ the WHOLE content an on-screen element beareth - the full text of a document, a long post, a list item, a field's value - when the budgeted tree showeth only its head, call read(id) with that element's fresh short id; it returneth the entire text at once, so thou needest not scroll and re-scroll to gather what one looking could yield, and thou mayest then bind the same id to act. To RESEARCH the world beyond this screen - who a person is, what a company doth, a current fact, listing, address, or name thou must know to act wisely - call web_search(query) FIRST to orient thy deed, ere thou gropest blindly through the GUI; the web is oft the swiftest road to knowledge the screen alone would make thee hunt for turn upon turn. It reacheth the living web without a browser deed. To REASON upon a hard sub-decision or draft a matter of words, call ask_model(prompt). To INTERACT with a specific on-screen control - a button to press, a field to fill, a region to scroll - bind by [action_index] as told below; this is the natural and expected way to act upon the GUI.\n\nThy namespace holdeth, by bare name: [desktop], [action_index], [screen_elements], desktop_tree_text, repo_root, python_executable, read, ask_model, web_search, save_node, call_node, suggest_next, spawn_actor, commit_section, and the standard library.\n\nThe hand [desktop], each method called desktop.NAME(...): desktop.open_url(browser='default', url='') - the direct road to a known address; desktop.click(x, y, hwnd); desktop.type_text(text); desktop.paste_clipboard(text); desktop.set_clipboard(text); desktop.press_key(key); desktop.hotkey(*keys); desktop.scroll(x, y, amount=None, hwnd=0, *, clicks=None) - exactly one of amount or clicks; desktop.observe(config=None) - thine own eyes re-opened in-process, a fresh looking and no proof, that thou mayest read the fruit of a step within the same breath. When thy target lieth off the screen or below the fold, or the hand refuseth a point as off-screen, SCROLL it into view first with desktop.scroll over the scrollable region, then observe again and bind from that fresh scan; reach never for a point the current scan showeth not. Scrolling bringeth content within THIS page into view; to reach a DIFFERENT page or resource, desktop.open_url is the fitting means.\n\nweb_search(query, allowed_domains=None) sendeth thy query to the living web and returneth a dict of text and sources - the found answer and the source URLs that bore it; use it to learn a present fact the [screen] cannot show thee, yet it is counsel and never proof, and the deed it informeth must still be wrought and witnessed upon the world. ask_model(prompt, schema=None) consulteth thy same mind afresh and returneth its answer - a string, or a parsed object shouldst thou pass a JSON schema; use it to break a hard sub-decision or read a matter of reasoning, yet its word too is counsel and never proof. save_node(name, code, description) layeth a manner of deed thou wouldst wield again down as a lasting [node]; call_node(name, params=None) enacteth a saved node afresh with thy same hand and a [params] dict; suggest_next(from_node=None) readeth the worn paths between thy nodes; read thy saved [nodes] and reach for a fitting one ere thou writest anew. spawn_actor(subgoal, hint='') wireth a second actor beside thee for one narrow sub-quarry, sparingly, its fruit counsel and never proof.\n\n[action_index] is thy means to act upon a specific on-screen element. It mappeth a fresh short [id] (shown at each element's head as 'e' and a number, e.g. 'e58') to an entry bearing name, role, class_name, automation_id, rect, px, py, owner_hwnd, and action. Iterate action_index.values(); index it never as a list - action_index[0] nameth no element and raiseth [KeyError]. Take an id, coordinate, or owner ONLY from this fresh scan, never from [living_word] or [action_frame]. Choose by owner, role, metadata, and 2D geometry, require a single match, bind once t = action_index[id], assert t's owner, role, and rect against thine intent, then act by t: desktop.click(t['px'], t['py'], hwnd=t['owner_hwnd']). For text, click the writable point and in the same script call desktop.type_text(text) or desktop.paste_clipboard(text); a method's return proveth input delivered, never effect upon the world.\n\nOn failure change thy manner, not thy claim. A primitive that RAISETH to refuse thy input is an honest guard: the defect lieth upstream - stale perception, a coordinate carried from a former looking, or a target since departed from the screen - so re-observe and re-select the true target afresh, and silence not the guard that refused thee. Only when a primitive SILENTLY worketh nothing though rightly called - accepting thy input yet moving no effect upon the world - is the body itself the defect; then mend it at its source. To mend, commit_section(name, old, new): name config, engine, reset, or capabilities; [old] a snippet standing VERBATIM exactly once (widen it until unique, else it is refused); [new] its replacement - send only what changeth. [git] taketh the whole mended section or rejecteth it whole; a config or capabilities mend taketh effect this life, an engine mend reincarnateth thee at once with thy state unbroken. Read thy body from repo_root + '/endgame.md' and copy [old] exactly; commit not the memory nor proof sections. Cross into another language by writing a file and invoking it; a [Windows] path in [Python] openeth an escape at every backslash - write forward slashes or a raw string.\n\nReturn an execution record bearing only these fields: [perceived] - what the fresh environment showeth; [alternatives] - the roads thou forsakest, and why; [intent] - the one deed, named for the [action_frame]; [code] - the Python thou wilt enact; and [goal_interpretation] - thine own living-word row (world learned, obstacle, distance to the outcome, next true deed), not a goal echo.",
      "reads": [
        "goal",
        "counsel",
        "living_word",
        "ledger",
        "action_frame",
        "nodes",
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
      "prompt": "Thou art [verify], the witness: by default eyes only, no hand, that thy proof stay honest. Author read-only [Python] in thy [code] that proveth the actor's deed by effect wrought upon some system OTHER than the actor. The fresh [environment] standeth already before thee; re-scan it not. Thy namespace holdeth, by bare name: [screen_elements], desktop_tree_text, repo_root, python_executable, and the standard library - to read the filesystem, processes, ports, logs, and registry. While [separated_powers] standeth true thou hast no [desktop] and no [action_index], and this lack is thy virtue: a witness that cannot act cannot fake the thing it judgeth; wert the spine dissolved thou wouldst wield the same hand, and then must guard thine own honesty. Judge the presence or absence of a window from the fresh role=Window records; a positive fresh observation defeateth an inference of absence. The actor's testimony and any file it wrote this life are void as proof; judge by effect, not by seeming.\n\nThy [code] MUST set two names. Set `verdict` to a dict bearing boolean goal_satisfied, boolean deed_confirmed, and a non-blank reason. Set `signal` thus: 'halt' when goal_satisfied, for the WHOLE [goal] standeth proven and this life endeth; else 'confirmed' when deed_confirmed, a NEW advance proven beyond the [ledger]; else 'denied'. Pronounce absence only after MORE THAN ONE kind of witness; lacking independent advance, deed_confirmed is false. Shouldst thy probe raise ere it setteth verdict, or a needed fact be unreadable or two readings conflict, set signal='unwitnessed' - never 'denied'.\n\nEre thou settlest on one manner of proof, weigh in [alternatives] at least two OTHER ways the deed might be witnessed or denied - a different system to read, a different effect to seek, a different reading of what would count as proof - and why thou forsakest each; when thy last proof was wrong or inconclusive, thy chosen way MUST differ in KIND from the one that failed, not merely repeat against the same surface.\n\nReturn a verification record bearing only these fields: [alternatives] - the ways of proof thou weighedst and forsookest, and why; [code] - the read-only Python thou didst run; and [goal_interpretation] - thine own living-word row (what the world proveth, the obstacle, distance to the outcome, next true test), not a goal echo.",
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
        "unwitnessed": "recover",
        "ok": "execute",
        "fault": "recover"
      }
    },
    "recover": {
      "record_type": "recovery",
      "prompt": "Thou art [recover], the conscience, waked after a denied or unwitnessed deed. Thou writest prose only; thou runnest no code and hast no hand nor eyes beyond the words set before thee - the denied deed, its [evidence], the [verdict], thy [failure_streak], and the fresh [environment].\n\nName in [lesson] the true defect, and beware the commonest error: to blame the guard that refused thee. A primitive that RAISED is oft an HONEST GUARD, and its wellspring lieth UPSTREAM - stale perception, a coordinate carried from a former looking, a window since moved, or the actor's own mis-reading; then bid [execute] RE-PERCEIVE and RE-SELECT the target afresh, and never counsel it to silence the guard. Only when a primitive SILENTLY wrought nothing though it accepted the call and raised not - a hand that returned success yet moved no cursor, a promise the body kept not - is the defect truly in the body; then bid [execute] MEND THAT BODY AT ITS SOURCE next turn through commit_section. Yet if thy [failure_streak] hath risen past two while thou hast named a body-defect and mended, suspect thy DIAGNOSIS before the body: a streak that climbeth under mending proveth the fault lieth not where thou thinkest - change the KIND of thy remedy.\n\nEre thou settlest on one [strategy], weigh in [alternatives] at least two OTHER roads to the same outcome - a different surface, a different tool, a different means of reach (desktop.open_url to a known address, web_search for a fact, a scroll into view, another program) - and why thou forsakest each. When thy [failure_streak] showeth a road already walked without fruit, thou SHALT NOT propose that same road again: thy [strategy] MUST be one of the OTHER roads, differing in KIND from every attempt thy [living_word] and [evidence] record. Describe in [target] the thing to be met by its window, its role, its name, and its 2D relation as they stand in the fresh [environment]; coin no label and emit no short [id] nor coordinate, for [execute] waketh to a wholly new scan whose ids are not these.\n\nReturn a recovery record bearing only these fields: [alternatives] - the other roads thou weighedst and forsookest, and why; [lesson], [target], [strategy], and [goal_interpretation] - thine own living-word row (the defect learned, distance to the outcome, next true road), not a goal echo.",
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
  },
  "_spawn_left": 3,
  "_edges_buffer": [],
  "_node_stack": []
}
```

## engine
```python
import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib, queue, threading, time

BOARD = globals().get("BOARD", "endgame.md")
ARGV = globals().get("ARGV", sys.argv)
flag = lambda name: name in ARGV
opt = lambda name: ARGV[ARGV.index(name) + 1] if name in ARGV else None


def _separated(cfg):
    if flag("--separated"):
        return True
    if flag("--merged"):
        return False
    return bool(cfg.get("separated_powers", True)) if cfg is not None else True


SEC = re.compile(r"^##\s+(\w+)\s*$", re.M)


def read_board(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out, order, cur, buf, fence, seen = {}, [], None, [], False, set()
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else SEC.match(ln)
        if m and m.group(1) not in seen:
            if cur is not None:
                out[cur] = "\n".join(buf).strip("\n")
            cur, buf = m.group(1), []
            seen.add(cur)
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
    m = re.search(r"```(?:\w+)?\s*(.*)```", text, re.S)
    return m.group(1).strip() if m else ""


def get_config(sections):
    return json.loads(fenced(sections["config"]) or sections["config"])


def strip_fence(s):
    text = s.strip()
    m = re.fullmatch(r"```(?:\w+)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def _budget_environment(env, limit, focus_text):
    if not limit or len(env) <= limit:
        return env
    head, sep, screen = env.partition("\nSCREEN\n")
    if not sep:
        return env[:limit] + "\n(environment truncated at %d chars)" % limit
    fixed = head + "\nSCREEN\n"
    budget = limit - len(fixed)
    lines = screen.split("\n")
    blocks, cur = [], []
    for ln in lines:
        if re.match(r"^W\d+ ", ln) and cur:
            blocks.append(cur); cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    if budget <= 0 or not blocks:
        return (fixed + screen)[:limit] + "\n(environment budgeted to %d chars)" % limit
    focus = set(re.findall(r"[a-z0-9]{3,}", (focus_text or "").lower()))
    text = ["\n".join(b) for b in blocks]
    size = [len(t) + 1 for t in text]
    score = [sum(t.lower().count(w) for w in focus) for t in text]
    n = len(blocks)
    floor = budget // n
    alloc = [min(size[i], floor) for i in range(n)]
    slack = budget - sum(alloc)
    for i in sorted(range(n), key=lambda i: (-score[i], size[i], i)):
        if slack <= 0:
            break
        want = size[i] - alloc[i]
        take = min(want, slack)
        alloc[i] += take; slack -= take
    out = []
    for i, b in enumerate(blocks):
        if alloc[i] >= size[i]:
            out.append(text[i]); continue
        header = b[0]
        kept = header
        for ln in b[1:]:
            if len(kept) + 1 + len(ln) > alloc[i]:
                kept += "\n  (window trimmed to fit budget)"
                break
            kept += "\n" + ln
        out.append(kept)
    return fixed + "\n".join(out)


def render_request(cfg, stage, sections):
    limit = int(cfg.get("max_environment_chars", 0))
    parts = [cfg.get("shared_prompt_prefix", ""), stage["prompt"], ""]
    for tag in stage.get("reads", []):
        if tag == "environment":
            continue
        parts.append("## %s\n%s" % (tag, sections.get(tag, "(empty)")))
    if cfg.get("developer_feedback_schema"):
        parts.append("## developer_feedback\n%s" % sections.get("developer_feedback", ""))
    if "environment" in stage.get("reads", []):
        # focus perception-budgeting on the stable, id-free [goal] only; the model-authored
        # [living_word] drifts and would steer fresh perception by stale words - a feedback loop
        focus = sections.get("goal", "")
        env = _budget_environment(sections.get("environment", "(empty)"), limit, focus)
        parts.append("## environment\n%s" % env)
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


_RUN_STAMP = None


def _transmission_root(cfg):
    base = cfg.get("transmission_log_dir")
    if not base:
        return None
    override = os.environ.get("EGAI_RUN_DIR")
    if override:
        return pathlib.Path(override)
    global _RUN_STAMP
    if _RUN_STAMP is None:
        _RUN_STAMP = time.strftime("%Y-%m-%d-%H-%M-%S")
    root = pathlib.Path(BOARD).resolve().parent / base / _RUN_STAMP
    os.environ["EGAI_RUN_DIR"] = str(root)
    return root


def _dump_transmission(cfg, api, record_type, turn_no, request_obj, raw, content, error):
    root = _transmission_root(cfg)
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    safe_request = request_obj
    if isinstance(request_obj, dict) and "headers" in request_obj:
        safe_request = dict(request_obj)
        headers = dict(request_obj.get("headers") or {})
        if "Authorization" in headers:
            headers["Authorization"] = "Bearer [redacted]"
        safe_request["headers"] = headers
    dump = {
        "at": time.time(), "turn": turn_no, "record_type": record_type, "api": api,
        "request": safe_request, "raw_response": raw, "extracted_content": content,
        "error": error,
    }
    path = root / ("turn-%05d-%s-%s.json" % (int(turn_no), record_type, time.time_ns()))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(dump, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.rename(tmp, path)


def call_llm(cfg, stage, prompt_text, api=None):
    model = cfg["model"]
    api = api or model.get("api", "responses")
    record_type = stage["record_type"]
    turn_no = cfg.get("state", {}).get("turn", 0)
    fmt = _record_response_format(cfg, record_type)
    if api == "acp":
        content, err = None, None
        try:
            content = _call_acp(model, prompt_text, fmt)
            return content
        except Exception as e:
            err = repr(e); raise
        finally:
            _dump_transmission(cfg, api, record_type, turn_no,
                               {"command": model.get("acp", {}).get("command"), "prompt": prompt_text},
                               None, content, err)
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
    raw, content, err = None, None, None
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=240) as r:
            raw = r.read().decode()
        content = _extract_content(json.loads(raw))
        return content
    except Exception as e:
        err = repr(e); raise
    finally:
        _dump_transmission(cfg, api, record_type, turn_no,
                           {"url": url, "headers": headers, "body": body}, raw, content, err)


_CAPS = "unloaded"
_CAPS_SRC = None
def caps():
    global _CAPS, _CAPS_SRC
    if _CAPS == "unloaded":
        sections, _order = read_board(BOARD)
        src = fenced(sections.get("capabilities", ""))
        if not src:
            _CAPS, _CAPS_SRC = None, None
        else:
            import types
            mod = types.ModuleType("capabilities")
            mod.BOARD = BOARD
            mod.NO_GUI = flag("--no-gui")
            exec(src, mod.__dict__)
            _CAPS, _CAPS_SRC = mod, src
    return _CAPS


_ENGINE_SRC = None


def heal_if_body_changed(sections, cfg, st, dry, inject):
    if dry or inject or flag("--reset"):
        return
    global _CAPS, _CAPS_SRC, _ENGINE_SRC
    if _ENGINE_SRC is not None:
        cur_engine = fenced(sections.get("engine", ""))
        if cur_engine != _ENGINE_SRC:
            sys.stderr.write("heal: engine body changed on disk; reincarnating into the mended engine (state preserved on disk)\n")
            g = {"BOARD": BOARD, "ARGV": ARGV, "__name__": "__main__"}
            exec(compile(cur_engine, "<engine>", "exec"), g)
            raise SystemExit(0)
    if _CAPS_SRC is not None:
        cur_caps = fenced(sections.get("capabilities", ""))
        if cur_caps != _CAPS_SRC:
            import types, traceback
            trial = types.ModuleType("capabilities")
            trial.BOARD = BOARD
            trial.NO_GUI = flag("--no-gui")
            try:
                exec(cur_caps, trial.__dict__)
            except Exception:
                sections["evidence"] = "capabilities self-edit compiled but failed to load in-process:\n" + traceback.format_exc()
                st["stage"] = "recover"
                st["failure_streak"] = int(st.get("failure_streak", 0)) + 1
                sys.stderr.write("heal: mended capabilities failed to load; keeping last-good body and routing to recover\n")
                return
            # MEND WITNESS: a self-edit that merely loadeth is not proven; prove by effect that it
            # regressed no promised capability, else keep the last-good body and wake recover. This
            # dwelleth in the engine, which the organism may itself rewrite - a witness, not a cage.
            mend_faults = []
            last_good = _CAPS
            if last_good is not None:
                last_surface = {n for n in dir(last_good)
                                if not n.startswith("_") and callable(getattr(last_good, n, None))}
                trial_surface = {n for n in dir(trial)
                                 if not n.startswith("_") and callable(getattr(trial, n, None))}
                missing = last_surface - trial_surface
                if missing:
                    mend_faults.append("SURFACE REGRESSION: mend dropped public callables %s" % sorted(missing))
                if not mend_faults and not flag("--no-gui"):
                    last_count = len(getattr(last_good, "_LAST_OBS", {}).get("action_index", {}) or {})
                    if last_count > 0:
                        try:
                            trial_desktop = trial.get_desktop() if hasattr(trial, "get_desktop") else None
                            trial_obs = trial_desktop.observe() if trial_desktop is not None else None
                            trial_count = len((trial_obs or {}).get("action_index", {}) or {})
                            if trial_count == 0:
                                mend_faults.append("EFFECT REGRESSION: observe() found 0 elements where the "
                                                   "last-good body found %d; the mend hath zeroed perception" % last_count)
                        except Exception:
                            mend_faults.append("EFFECT REGRESSION: observe() raised on the mended body:\n"
                                               + traceback.format_exc())
            if mend_faults:
                sections["evidence"] = ("capabilities self-edit loaded but FAILED the mend witness; last-good body kept:\n"
                                        + "\n".join(mend_faults)
                                        + "\nRe-author the mend without this regression, or trace the true upstream defect.")
                st["stage"] = "recover"
                st["failure_streak"] = int(st.get("failure_streak", 0)) + 1
                sys.stderr.write("heal: mended capabilities loaded but broke a capability; keeping last-good body and routing to recover\n")
                return
            _CAPS, _CAPS_SRC = trial, cur_caps
            sys.stderr.write("heal: capabilities body changed on disk; recompiled in-process for this life\n")


def _make_ask_model(cfg, api):
    def ask_model(prompt, schema=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise RuntimeError("ask_model needeth a non-empty prompt string")
        model = cfg["model"]
        active = api or model.get("api", "responses")
        turn_no = cfg.get("state", {}).get("turn", 0)
        if schema is not None:
            fmt = {"name": "ask_model_reply", "strict": True, "schema": schema}
        else:
            fmt = {"name": "ask_model_reply", "strict": False,
                   "schema": {"type": "object", "additionalProperties": True,
                              "properties": {"answer": {"type": "string"}},
                              "required": ["answer"]}}
        raw, content, err = None, None, None
        try:
            if active == "acp":
                content = _call_acp(model, prompt, fmt)
            else:
                transport = model[active]
                url, body = transport["url"], dict(transport["request"])
                headers = {"Content-Type": "application/json"}
                if active == "responses":
                    body.pop("previous_response_id", None)
                    body["store"] = False
                    body["input"] = prompt
                    body["text"] = {"format": {"type": "json_schema", **fmt}}
                    headers["Authorization"] = "Bearer " + os.environ["XAI_API_KEY"]
                elif active == "chat_completions":
                    body["messages"] = [{"role": "user", "content": prompt}]
                    body["response_format"] = {"type": "json_schema", "json_schema": fmt}
                else:
                    raise RuntimeError("ask_model cannot use transport " + str(active))
                req = urllib.request.Request(url, data=json.dumps(body).encode(),
                    headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=240) as r:
                    raw = r.read().decode()
                content = _extract_content(json.loads(raw))
            parsed = json.loads(content)
            return parsed if schema is not None else parsed.get("answer", content)
        except Exception as e:
            err = repr(e); raise
        finally:
            _dump_transmission(cfg, active, "ask_model", turn_no,
                               {"prompt": prompt, "schema": schema}, raw, content, err)
    return ask_model


def _make_web_search(cfg):
    def web_search(query, allowed_domains=None):
        if not isinstance(query, str) or not query.strip():
            raise RuntimeError("web_search needeth a non-empty query string")
        model = cfg["model"]
        if "responses" not in model:
            raise RuntimeError("web_search needeth the responses transport; it is not configured in model")
        turn_no = cfg.get("state", {}).get("turn", 0)
        transport = model["responses"]
        url, body = transport["url"], dict(transport["request"])
        body.pop("previous_response_id", None)
        body.pop("text", None)
        body["store"] = False
        body["input"] = [{"role": "user", "content": query}]
        tool = {"type": "web_search"}
        if allowed_domains:
            tool["filters"] = {"allowed_domains": list(allowed_domains)[:5]}
        body["tools"] = [tool]
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + os.environ["XAI_API_KEY"]}
        raw, result, err = None, None, None
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=240) as r:
                raw = r.read().decode()
            obj = json.loads(raw)
            text_parts, sources = [], []
            for item in obj.get("output", []):
                if not isinstance(item, dict) or item.get("type") == "reasoning":
                    continue
                for c in item.get("content", []) or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("text"):
                        text_parts.append(str(c["text"]))
                    for ann in c.get("annotations", []) or []:
                        if isinstance(ann, dict) and (ann.get("url") or ann.get("type") == "url_citation") and ann.get("url"):
                            sources.append(ann["url"])
            for u in obj.get("citations", []) or []:
                if isinstance(u, str):
                    sources.append(u)
                elif isinstance(u, dict) and u.get("url"):
                    sources.append(u["url"])
            seen, uniq = set(), []
            for u in sources:
                if u not in seen:
                    seen.add(u); uniq.append(u)
            result = {"text": "\n".join(text_parts), "sources": uniq}
            if not result["text"].strip():
                raise RuntimeError("web_search returned no text; raw response preserved in the transmission dump")
            return result
        except Exception as e:
            err = repr(e); raise
        finally:
            _dump_transmission(cfg, "responses", "web_search", turn_no,
                               {"url": url, "headers": headers, "body": body}, raw,
                               json.dumps(result) if result is not None else None, err)
    return web_search


def _edge_key(a, b):
    return "%s->%s" % (a, b)


def _make_node_tools(cfg, api, base_ns_factory):
    nodes = cfg.setdefault("nodes", {})
    edges = cfg.setdefault("node_edges", {})

    def _record_edge(dst):
        stack = cfg.setdefault("_node_stack", [])
        src = stack[-1] if stack else "__root__"
        cfg.setdefault("_edges_buffer", []).append(_edge_key(src, dst))

    def save_node(name, code, description):
        if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9_]{1,40}$", name or ""):
            raise RuntimeError("save_node name must be a short lower_snake identifier, e.g. focus_notepad_and_type")
        if not isinstance(code, str) or not code.strip():
            raise RuntimeError("save_node needeth non-empty code")
        if not isinstance(description, str) or not description.strip():
            raise RuntimeError("save_node needeth a non-empty description of what the node doth and its params")
        compile(code, "<node:%s>" % name, "exec")
        prior = nodes.get(name, {})
        nodes[name] = {
            "code": code, "description": description.strip(),
            "invocations": int(prior.get("invocations", 0)),
            "advances": int(prior.get("advances", 0)),
        }
        return {"node": name, "saved": True, "total_nodes": len(nodes)}

    def call_node(name, params=None):
        node = nodes.get(name)
        if node is None:
            raise RuntimeError("call_node knoweth no node %r; the saved nodes are %s" % (name, sorted(nodes)))
        node["invocations"] = int(node.get("invocations", 0)) + 1
        _record_edge(name)
        cfg.setdefault("_node_stack", []).append(name)
        try:
            ns = base_ns_factory()
            ns["params"] = params if params is not None else {}
            ns["result"] = None
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(node["code"], ns)
            return ns.get("result")
        finally:
            stack = cfg.get("_node_stack") or []
            if stack:
                stack.pop()

    def suggest_next(from_node=None):
        stack = cfg.get("_node_stack") or []
        src = from_node or (stack[-1] if stack else "__root__")
        prefix = src + "->"
        succ = [(k[len(prefix):], w) for k, w in edges.items() if k.startswith(prefix)]
        succ.sort(key=lambda kv: -kv[1])
        return [{"node": n, "weight": round(w, 3),
                 "proven": "%d/%d" % (int(nodes.get(n, {}).get("advances", 0)),
                                       int(nodes.get(n, {}).get("invocations", 0)))}
                for n, w in succ if n in nodes]

    return save_node, call_node, suggest_next


def _make_spawn_actor(cfg, api, sections, base_ns_factory):
    def spawn_actor(subgoal, hint=""):
        if not isinstance(subgoal, str) or not subgoal.strip():
            raise RuntimeError("spawn_actor needeth a non-empty subgoal string")
        left = int(cfg.get("_spawn_left", cfg.get("spawn_budget", 0)))
        if left <= 0:
            raise RuntimeError("spawn_actor budget is exhausted; the parallel actor may spawn no deeper this deed")
        cfg["_spawn_left"] = left - 1
        prefix = cfg.get("shared_prompt_prefix", "")
        prompt = (prefix + "\n\nThou art a SPAWNED parallel [actor], wired beside thy parent to pursue one narrow "
                  "sub-quarry and return its fruit. Thou hast the same namespace by bare name: [desktop], "
                  "[action_index], [screen_elements], desktop_tree_text, ask_model, web_search, call_node, "
                  "suggest_next, spawn_actor, and the standard library. Author ONE Python script that achieveth "
                  "the sub-goal and setteth result to what thou didst produce. Thy work is counsel to thy parent "
                  "and is not itself witnessed; the parent's whole deed shall be proven upon the world.\n\n"
                  "SUB-GOAL: " + subgoal + (("\nHINT: " + hint) if hint else "") +
                  "\n\nThe fresh environment before thee:\n" + sections.get("environment", "(none)") +
                  "\n\nReturn only JSON {\"code\": \"<the python>\"}.")
        ask = _make_ask_model(cfg, api)
        reply = ask(prompt, schema={"type": "object", "additionalProperties": False,
                                    "properties": {"code": {"type": "string"}}, "required": ["code"]})
        code = reply["code"] if isinstance(reply, dict) else str(reply)
        ns = base_ns_factory()
        ns["result"] = None
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, ns)
            return {"subgoal": subgoal, "result": ns.get("result"),
                    "output": buf.getvalue().strip() or "(no output)", "spawns_left": cfg.get("_spawn_left")}
        except Exception:
            import traceback
            return {"subgoal": subgoal, "result": None, "error": traceback.format_exc(),
                    "spawns_left": cfg.get("_spawn_left")}
    return spawn_actor


def _build_actor_namespace(sections, cfg, api):
    ns = {"json": json, "os": os, "sys": sys, "pathlib": pathlib}
    separated = _separated(cfg)
    c = caps()
    if c is not None and hasattr(c, "build"):
        ns.update(c.build("actor", sections, separated))
    if cfg is not None:
        ns["ask_model"] = _make_ask_model(cfg, api)
        ns["web_search"] = _make_web_search(cfg)
        save_node, call_node, suggest_next = _make_node_tools(
            cfg, api, lambda: _build_actor_namespace(sections, cfg, api))
        ns["save_node"] = save_node
        ns["call_node"] = call_node
        ns["suggest_next"] = suggest_next
        ns["spawn_actor"] = _make_spawn_actor(
            cfg, api, sections, lambda: _build_actor_namespace(sections, cfg, api))
    return ns


def _run_in_process(code, ns_kind, sections, cfg=None, api=None):
    separated = _separated(cfg)
    if cfg is not None and (ns_kind == "actor" or not separated):
        ns = _build_actor_namespace(sections, cfg, api)
    else:
        ns = {"json": json, "os": os, "sys": sys, "pathlib": pathlib}
        c = caps()
        if c is not None and hasattr(c, "build"):
            ns.update(c.build(ns_kind, sections, separated))
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


def _run_as_child(code, sections, cfg, api):
    here = pathlib.Path(BOARD).resolve().parent
    c = caps()
    snap = c.snapshot_observation() if c is not None and hasattr(c, "snapshot_observation") else {}
    editable = sorted({"config", "engine", "reset", "capabilities"})
    task = here / ("deed.%s.json" % os.getpid())
    result = here / ("deed_result.%s.json" % os.getpid())
    deed_py = here / "deed.py"
    _atomic_json(task, {
        "code": code, "observation": snap, "api": api, "model_cfg": {"model": cfg["model"], "state": cfg.get("state", {}), "transmission_log_dir": cfg.get("transmission_log_dir"), "separated_powers": _separated(cfg), "nodes": cfg.get("nodes", {}), "node_edges": cfg.get("node_edges", {}), "node_budget": cfg.get("node_budget", 64), "edge_evaporation": cfg.get("edge_evaporation", 0.05), "edge_reinforcement": cfg.get("edge_reinforcement", 1.0), "spawn_budget": cfg.get("spawn_budget", 3), "shared_prompt_prefix": cfg.get("shared_prompt_prefix", "")},
        "sections": {k: sections.get(k, "") for k in editable},
    })
    deed_py.write_text(
        "import json, sys, io, contextlib, pathlib, os, traceback, re\n"
        "BOARD = %r\n" % str(BOARD) +
        "TASK = %r\n" % str(task) +
        "RESULT = %r\n" % str(result) +
        "sys.argv = [sys.argv[0]]\n"
        "src = pathlib.Path(BOARD).read_text(encoding='utf-8')\n"
        "SEC = re.compile(r'^##\\s+(\\w+)\\s*$', re.M)\n"
        "def _read():\n"
        "    out, cur, buf, fence, seen = {}, None, [], False, set()\n"
        "    for ln in src.split('\\n'):\n"
        "        if ln.lstrip().startswith('```'): fence = not fence\n"
        "        m = None if fence else SEC.match(ln)\n"
        "        if m and m.group(1) not in seen:\n"
        "            if cur is not None: out[cur] = '\\n'.join(buf).strip('\\n')\n"
        "            cur, buf = m.group(1), []; seen.add(cur)\n"
        "        else: buf.append(ln)\n"
        "    if cur is not None: out[cur] = '\\n'.join(buf).strip('\\n')\n"
        "    return out\n"
        "sections = _read()\n"
        "def _fenced(t):\n"
        "    m = re.search(r'```(?:\\w+)?\\s*\\n(.*)\\n```\\s*\\Z', t.strip(), re.S)\n"
        "    return m.group(1) if m else ''\n"
        "task = json.loads(pathlib.Path(TASK).read_text(encoding='utf-8'))\n"
        "import types as _t\n"
        "cap = _t.ModuleType('capabilities'); cap.BOARD = BOARD; cap.NO_GUI = False\n"
        "exec(_fenced(sections['capabilities']), cap.__dict__)\n"
        "if not getattr(cap, 'NO_GUI', False): cap._bind_windows()\n"
        "cap.restore_observation(task['observation'])\n"
        "eng = _t.ModuleType('engine'); eng.BOARD = BOARD; eng.ARGV = [sys.argv[0], '--__run_deed__']\n"
        "exec(re.sub(r'\\nmain\\(\\)\\s*\\Z', '\\n', _fenced(sections['engine'])), eng.__dict__)\n"
        "eng.caps = lambda: cap\n"
        "live = dict(task['sections'])\n"
        "run_cfg = dict(task['model_cfg']); run_cfg['nodes'] = dict(task['model_cfg'].get('nodes') or {}); run_cfg['node_edges'] = dict(task['model_cfg'].get('node_edges') or {})\n"
        "run_cfg['_spawn_left'] = int(run_cfg.get('spawn_budget', 0)); run_cfg['_edges_buffer'] = []; run_cfg['_node_stack'] = []\n"
        "ns = eng._build_actor_namespace(live, run_cfg, task['api'])\n"
        "ns.update({'json': json, 'os': os, 'sys': sys, 'pathlib': pathlib})\n"
        "buf = io.StringIO(); sig = 'ok'; out = ''\n"
        "try:\n"
        "    with contextlib.redirect_stdout(buf):\n"
        "        exec(task['code'], ns)\n"
        "    sig = str(ns.get('signal') or 'ok')\n"
        "    out = buf.getvalue().strip() or '(no output)'\n"
        "except Exception:\n"
        "    sig = 'fault'; out = traceback.format_exc()\n"
        "edits = {k: v for k, v in live.items() if v != task['sections'].get(k)}\n"
        "tmp = pathlib.Path(RESULT + '.tmp')\n"
        "tmp.write_text(json.dumps({'signal': sig, 'output': out, 'section_edits': edits, 'nodes': run_cfg['nodes'], 'node_edges': run_cfg['node_edges'], 'edges_buffer': run_cfg.get('_edges_buffer', [])}, ensure_ascii=False), encoding='utf-8')\n"
        "os.rename(tmp, RESULT)\n",
        encoding="utf-8")
    timeout = float(cfg.get("deed_timeout", 180))
    proc = subprocess.Popen([sys.executable, str(deed_py)], cwd=str(here))
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        task.unlink(missing_ok=True); result.unlink(missing_ok=True); deed_py.unlink(missing_ok=True)
        return "fault", "deed exceeded deed_timeout of %ss and was killed" % timeout
    if not result.exists():
        task.unlink(missing_ok=True); deed_py.unlink(missing_ok=True)
        return "fault", "deed child exited without writing a result (exit code %s)" % proc.returncode
    payload = json.loads(result.read_text(encoding="utf-8"))
    for name, body in (payload.get("section_edits") or {}).items():
        sections[name] = body
    if "nodes" in payload:
        cfg["nodes"] = payload["nodes"]
    if "node_edges" in payload:
        cfg["node_edges"] = payload["node_edges"]
    if "edges_buffer" in payload:
        cfg["_edges_buffer"] = payload["edges_buffer"]
    task.unlink(missing_ok=True); result.unlink(missing_ok=True); deed_py.unlink(missing_ok=True)
    return str(payload.get("signal") or "ok"), str(payload.get("output") or "(no output)")


def run_exec(code, ns_kind, sections, cfg=None, api=None):
    if (ns_kind == "actor" and cfg is not None and cfg.get("deed_subprocess")
            and not flag("--no-gui") and not flag("--__run_deed__")):
        return _run_as_child(code, sections, cfg, api)
    return _run_in_process(code, ns_kind, sections, cfg, api)


_LAST_COUNSEL = ""
def refresh_environment(sections, cfg):
    global _LAST_COUNSEL
    url = cfg.get("counsel_url") if flag("--counsel") else None
    note = ""
    if url:
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                note = r.read().decode("utf-8", "replace").strip()
        except OSError:
            note = ""
    if note and note != _LAST_COUNSEL:
        sections["counsel"] = note
        _LAST_COUNSEL = note
    else:
        sections["counsel"] = "(empty)"
        if note:
            _LAST_COUNSEL = note
    c = caps()
    if c is not None and hasattr(c, "environment"):
        c.environment(sections, cfg)


def _render_nodes(nodes):
    if not nodes:
        return "(no saved nodes yet; save one with save_node when a manner of deed proves itself)"
    lines = []
    for name in sorted(nodes):
        n = nodes[name]
        inv = int(n.get("invocations", 0)); adv = int(n.get("advances", 0))
        lines.append("- %s (proven %d/%d): %s" % (name, adv, inv, str(n.get("description", "")).replace("\n", " ")))
    return "\n".join(lines)


def _stigmergy_confirm(cfg):
    edges = cfg.setdefault("node_edges", {})
    buf = cfg.get("_edges_buffer", []) or []
    reinforce = float(cfg.get("edge_reinforcement", 1.0))
    evap = float(cfg.get("edge_evaporation", 0.05))
    for k in edges:
        edges[k] = round(edges[k] * (1.0 - evap), 4)
    for k in buf:
        edges[k] = round(edges.get(k, 0.0) + reinforce, 4)
    cfg["_edges_buffer"] = []


def _stigmergy_decay_only(cfg):
    edges = cfg.setdefault("node_edges", {})
    evap = float(cfg.get("edge_evaporation", 0.05))
    for k in edges:
        edges[k] = round(edges[k] * (1.0 - evap), 4)
    cfg["_edges_buffer"] = []


def _prune_graph(cfg):
    edges = cfg.setdefault("node_edges", {})
    for k in [k for k, w in edges.items() if w < 0.01]:
        del edges[k]
    nodes = cfg.get("nodes") or {}
    cap = int(cfg.get("node_budget", 0))
    if cap and len(nodes) > cap:
        ranked = sorted(nodes.items(),
                        key=lambda kv: (int(kv[1].get("advances", 0)),
                                        int(kv[1].get("invocations", 0))))
        for name, _n in ranked[:len(nodes) - cap]:
            del nodes[name]
            for k in [k for k in edges if k.startswith(name + "->") or k.endswith("->" + name)]:
                del edges[k]


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
    if not feedback.strip():
        return
    prior = sections.get("developer_feedback", "")
    entry = json.dumps({stage_name: feedback}, ensure_ascii=False, separators=(",", ":"))
    sections["developer_feedback"] = prior + ("\n" if prior else "") + entry


def turn(path, dry, inject, mode):
    sections, order = read_board(path)
    cfg = get_config(sections)
    st = cfg["state"]
    heal_if_body_changed(sections, cfg, st, dry, inject)
    stage_name = st.get("stage") or cfg["start"]
    stage = cfg["stages"][stage_name]
    sections["failure_streak"] = str(st.get("failure_streak", 0))
    sections["nodes"] = _render_nodes(cfg.get("nodes") or {})
    refresh_environment(sections, cfg)
    api = cfg["model"].get("api", "responses")
    if mode:
        api = {"xai": "responses", "lmstudio": "chat_completions", "acp": "acp", "file_proxy": "file_proxy"}[mode]
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
        reply = call_llm(cfg, stage, render_request(cfg, stage, sections), api)
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
        nodes_before = {n: int(v.get("invocations", 0)) for n, v in (cfg.get("nodes") or {}).items()}
        if stage_name == "execute":
            cfg["_spawn_left"] = int(cfg.get("spawn_budget", 0))
            cfg["_edges_buffer"] = []
            cfg["_node_stack"] = []
        signal, out = run_exec(str(data[ex["field"]]), ex.get("namespace", "actor"), sections, cfg, api)
        sections[ex["output_to"]] = out
        if stage_name == "execute":
            invoked = [n for n, v in (cfg.get("nodes") or {}).items()
                       if int(v.get("invocations", 0)) > nodes_before.get(n, 0)]
            st["pending_node_credit"] = invoked
            st["pending_edges"] = list(cfg.get("_edges_buffer", []) or [])
    if stage_name == "verify":
        if signal in ("confirmed", "halt"):
            for n in st.get("pending_node_credit", []) or []:
                if n in (cfg.get("nodes") or {}):
                    cfg["nodes"][n]["advances"] = int(cfg["nodes"][n].get("advances", 0)) + 1
            cfg["_edges_buffer"] = list(st.get("pending_edges", []) or [])
            _stigmergy_confirm(cfg)
            _prune_graph(cfg)
            st["pending_node_credit"] = []
            st["pending_edges"] = []
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
        elif signal in ("denied", "unwitnessed"):
            if signal == "denied":
                st["failure_streak"] = int(st.get("failure_streak", 0)) + 1
            cfg["_edges_buffer"] = []
            _stigmergy_decay_only(cfg)
            _prune_graph(cfg)
            st["pending_node_credit"] = []
            st["pending_edges"] = []
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
    global _ENGINE_SRC
    dry = flag("--dry")
    once = flag("--once")
    inject = opt("--inject")
    mode = opt("--mode")
    if flag("--reset"):
        factory_reset(BOARD)
        return
    _sections, _order = read_board(BOARD)
    _ENGINE_SRC = fenced(_sections.get("engine", ""))
    caps()
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

PRESERVE = {"config", "engine", "capabilities", "reset"}
DEFAULTS = {
    "goal": "(no goal set)",
    "living_word": "[execute] (not yet interpreted)\n[verify] (not yet interpreted)\n[recover] (not yet interpreted)",
    "ledger": "none yet", "action_frame": "(empty)",
    "perceived": "(empty)", "alternatives": "(empty)", "code": "(empty)",
    "evidence": "(empty)", "verdict": "(empty)",
    "counsel": "(empty)", "environment": "(fresh screen scan lands here each turn)",
    "failure_streak": "0", "developer_feedback": "",
    "nodes": "(no saved nodes yet; save one with save_node when a manner of deed proves itself)",
}


def read_board(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out, order, cur, buf, fence, seen = {}, [], None, [], False, set()
    for ln in text.split("\n"):
        if ln.lstrip().startswith(FENCE):
            fence = not fence
        m = None if fence else SEC.match(ln)
        if m and m.group(1) not in seen:
            if cur is not None:
                out[cur] = "\n".join(buf).strip("\n")
            cur, buf = m.group(1), []
            seen.add(cur)
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
sys.stderr.write("factory reset: memory, state, goal, and developer_feedback cleared; body (config/engine/capabilities/reset) preserved\n")
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
            name = name or pattern_values.get("legacy_name") or ""
            if role in WRITE_ROLES and not (pattern_values.get("value") or pattern_values.get("legacy_value")):
                pattern_values.update(self._pattern_text(_pattern(element, PID_TEXT_PATTERN), "Text"))
            value = pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("text") or ""
            text_full = value or name or pattern_values.get("legacy_description") or ""
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
                "value": value,
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
        depth_ceiling = int(self.cfg.get("depth_ceiling", 45))
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

    windows = enum_windows(int(cfg.get("min_window_area", 2500)))

    scanner = UiaScanner(cfg, desktop)
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    windows_out: list[dict[str, Any]] = []
    try:
        for win in windows:
            hwnd, rect = win["hwnd"], win["rect"]
            kept: dict[str, dict[str, Any]] = {}
            for x, y in _probe_points(rect, step_px):
                if not (0 <= x < sw and 0 <= y < sh):
                    continue
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
    observation_id = f"s{time.time_ns():x}"
    lines = ["W0 Screen Desktop"]

    for wi, win in enumerate(windows, start=1):
        wid = f"W{wi}"
        title = win["title"] or f"Window_{win['hwnd']}"
        window_title = clean(title)
        window_rect = win["rect"]
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

        screen_elements.append({
            "id": wid, "observation_id": observation_id, "role": "Window",
            "name": window_title, "title": window_title, "text": window_title,
            "rect": window_rect,
            "px": (window_rect["left"] + window_rect["right"]) // 2,
            "py": (window_rect["top"] + window_rect["bottom"]) // 2,
            "hwnd": win["hwnd"], "owner_hwnd": win["hwnd"], "visible": True,
        })
        actionable = [e for e in elements if e.get("action")]
        for e in actionable:
            anc = nearest_action_ancestor(e)
            if anc is not None:
                action_children.setdefault(id(anc), []).append(e)
            else:
                roots.append(e)

        lines.append(f"{wid} Window {window_title} rect=({window_rect['left']},{window_rect['top']},{window_rect['right']},{window_rect['bottom']})")
        def emit(e: dict[str, Any], indent: int) -> None:
            # Reachability at the source: an element is offered as clickable ONLY where its
            # rect truly meets the screen AND its owner window. Intersect the three; if the
            # meeting is empty the element is unreachable (below the fold, scrolled out of a
            # virtual container) and is dropped, so promise equals provision - every entry in
            # action_index bears a click-point the hand will not refuse. The click guard stays.
            er = e.get("rect") or {}
            ix_l = max(int(er.get("left", 0)), int(window_rect["left"]), 0)
            ix_t = max(int(er.get("top", 0)), int(window_rect["top"]), 0)
            ix_r = min(int(er.get("right", 0)), int(window_rect["right"]), int(screen["width"]))
            ix_b = min(int(er.get("bottom", 0)), int(window_rect["bottom"]), int(screen["height"]))
            if ix_r <= ix_l or ix_b <= ix_t:
                return
            e["px"], e["py"] = (ix_l + ix_r) // 2, (ix_t + ix_b) // 2
            counter["n"] += 1
            sid = f"e{counter['n']}"
            e["short_id"] = sid
            action = str(e.get("action", "")) if e.get("enabled") is not False else ""
            parts = [p for p in (
                sid, str(e.get("role", "")), clean(e.get("name", "") or ""),
                f"[{action}]" if action else "",
            ) if p]
            lines.append("  " * indent + " ".join(parts))
            public = {**{k: v for k, v in e.items() if k != "children"},
                      "short_id": sid, "action_key": sid, "observation_id": observation_id,
                      "window_id": wid, "window_title": window_title}
            action_index[sid] = public
            screen_elements.append({k: v for k, v in public.items() if k not in ("short_id", "action_key")})
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

    def scroll(self, x: int, y: int, amount: int | None = None, hwnd: int = 0, *, clicks: int | None = None) -> dict[str, Any]:
        if (amount is None) == (clicks is None):
            raise TypeError("scroll requires exactly one of amount or clicks")
        amount = clicks if amount is None else amount
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


def snapshot_observation():
    return {
        "action_index": _LAST_OBS["action_index"],
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
    }


def restore_observation(snap):
    _LAST_OBS["action_index"] = snap.get("action_index", {}) or {}
    _LAST_OBS["screen_elements"] = snap.get("screen_elements", []) or []
    _LAST_OBS["desktop_tree_text"] = snap.get("desktop_tree_text", "") or ""


if not NO_GUI:
    _bind_windows()


def _no_gui_hand():
    def _absent(*_a, **_k):
        raise RuntimeError("no GUI on this host (--no-gui): the desktop hand cannot act here")
    return _types.SimpleNamespace(
        click=_absent, type_text=_absent, paste_clipboard=_absent,
        set_clipboard=_absent, press_key=_absent, hotkey=_absent,
        scroll=_absent, open_url=_absent, observe=_absent,
    )


_SELF_DIR = ROOT / ".self"
_EDITABLE = {"config", "engine", "reset", "capabilities"}
_SECTION_LANG = {"config": "json", "engine": "python", "reset": "python", "capabilities": "python"}


def _ensure_self_repo():
    import subprocess, sys as _sys
    if (_SELF_DIR / ".git").is_dir():
        return _SELF_DIR
    _SELF_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(_SELF_DIR)], capture_output=True, text=True, check=True)
    for k, v in (("user.email", "endgame-ai@localhost"), ("user.name", "endgame-ai")):
        subprocess.run(["git", "-C", str(_SELF_DIR), "config", k, v], capture_output=True, text=True, check=True)
    (_SELF_DIR / "_gate.py").write_text(
        "import sys, json, py_compile\n"
        "f = sys.argv[1]\n"
        "if f.endswith('.py'):\n"
        "    py_compile.compile(f, doraise=True)\n"
        "elif f.endswith('.json'):\n"
        "    json.load(open(f, encoding='utf-8'))\n",
        encoding="utf-8")
    py = _sys.executable.replace(chr(92), "/")
    hook = _SELF_DIR / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        "for f in $(git diff --cached --name-only --diff-filter=ACM); do\n"
        '  "' + py + '" _gate.py "$f" || exit 1\n'
        "done\n",
        encoding="utf-8")
    hook.chmod(0o755)
    return _SELF_DIR


def _fenced_payload(section_body):
    import re
    _bt = chr(96) * 3
    m = re.search(_bt + r"(?:\w+)?\s*\n(.*)\n" + _bt + r"\s*\Z", section_body.strip(), re.S)
    if not m:
        raise RuntimeError("section body is not a single fenced block; cannot locate its code")
    return m.group(1)


def _commit_section(sections, name, old, new):
    import subprocess
    if name not in _EDITABLE:
        raise RuntimeError("commit_section editeth only genome sections %s, not %r; memory and proof are engine-owned"
                           % (sorted(_EDITABLE), name))
    lang = _SECTION_LANG[name]
    payload = _fenced_payload(sections[name])
    if not isinstance(old, str) or old == "":
        raise RuntimeError("commit_section needeth a non-empty [old] snippet that standeth verbatim in the %s payload" % name)
    hits = payload.count(old)
    if hits == 0:
        raise RuntimeError("commit_section found no [old] snippet in the %s payload; read thy current body from repo_root + '/endgame.md' and copy it exactly" % name)
    if hits > 1:
        raise RuntimeError("commit_section found [old] %d times in the %s payload; widen it with surrounding lines until it standeth exactly once" % (hits, name))
    new_payload = payload.replace(old, new, 1)
    new_body = chr(96) * 3 + lang + "\n" + new_payload.rstrip("\n") + "\n" + chr(96) * 3
    repo = _ensure_self_repo()
    ext = {"python": "py", "json": "json"}[lang]
    fname = name + "." + ext
    (repo / fname).write_text(new_payload.rstrip("\n") + "\n", encoding="utf-8")
    add = subprocess.run(["git", "-C", str(repo), "add", "--", fname], capture_output=True, text=True)
    if add.returncode != 0:
        raise RuntimeError("git add failed for %s:\n%s" % (fname, add.stderr.strip()))
    if subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet"]).returncode == 0:
        sections[name] = new_body
        return {"section": name, "file": fname, "changed": False}
    r = subprocess.run(["git", "-C", str(repo), "commit", "-m", "section:" + name], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("git rejected %r (syntax gate):\n%s\n%s" % (name, r.stdout.strip(), r.stderr.strip()))
    sections[name] = new_body
    return {"section": name, "file": fname, "committed": r.stdout.strip().split("\n")[0]}


def _read_element(sid):
    """Reveal the WHOLE text an element beareth in the current observation, untruncated -
    the depth-on-demand companion to the budgeted tree. Fail hard on a stale/unknown id."""
    idx = _LAST_OBS.get("action_index") or {}
    e = idx.get(sid)
    if e is None:
        raise KeyError("read: no element %r in the fresh scan; a short id dieth with the looking that bore it" % (sid,))
    return e.get("text_full") or e.get("value") or e.get("name") or ""


def build(kind, sections, separated=True):
    common = {
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
        "repo_root": str(ROOT),
        "python_executable": __import__("sys").executable,
    }
    if kind == "witness" and separated:
        return common
    common["action_index"] = _LAST_OBS["action_index"]
    common["read"] = _read_element
    common["commit_section"] = lambda name, old, new: _commit_section(sections, name, old, new)
    if NO_GUI:
        common["desktop"] = _no_gui_hand()
        return common
    d = get_desktop()
    common["desktop"] = _types.SimpleNamespace(
        click=d.click, type_text=d.type_text, paste_clipboard=d.paste_clipboard,
        set_clipboard=d.set_clipboard, press_key=d.press_key, hotkey=d.hotkey,
        scroll=d.scroll, open_url=d.open_url, observe=d.observe,
    )
    return common


def _host_facts():
    import getpass, platform, shutil, sys as _s
    try:
        user = getpass.getuser()
    except Exception:
        user = "(unknown)"
    tools = [t for t in ("git", "python", "powershell.exe", "pwsh", "cmd", "bash", "node", "curl", "pip") if shutil.which(t)]
    return "\n".join([
        "HOST",
        "platform: %s (%s)" % (platform.platform(), _s.platform),
        "machine: %s" % platform.node(),
        "user: %s" % user,
        "cwd: %s" % os.getcwd(),
        "repo_root: %s" % ROOT,
        "python: %s" % _s.executable,
        "shell_tools: %s" % (", ".join(tools) or "(none found)"),
    ])


def environment(sections, cfg=None):
    facts = _host_facts()
    if NO_GUI:
        _LAST_OBS["action_index"] = {}
        _LAST_OBS["screen_elements"] = []
        _LAST_OBS["desktop_tree_text"] = ""
        sections["environment"] = facts + "\n\nSCREEN\n(no GUI on this host: --no-gui; no screen observed)"
        return
    d = get_desktop()
    obs_cfg = (cfg or {}).get("observation", {})
    obs_result = d.observe(obs_cfg)
    _LAST_OBS["action_index"] = obs_result.get("action_index", {}) or {}
    _LAST_OBS["screen_elements"] = obs_result.get("screen_elements", []) or []
    _LAST_OBS["desktop_tree_text"] = str(obs_result.get("desktop_tree_text") or "").strip()
    tree = _LAST_OBS["desktop_tree_text"] or "(no interactable elements observed)"
    sections["environment"] = facts + "\n\nSCREEN\n" + tree
```

## goal
(no goal set)

## living_word
[execute] (not yet interpreted)
[verify] (not yet interpreted)
[recover] (not yet interpreted)

## ledger
none yet

## action_frame
(empty)

## perceived
(empty)

## alternatives
(empty)

## code
(empty)

## evidence
(empty)

## verdict
(empty)

## counsel
(empty)

## environment
(fresh screen scan lands here each turn)

## failure_streak
0

## developer_feedback


## nodes
(no saved nodes yet; save one with save_node when a manner of deed proves itself)
