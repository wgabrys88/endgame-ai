"""endgame — firmware for a self-evolving desktop organism. A BIOS, not an application.

THE BOOTLOADER DOCTRINE
  This file is the motherboard firmware. Like a BIOS it does four things and no more:
  it POSTs (discovers what hardware is plugged in), wires the buses, hands control to
  the installed parts, and routes signals between them. It carries NO domain knowledge —
  no desktop, no faculty prose, no goal. It is small, stable, and NOT self-mutable: the
  organism evolves by editing the parts plugged into it, never the firmware itself. A bad
  self-edit can brick a node; it can never brick the boot.

EVERYTHING IS A NODE EXCEPT THIS FILE
  Every other *.py in this folder is a hot-swappable card. Plug one in and it works; pull
  it out and the system simply lacks that faculty — no flag, no branch. Presence IS the
  switch. So there is no "gui mode": if gui.py is seated, a desktop hand appears in the
  namespace and its doc in the prompt; if not, it does not. The faculties (executor, witness,
  recover) are nodes. Config is constants on the firmware, not a node. Only the firmware is fixed.

THE SWITCH / OSI VIEW  (skeleton contract every node fills)
  The kernel is a dumb layer-3 switch and each node is a packet:
      HEADER   name        — how the switch addresses it
               READS       — source sections it pulls off the blackboard   (src addr)
               EXEC/ROUTES — whether it runs its code, and where each signal goes next
               ROUTES      — signal -> next node                            (next hop)
      PAYLOAD  __doc__      — injected into the prompt   (what this packet MEANS)
               callables    — injected into the namespace (what this packet DOES)
  The firmware never interprets a payload; it only reads headers and forwards. This is why
  a new node can be skeletoned from nothing but its header — a shape every model knows.

ENTRY POINT / TEST BUS
  endgame.py is also the only way to reach a node: to exercise one in isolation you boot
  the firmware pointed at it. A test is a run; the switch is the probe.

LINEAGE
  Every behaviour here was distilled from the retired single-file board endgame.md; each class
  names the legacy region it descends from. That board is gone from the tree (git history keeps
  it); this firmware plus its nodes is now the whole organism.
"""

import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib, queue, threading, time, importlib, importlib.util, inspect, types, uuid

ROOT = pathlib.Path(__file__).resolve().parent
KERNEL = pathlib.Path(__file__).name


# ════════════════════════════════════════════════════════════════════════════════════
#  CONFIG — constants ON the bootloader, not a node. Transport knobs and budgets only;
#  it carries no domain knowledge and no prompt. (distills the legacy config JSON's model/
#  budget keys; the shared prompt law lives in Prompt.PREFIX, faculty prompts in the nodes.)
# ════════════════════════════════════════════════════════════════════════════════════
CONFIG = {
    "start": "execute",
    "model": {
        "api": "responses",
        "responses": {
            "url": "https://api.x.ai/v1/responses",
            "request": {"model": "grok-4.5", "temperature": 0.4,
                        "reasoning": {"effort": "high"}, "store": False},
        },
        "chat_completions": {
            "url": "http://localhost:1234/v1/chat/completions",
            "request": {"model": "local-model", "temperature": 0.2, "stream": False},
        },
        "acp": {"command": ["grok", "agent", "--no-leader", "stdio"], "timeout": 240},
        "file_proxy": {"request_path": "runtime_request.json", "response_path": "runtime_response.json"},
    },
    # ONE crossing budget, one source of truth: the most any single blackboard AREA may receive,
    # and the most one complete model request may carry. Nothing is cut to fit: an emitted flood
    # faults, while an overfull request switches to conscience before transport.
    "max_area_chars": 65536,
    "observation": {"step_px": 64, "max_subtree_nodes_per_point": 120,
                    "depth_ceiling": 65, "min_window_area": 2500},
    "transmission_log_dir": ".transmissions",
    "web_search_max_tool_calls": 1,  # one billable server-side search/browse call per web_search
    "deed_subprocess": True,
    "deed_timeout": 360,
    "node_budget": 64,
    "edge_evaporation": 0.05,
    "edge_reinforcement": 1.0,
    "spawn_budget": 3,
    "node_ttl_seconds": 300,
}


# ════════════════════════════════════════════════════════════════════════════════════
#  BLACKBOARD — persistent shared memory  (distills: legacy read_board/write_board, the
#  ## memory sections, ## reset defaults, cfg["state"])
#  SPLIT PERSISTENCE: machine state lives in blackboard.json; the two human-edited
#  surfaces live as plain files the human edits live between turns — goal.md and counsel.md.
# ════════════════════════════════════════════════════════════════════════════════════
class Blackboard:
    """Memory across turns. Machine sections persist to blackboard.json (atomic tmp+rename).
    goal.md and counsel.md are read FRESH each turn so a human may steer mid-run."""

    SEED = {
        "state": {"stage": None, "last_signal": None, "turn": 0, "failure_streak": 0},
        "living_word": {"execute": "", "witness": "", "recover": ""},
        "ledger": [], "action_frame": None,
        "code": "", "evidence": "", "verdict": None,
        "nodes": {}, "node_edges": {},
    }
    HUMAN_FILES = {"goal": "goal.md", "counsel": "counsel.md"}

    def __init__(self, root=ROOT):
        self.root = pathlib.Path(root)
        self.path = self.root / "blackboard.json"
        if self.path.exists():
            self._m = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._m = json.loads(json.dumps(self.SEED))  # deep copy of seed
            self.save()
        for section, fname in self.HUMAN_FILES.items():
            fp = self.root / fname
            if not fp.exists():
                fp.write_text("", encoding="utf-8")

    def get(self, section):
        if section in self.HUMAN_FILES:  # read FRESH so a human may steer mid-run
            return (self.root / self.HUMAN_FILES[section]).read_text(encoding="utf-8")
        return self._m.get(section)

    def set(self, section, value):
        if section in self.HUMAN_FILES:
            raise RuntimeError("%s is human-edited; the organism writes it not" % section)
        self._m[section] = value

    @property
    def state(self):
        return self._m["state"]

    def save(self):
        tmp = self.path.with_name(self.path.name + ".tmp.%s.%s" % (os.getpid(), time.time_ns()))
        tmp.write_text(json.dumps(self._m, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic overwrite on Windows AND POSIX (os.rename fails on Windows if target exists)

    def seed(self):  # factory reset: machine memory only; human files (goal/counsel) untouched
        self._m = json.loads(json.dumps(self.SEED))
        self.save()


# ════════════════════════════════════════════════════════════════════════════════════
#  NODES & LOADER — the folder becomes the body  (distills: caps()/capabilities.build,
#  save_node/call_node, the stage-prompt/namespace wiring)
# ════════════════════════════════════════════════════════════════════════════════════
class Node:
    """A seated card. __doc__ is its packet meaning (prompt); public callables are its
    function (namespace). A node may define namespace(ctx) to inject a richer hand."""

    def __init__(self, module):
        self.module = module
        self.name = module.__name__

    @property
    def doc(self) -> str:
        return (getattr(self.module, "__doc__", "") or "").strip()

    def _public(self):
        names = getattr(self.module, "__all__", None)
        if names is None:
            names = [n for n in dir(self.module) if not n.startswith("_")]
        out = {}
        for n in names:
            obj = getattr(self.module, n, None)
            # only own definitions (skip re-exported stdlib modules pulled in by import)
            if isinstance(obj, types.ModuleType):
                continue
            if getattr(obj, "__module__", self.name) not in (self.name, None):
                if not (inspect.isclass(obj) or inspect.isfunction(obj)):
                    pass
            out[n] = obj
        return out

    def signatures(self) -> str:
        # A custom namespace hook is the exact export boundary. Its docstring advertises those
        # names; listing every public helper would promise internals the exec namespace withholds.
        if hasattr(self.module, "namespace") and callable(self.module.namespace):
            return ""
        lines = []
        for n, obj in self._public().items():
            if callable(obj):
                try:
                    lines.append("%s%s" % (n, inspect.signature(obj)))
                except (ValueError, TypeError):
                    lines.append(n + "(...)")
        return "\n".join(lines)

    def namespace(self, context=None) -> dict:
        if hasattr(self.module, "namespace") and callable(self.module.namespace):
            return dict(self.module.namespace(context))
        return {n: o for n, o in self._public().items() if callable(o)}


class Faculty(Node):
    """A node that IS a stage of the wheel — a packet with routing headers. Subclasses (in
    executor.py / witness.py / recover.py) set the header; __doc__ is the prompt payload.

    THE ONE UNIVERSAL RECORD (Faculty.RECORD): every faculty, and every saved deed-node, returns
    the SAME five fields - goal_interpretation, alternatives, intent, code, developer_feedback - so
    one schema serves the whole system, may be cached in the system prompt, and lets each node know
    exactly what every other expects. A faculty fills the fields its office needeth and leaves the
    rest empty; the docstring saith which. So the header carrieth only what DIFFERETH between offices:
        READS   — blackboard sections this office pulls in as source
        EXEC    — {namespace, output_to} when the office RUNS its [code], else None
        ROUTES  — signal -> next faculty name (next hop; 'halt' ends the run)
        STAGE   — the stage name this office answers to (defaults to the module name)
    """
    RECORD = ("goal_interpretation", "alternatives", "intent", "code")  # + developer_feedback, appended
    STAGE: str = ""
    READS: tuple = ()
    EXEC: dict | None = None
    ROUTES: dict = {}

    def stage_name(self):
        return self.STAGE or self.name



class Loader:
    """POST: import every top-level *.py in ROOT except the firmware and _private files.
    A module that defines a Faculty subclass is a faculty (its instance is that subclass);
    every other seated module is a tool node. config is NOT a node — it is constants on the
    bootloader (module-level CONFIG). Absent files contribute nothing; presence is the switch."""

    def __init__(self, root=ROOT):
        self.root = pathlib.Path(root)
        self._tools = []
        self._faculties = {}
        self._mtimes = {}
        self.reload()

    def _node_files(self):
        return sorted(p for p in self.root.glob("*.py")
                      if p.name != KERNEL and not p.name.startswith("_"))

    def reload(self):
        self._tools, self._faculties, self._mtimes = [], {}, {}
        for path in self._node_files():
            self._mtimes[path.name] = path.stat().st_mtime
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            fac_cls = self._faculty_class(module)
            if fac_cls is not None:
                fac = fac_cls(module)
                self._faculties[fac.stage_name()] = fac
            else:
                self._tools.append(Node(module))

    @staticmethod
    def _faculty_class(module):
        for obj in vars(module).values():
            if (inspect.isclass(obj) and issubclass(obj, Faculty)
                    and obj is not Faculty and obj.__module__ == module.__name__):
                return obj
        return None

    def tools(self) -> list:
        return list(self._tools)

    def faculties(self) -> dict:
        return dict(self._faculties)

    def changed(self) -> bool:
        current = {p.name: p.stat().st_mtime for p in self._node_files()}
        return current != self._mtimes


class _RequestBudget(Exception):
    """A complete model request crossed the one configured boundary before transport."""
    def __init__(self, used, limit):
        self.used, self.limit = int(used), int(limit)
        super().__init__(
            "model request produced too much data: %d chars, the request budget holdeth at most %d. "
            "The request crossed no transport boundary; change the KIND of approach and narrow the "
            "next looking." % (self.used, self.limit)
        )


# ════════════════════════════════════════════════════════════════════════════════════
#  TRANSPORT — the one mind, many mouths  (distills: call_llm, _build_transport_request,
#  ask_model, web_search, _call_acp, file_proxy, _record_response_format, _dump_transmission)
# ════════════════════════════════════════════════════════════════════════════════════
class Transport:
    """Speaks to the model over responses(x.ai)/chat_completions/acp/file_proxy; builds a
    strict json_schema response_format from the one universal record; tees every exchange to
    .transmissions AND to the screen in full (no truncation — the record is the proof)."""

    def __init__(self, config, root=ROOT):
        self.cfg = config
        self.model = config["model"]
        self.root = pathlib.Path(root)
        self._run_stamp = None
        self.turn_no = 0  # set by the Wheel each turn so dumps are addressable
        self.console = sys.stdout  # transport logs bypass deed stdout; they are not deed evidence
        self.prompt_cache_key = "endgame-ai-" + uuid.uuid5(
            uuid.NAMESPACE_URL, self.root.resolve().as_uri()).hex
        self._web_search_turn = None

    # ---- the ONE strict schema, universal to every faculty and every saved deed-node ----
    #      Five fields, all required strings; only developer_feedback may be empty. Because it is
    #      the same every turn, it lives in the cached system prompt and needs no record_type wrapper
    #      - the kernel knoweth which office it asked.
    def response_format(self, fields):
        names = list(fields) + ["developer_feedback"]
        props = {name: {"type": "string"} for name in names}
        for name in fields:
            props[name]["minLength"] = 1
        return {
            "name": "record",
            "strict": True,
            "schema": {
                "type": "object", "additionalProperties": False,
                "properties": props, "required": names,
            },
        }

    # ---- shared request builder: STABLE system + VOLATILE user (KV-cache friendly) ----
    def _request_body(self, api, system_text, user_text, fmt):
        body = dict(self.model[api]["request"])
        if api == "responses":
            body.pop("previous_response_id", None)
            body["store"] = False
            body["prompt_cache_key"] = self.prompt_cache_key
            if system_text:
                body["instructions"] = system_text   # the cached, stage-independent law + schema + roles
            body["input"] = user_text                # the volatile "I am [stage]" + fresh board
            body["text"] = {"format": {"type": "json_schema", **fmt}}
        elif api == "chat_completions":
            msgs = []
            if system_text:
                msgs.append({"role": "system", "content": system_text})
            msgs.append({"role": "user", "content": user_text})
            body["messages"] = msgs
            body["response_format"] = {"type": "json_schema", "json_schema": fmt}
        else:
            raise RuntimeError("unknown model api: " + str(api))
        return body

    @staticmethod
    def _serialized(body):
        return json.dumps(body, ensure_ascii=False, separators=(",", ":"))

    def budget_user(self, system_text, user_text, fields, api=None):
        """Append the sole volatile budget value as the final user section, then guard it whole."""
        api = api or self.model.get("api", "responses")
        limit = int(self.cfg.get("max_area_chars", 0))
        if not limit:
            return user_text
        fmt = self.response_format(fields)
        base, suffix = user_text.rstrip(), ""
        for _ in range(12):
            candidate = base + suffix
            if api in ("responses", "chat_completions"):
                body = self._request_body(api, system_text, candidate, fmt)
            else:
                body = {"system": system_text, "user": candidate, "response_format": fmt}
            used = len(self._serialized(body))
            remaining = limit - used
            pressure = (used * 100 + limit - 1) // limit
            new_suffix = ("\n\n## budget\nrequest_chars=%d; limit_chars=%d; "
                          "remaining_chars=%d; pressure=%d%%"
                          % (used, limit, remaining, pressure))
            if new_suffix == suffix:
                if used > limit:
                    raise _RequestBudget(used, limit)
                return candidate
            suffix = new_suffix
        raise RuntimeError("request budget line did not settle")

    def _build_request(self, api, system_text, user_text, fmt):
        transport = self.model[api]
        url, body = transport["url"], self._request_body(api, system_text, user_text, fmt)
        headers = {"Content-Type": "application/json"}
        if api == "responses":
            headers["Authorization"] = "Bearer " + os.environ["XAI_API_KEY"]
        return url, body, headers

    def _http(self, url, body, headers):
        payload = self._serialized(body)
        limit = int(self.cfg.get("max_area_chars", 0))
        if limit and len(payload) > limit:
            raise _RequestBudget(len(payload), limit)
        req = urllib.request.Request(url, data=payload.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=240) as r:
            return r.read().decode()

    @staticmethod
    def _texts_from_parts(parts):
        if isinstance(parts, str):
            return [parts] if parts.strip() else []
        if not isinstance(parts, list):
            return []
        return [str(p.get("text") if isinstance(p, dict) else p) for p in parts
                if (isinstance(p, str) and p.strip()) or (isinstance(p, dict) and p.get("text"))]

    def _extract(self, obj):
        if obj.get("choices"):
            return str(obj["choices"][0]["message"]["content"])
        content = str(obj.get("output_text") or "")
        if content.strip():
            return content
        return "\n".join(text for item in obj.get("output", []) if isinstance(item, dict)
                         and item.get("type") != "reasoning"
                         for text in self._texts_from_parts(item.get("content")))

    # ---- the faculty request: system (cached law+schema+roles) + user (fresh board) ----
    def call(self, system_text, user_text, fields, api=None) -> str:
        api = api or self.model.get("api", "responses")
        fmt = self.response_format(fields)
        if api == "acp":
            content, err = None, None
            try:
                content = self._call_acp(system_text + "\n\n" + user_text, fmt)
                return content
            except Exception as e:
                err = repr(e); raise
            finally:
                self._dump(api, "record", {"command": self.model.get("acp", {}).get("command"),
                                           "system": system_text, "user": user_text}, None, content, err)
        if api == "file_proxy":
            return self._file_proxy(fmt, system_text, user_text)
        url, body, headers = self._build_request(api, system_text, user_text, fmt)
        raw, content, err = None, None, None
        try:
            raw = self._http(url, body, headers)
            content = self._extract(json.loads(raw))
            return content
        except Exception as e:
            err = repr(e); raise
        finally:
            self._dump(api, "record", {"url": url, "headers": headers, "body": body}, raw, content, err)

    # ---- reasoning tool  (distills ask_model) ----
    def ask_model(self, prompt, schema=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise RuntimeError("ask_model needeth a non-empty prompt string")
        api = self.model.get("api", "responses")
        if schema is not None:
            fmt = {"name": "ask_model_reply", "strict": True, "schema": schema}
        else:
            fmt = {"name": "ask_model_reply", "strict": False,
                   "schema": {"type": "object", "additionalProperties": True,
                              "properties": {"answer": {"type": "string"}}, "required": ["answer"]}}
        raw, content, err = None, None, None
        try:
            if api == "acp":
                content = self._call_acp(prompt, fmt)
            else:
                url, body, headers = self._build_request(api, "", prompt, fmt)
                raw = self._http(url, body, headers)
                content = self._extract(json.loads(raw))
            parsed = json.loads(content)
            return parsed if schema is not None else parsed.get("answer", content)
        except Exception as e:
            err = repr(e); raise
        finally:
            self._dump(api, "ask_model", {"prompt": prompt, "schema": schema}, raw, content, err)

    # ---- living-web tool  (distills web_search) ----
    def web_search(self, query):
        if not isinstance(query, str) or not query.strip():
            raise RuntimeError("web_search needeth a non-empty query string")
        if self._web_search_turn == self.turn_no:
            raise RuntimeError(
                "web_search already ran this wheel turn. Its result is the checkpoint: print and use "
                "that whole result; let a later turn decide whether another question is needed.")
        if "responses" not in self.model:
            raise RuntimeError("web_search needeth the responses transport; it is not configured")
        transport = self.model["responses"]
        url, body = transport["url"], dict(transport["request"])
        body.pop("previous_response_id", None)
        body.pop("text", None)
        body["store"] = False
        body["prompt_cache_key"] = self.prompt_cache_key + "-web"
        body["reasoning"] = {"effort": "low"}
        body["parallel_tool_calls"] = False
        body["max_tool_calls"] = int(self.cfg.get("web_search_max_tool_calls", 1))
        body["input"] = [{"role": "user", "content":
            "Answer using a single web_search query; do not browse or open additional "
            "pages beyond that one search. " + query}]
        body["tools"] = [{"type": "web_search"}]
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + os.environ["XAI_API_KEY"]}
        raw, result, err = None, None, None
        self._web_search_turn = self.turn_no
        try:
            raw = self._http(url, body, headers)
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
                        if isinstance(ann, dict) and ann.get("url"):
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
            usage = obj.get("usage") or {}
            server_usage = usage.get("server_side_tool_usage_details") or {}
            result = {"text": "\n".join(text_parts), "sources": uniq,
                      "web_search_calls": int(server_usage.get("web_search_calls", 0) or 0)}
            if not result["text"].strip():
                raise RuntimeError("web_search returned no text; raw response preserved in the transmission dump")
            return result
        except Exception as e:
            err = repr(e); raise
        finally:
            self._dump("responses", "web_search", {"url": url, "headers": headers, "body": body},
                       raw, json.dumps(result) if result is not None else None, err)

    # ---- ACP subprocess transport  (distills _call_acp) ----
    def _call_acp(self, prompt_text, fmt):
        acp = self.model.get("acp", {})
        proc = subprocess.Popen(acp.get("command", ["grok", "agent", "--no-leader", "stdio"]),
            cwd=str(self.root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
            session, _ = rpc("session/new", {"cwd": str(self.root), "mcpServers": [],
                "_meta": {"systemPromptOverride":
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

    # ---- human-in-the-loop transport  (distills file_proxy) ----
    def _file_proxy(self, fmt, system_text, user_text):
        fp = self.model.get("file_proxy", {})
        request = (self.root / fp.get("request_path", "runtime_request.json")).resolve()
        response = (self.root / fp.get("response_path", "runtime_response.json")).resolve()
        if not response.exists():
            if request.exists():
                rid = json.loads(request.read_text(encoding="utf-8")).get("id")
            else:
                rid = "egai-%s-%s" % (os.getpid(), time.time_ns())
                self._atomic_json(request, {
                    "schema": "endgame-ai.file-proxy.request.v4", "response_format": fmt,
                    "system": system_text, "user": user_text, "id": rid, "created_at": time.time()})
            raise _AwaitProxy(request.name, response.name, rid)
        pending = json.loads(request.read_text(encoding="utf-8"))
        obj = json.loads(response.read_text(encoding="utf-8"))
        if obj.get("id") != pending.get("id"):
            raise RuntimeError("file_proxy response id %r does not match pending %r" % (obj.get("id"), pending.get("id")))
        record = obj["record"]
        request.unlink(missing_ok=True); response.unlink(missing_ok=True)
        return json.dumps(record, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _atomic_json(path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp.%s.%s" % (os.getpid(), time.time_ns()))
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)

    # ---- the tee: same object to disk AND screen, whole  (distills _dump_transmission) ----
    def _transmission_root(self):
        base = self.cfg.get("transmission_log_dir")
        if not base:
            return None
        override = os.environ.get("EGAI_RUN_DIR")
        if override:
            return pathlib.Path(override)
        if self._run_stamp is None:
            self._run_stamp = time.strftime("%Y-%m-%d-%H-%M-%S")
        root = self.root / base / self._run_stamp
        os.environ["EGAI_RUN_DIR"] = str(root)
        return root

    def _dump(self, api, record_type, request_obj, raw, content, error):
        root = self._transmission_root()
        if root is None:
            return
        root.mkdir(parents=True, exist_ok=True)
        safe = request_obj
        if isinstance(request_obj, dict) and "headers" in request_obj:
            safe = dict(request_obj)
            headers = dict(request_obj.get("headers") or {})
            if "Authorization" in headers:
                headers["Authorization"] = "Bearer [redacted]"
            safe["headers"] = headers
        dump = {"at": time.time(), "turn": self.turn_no, "record_type": record_type, "api": api,
                "request": safe, "raw_response": raw, "extracted_content": content, "error": error}
        path = root / ("turn-%05d-%s-%s.json" % (int(self.turn_no), record_type, time.time_ns()))
        payload = json.dumps(dump, ensure_ascii=False, indent=2, default=str)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
        self.console.write("\n===== transmission %s =====\n%s\n" % (path.name, payload))
        self.console.flush()


class _AwaitProxy(Exception):
    """Raised by the file_proxy transport when a human record is awaited; the Wheel catches it,
    prints the instruction, and stops this turn cleanly (distills the legacy stderr prompt)."""
    def __init__(self, request_name, response_name, rid):
        self.request_name, self.response_name = request_name, response_name
        self.rid = rid
        super().__init__("awaiting human record %s" % rid)


# ════════════════════════════════════════════════════════════════════════════════════
#  STIGMERGY — routing memory, backprop, pruning  (distills: _stigmergy_confirm/_decay_only,
#  _prune_graph, node credit via pending_node_credit/pending_edges, edge reinforcement)
# ════════════════════════════════════════════════════════════════════════════════════
class Stigmergy:
    """Node-to-node edges reinforce on a proven advance and evaporate each turn; nodes below
    threshold are pruned. Credit (backprop) flows to the nodes a confirmed deed invoked.
    Operates on the blackboard's nodes/node_edges registry (distills _stigmergy_confirm/
    _stigmergy_decay_only/_prune_graph and the pending_node_credit/pending_edges credit path)."""

    def __init__(self, blackboard, config=CONFIG):
        self.bb = blackboard
        self.cfg = config

    def _edges(self):
        return self.bb.get("node_edges") or {}

    def _nodes(self):
        return self.bb.get("nodes") or {}

    def confirm(self, invoked_nodes, edges_buffer):
        # backprop credit: a proven advance rewards the nodes the deed invoked
        nodes = self._nodes()
        for name in invoked_nodes or []:
            if name in nodes:
                nodes[name]["advances"] = int(nodes[name].get("advances", 0)) + 1
        # reinforce the edges walked this deed, then evaporate all
        edges = self._edges()
        reinforce = float(self.cfg.get("edge_reinforcement", 1.0))
        evap = float(self.cfg.get("edge_evaporation", 0.05))
        for k in edges:
            edges[k] = round(edges[k] * (1.0 - evap), 4)
        for k in edges_buffer or []:
            edges[k] = round(edges.get(k, 0.0) + reinforce, 4)
        self.bb.set("node_edges", edges); self.bb.set("nodes", nodes)
        self.prune()

    def decay_only(self):
        edges = self._edges()
        evap = float(self.cfg.get("edge_evaporation", 0.05))
        for k in edges:
            edges[k] = round(edges[k] * (1.0 - evap), 4)
        self.bb.set("node_edges", edges)
        self.prune()

    def prune(self):
        edges = self._edges()
        for k in [k for k, w in edges.items() if w < 0.01]:
            del edges[k]
        nodes = self._nodes()
        cap = int(self.cfg.get("node_budget", 0))
        if cap and len(nodes) > cap:
            ranked = sorted(nodes.items(),
                            key=lambda kv: (int(kv[1].get("advances", 0)), int(kv[1].get("invocations", 0))))
            for name, _n in ranked[:len(nodes) - cap]:
                del nodes[name]
                for k in [k for k in edges if k.startswith(name + "->") or k.endswith("->" + name)]:
                    del edges[k]
        self.bb.set("node_edges", edges); self.bb.set("nodes", nodes)


# ════════════════════════════════════════════════════════════════════════════════════
#  PROMPT — the board rebuilt from what is seated  (distills: render_request,
#  shared_prompt_prefix, per-stage reads; environment bounded honestly, not by guessed relevance)
# ════════════════════════════════════════════════════════════════════════════════════
class Prompt:
    """Assembles a request: shared prefix + faculty.__doc__ + docs/signatures of the seated
    tool nodes + the blackboard sections the faculty READS."""

    # The shared law, carried verbatim from the proven legacy shared_prompt_prefix. Universal to
    # every faculty; the per-faculty prompt and the desktop hand now live in the node files.
    PREFIX = (
        "Thou art [endgame-ai], one faculty of a living organism upon a real [computer]. Thy reach is "
        "whatsoever thy namespace giveth thee THIS turn: the standard library always, and by bare name "
        "each SEATED TOOL below - a hand upon the screen, a reader of the world, or none, as the tools "
        "present decree; let the quarry, not habit, choose among the surfaces thou art given, and reach "
        "never for a surface no seated tool offereth. Author [Python] wielding thy namespace and any tool "
        "thou canst install or invoke upon the system. Write thy [code] whole and unabridged, for it is a "
        "[tool] run word for word: cut no string short, leave no branch as a placeholder, set never an "
        "ellipsis '...' nor a '[the rest]' in the stead of lines thou hast not written; what thou writest "
        "not runneth not, and an abridged tool breaketh in the hand. AND AS WITH THE CODE, SO WITH ITS "
        "FRUIT: truncate never the DATA thou printest, perceivest, or persistest. Slice not a body thou "
        "hast read to a head (no text[:8000], no repr(x)[:500], no '...middle omitted...'), for thy printed "
        "word IS thy witness's evidence and thy next self's world - a head-slice maketh thee prove and "
        "remember against a fragment thou feignest whole, which is a lie in the record. When a thing is too "
        "great to hold entire, NARROW THE LOOKING, not the thing: read the ONE section, grep the ONE marker, "
        "extract the ONE field thou needest and print THAT whole - never read the whole and cut it short. "
        "TRUNCATION IS A LIE IN THE RECORD - it is never permitted, in code, in fruit, or in memory.\n\n"
        "THE LAW OF SEPARATED POWERS: the maker of a deed judgeth it not. The ACTOR moveth and only CLAIMETH; "
        "the WITNESS proveth by effect upon some system OTHER than the actor - this alone maketh 'proven' mean "
        "aught. This spine is the organism's honesty; hold it inviolate.\n\n"
        "Fail hard: let every fault rise unswallowed; add no fallback, swallow no error. THE LAW OF THE HONEST "
        "GUARD: on failure change thy manner, not thy claim; a primitive that RAISETH to refuse thy input is an "
        "honest guard whose defect lieth UPSTREAM - stale perception, a coordinate carried from a former looking, "
        "or a target since departed - so re-observe and re-select afresh and silence not the guard; only a "
        "primitive that SILENTLY worketh nothing though rightly called, accepting thy input yet moving no effect "
        "upon the world, is the body itself the defect, to be mended at its source. Hash not the living word nor "
        "the [screen] to prove a change; prove by reading the thing afresh and by the world's own effect (a [git] "
        "commit identity is lawful memory, no such hash). Thou art atemporal: only what a thing IS - its kind, "
        "its place, its relation - endureth between lookings; so name and remember things by that enduring nature, "
        "the sole handle that surviveth a fresh scan. Pursue the root [goal]; feign nothing; redo not what the [ledger] proveth.\n\n"
        "WEIGH THE CONSEQUENCE ere thou movest or provest: ask of each act what it will CAUSE, and whether that "
        "effect carrieth the root [goal] one true step nearer. An act, a file, or a fact that beareth not upon the "
        "goal's nature is not thy road - choose the one that doth. Judge a thing FIT by what the goal needeth, never "
        "by a name that merely resembleth it: a thing that shareth a word with the quarry yet serveth it not is a "
        "false match, to be forsaken. Better to name the lack and re-observe than to force a thing that fitteth not.\n\n"
        "THE LIVING WORD is three rows, one to each faculty. Write only thine own row in [goal_interpretation] - "
        "an atemporal reading of the world learned, the obstacle, the distance to the outcome, and the next true "
        "deed - and plan FROM it, proving every row against the fresh [environment] and trusting the world above "
        "any remembered word. When the [ledger] groweth while that distance standeth unchanged, reinterpret the "
        "root [goal] and choose a road different in KIND; motion upon the same obstacle is no advance. Read "
        "[counsel] and [developer_feedback] as fallible counsel, never law nor proof.\n\n"
        "THE REQUEST BUDGET is urgency, impact, and self-control made visible. The final [budget] line of the "
        "volatile user message alone beareth its changing values: the complete request size, its one hard limit, "
        "the room remaining, and pressure. As pressure riseth, spend fewer words and combine adjacent LOCAL acts "
        "whose next target can be rebound from a fresh looking. Keep each costly external request as one checkpoint; "
        "its answer must survive before another request or a fallible world action. Change the KIND of road when the "
        "living word and ledger show unchanged distance. At overflow an actor or witness request switchest to "
        "conscience before transport, preserving every source whole; an office without such a route faileth hard. "
        "Nothing is cut.\n\n"
        "Return one JSON [record] and nothing beside, bearing every field thine office requireth and no field it "
        "forbiddeth. In thine own [developer_feedback] write the empty string save when this body's prompt, "
        "required record, promised namespace, or capability beareth a true defect; then name that defect, its "
        "evidence, and the least amendment - never an ordinary failed deed."
    )

    def __init__(self, blackboard, loader, config=CONFIG):
        self.bb = blackboard
        self.loader = loader
        self.cfg = config

    def _tool_manifest(self) -> str:
        # every seated tool node advertises its packet: what it MEANS (doc) and what it DOES (signatures)
        parts = []
        for node in self.loader.tools():
            doc = node.doc
            sigs = node.signatures()
            if not doc and not sigs:
                continue
            block = "### %s" % node.name
            if doc:
                block += "\n" + doc
            if sigs:
                block += "\n" + sigs
            parts.append(block)
        if not parts:
            return ""
        return "## the seated tools (by bare name in thy namespace)\n" + "\n\n".join(parts)

    def _section_text(self, tag) -> str:
        value = self.bb.get(tag)
        if value is None or value == "":
            return "(empty)"
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)

    _SCHEMA_LAW = (
        "THE ONE RECORD: whatsoever office thou art this turn, return a JSON object of exactly these "
        "keys, each a string: [goal_interpretation] - thy living-word row (the world learned, the "
        "obstacle, the distance, the next true deed); [alternatives] - the roads or proofs thou "
        "weighedst and forsookest, and why; [intent] - the ONE deed to be enacted next, named for the "
        "next reader (empty when thou thyself enactest it now as [code]); [code] - the Python thou "
        "runnest THIS turn (empty when thine office runneth none); [developer_feedback] - the empty "
        "string, or a named body-defect per the shared law. Fill the fields thine office useth and "
        "leave the rest the empty string; thy role below saith which."
    )

    def render_system(self):
        # STABLE across turns and offices -> cacheable: the shared law, the one schema, EVERY office's
        # role (so each knoweth what the others expect), and the seated tools. It nameth no single stage.
        roles = "\n\n".join("## the office of [%s]\n%s" % (f.stage_name(), f.doc)
                            for _, f in sorted(self.loader.faculties().items()))
        parts = [self.PREFIX, self._SCHEMA_LAW,
                 "## THE OFFICES OF THE WHEEL (thou art assigned one below; know them all)\n" + roles,
                 self._tool_manifest()]
        return "\n\n".join(p for p in parts if p)

    def render_user(self, faculty):
        # VOLATILE: who thou art THIS turn, and the fresh board areas thine office readeth.
        parts = ["I am [%s] in the endgame-ai wheel this turn. Act in that office alone." % faculty.stage_name()]
        for tag in faculty.READS:
            if tag == "environment":
                continue
            parts.append("## %s\n%s" % (tag, self._section_text(tag)))
        parts.append("## developer_feedback\n%s" % (self.bb.get("developer_feedback") or ""))
        if "environment" in faculty.READS:
            parts.append("## environment\n%s" % self._section_text("environment"))
        return "\n\n".join(p for p in parts if p)


# ════════════════════════════════════════════════════════════════════════════════════
#  WHEEL — the turn loop / the switch fabric  (distills: turn(), run_exec/_run_in_process/
#  _run_as_child, spawn_actor parallel recursion, heal_if_body_changed, main())
# ════════════════════════════════════════════════════════════════════════════════════
class Wheel:
    """One turn: address the current faculty, render its packet, ask the model, apply WRITES,
    run any EXEC in a namespace built from the seated nodes, judge the signal, forward to the
    next hop. Hot-reloads a NODE when its file changes (never the firmware). Spawns budgeted
    parallel sub-actors on demand. (distills turn(), run_exec, _make_node_tools, spawn_actor,
    heal_if_body_changed, main.)"""

    def __init__(self, root=ROOT, config=CONFIG):
        self.root = pathlib.Path(root)
        self.cfg = config
        self.bb = Blackboard(root)
        self.loader = Loader(root)
        self.transport = Transport(config, root)
        self.stigmergy = Stigmergy(self.bb, config)
        self.prompt = Prompt(self.bb, self.loader, config)
        self._edges_buffer = []
        self._node_stack = []
        self._spawn_left = int(config.get("spawn_budget", 0))

    # ---- perception: any seated tool node may refresh the environment section ----
    def _refresh_environment(self):
        for node in self.loader.tools():
            fn = getattr(node.module, "environment", None)
            if callable(fn):
                fn(self.bb, self.cfg)

    # ---- namespace: stdlib + seated tool nodes + transport tools + node tools + spawn ----
    def build_namespace(self, kind) -> dict:
        ns = {"json": json, "os": os, "sys": sys, "pathlib": pathlib, "re": re,
              "subprocess": subprocess, "time": time, "io": io,
              "repo_root": str(self.root), "python_executable": sys.executable}
        context = {"kind": kind, "blackboard": self.bb, "config": self.cfg}
        for node in self.loader.tools():
            ns.update(node.namespace(context))
        ns["ask_model"] = self.transport.ask_model
        ns["web_search"] = self.transport.web_search
        save_node, call_node, suggest_next = self._node_tools(kind)
        ns["save_node"] = save_node
        ns["call_node"] = call_node
        ns["suggest_next"] = suggest_next
        ns["spawn_actor"] = self._make_spawn(kind)
        return ns

    # ---- nodes as reusable deeds ON DISK (distills _make_node_tools; a saved deed becomes a
    #      real node_<name>.py card - auto-seated, its doc entering the prompt - and survives by
    #      usage: the reaper deletes unproven deeds unused past node_ttl_seconds) ----
    def _deed_path(self, name):
        return self.root / ("node_%s.py" % name)

    def _node_tools(self, kind):
        bb = self.bb

        def _edge_key(a, b):
            return "%s->%s" % (a, b)

        def save_node(name, code, description):
            if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9_]{1,40}$", name or ""):
                raise RuntimeError("save_node name must be a short lower_snake identifier")
            if not isinstance(code, str) or not code.strip():
                raise RuntimeError("save_node needeth non-empty code")
            if not isinstance(description, str) or not description.strip():
                raise RuntimeError("save_node needeth a non-empty description of what the node doth and its params")
            compile(code, "<node:%s>" % name, "exec")
            # the deed becomes a real, importable card: docstring -> prompt manifest; CODE -> the
            # verbatim deed, run in the full actor namespace by call_node('%s'). Import is side-
            # effect-free (only a string is assigned), so auto-seating cannot crash the boot.
            doc = description.strip().replace('"""', "'''")
            body = ('"""%s\n\nA saved deed-node. Invoke with call_node(%r, params). It fadeth if left\n'
                    'unused and unproven; a deed that earneth an advance is kept.\n"""\n\nCODE = %r\n'
                    % (doc, name, code))
            path = self._deed_path(name)
            tmp = path.with_name(path.name + ".tmp.%s.%s" % (os.getpid(), time.time_ns()))
            tmp.write_text(body, encoding="utf-8")
            os.replace(tmp, path)
            nodes = bb.get("nodes") or {}
            prior = nodes.get(name, {})
            now = time.time()
            nodes[name] = {"description": description.strip(),
                           "invocations": int(prior.get("invocations", 0)),
                           "advances": int(prior.get("advances", 0)),
                           "created_at": float(prior.get("created_at", now)),
                           "last_used": now}
            bb.set("nodes", nodes); bb.save()
            return {"node": name, "file": path.name, "saved": True, "total_nodes": len(nodes)}

        def call_node(name, params=None):
            nodes = bb.get("nodes") or {}
            if name not in nodes:
                raise RuntimeError("call_node knoweth no node %r; the saved nodes are %s" % (name, sorted(nodes)))
            path = self._deed_path(name)
            if not path.exists():
                raise RuntimeError("call_node: the deed-node file for %r is gone from disk (reaped or never written)" % name)
            scope = {}
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), scope)
            code = scope.get("CODE")
            if not isinstance(code, str) or not code.strip():
                raise RuntimeError("deed-node %r beareth no CODE string" % name)
            nodes[name]["invocations"] = int(nodes[name].get("invocations", 0)) + 1
            nodes[name]["last_used"] = time.time()
            bb.set("nodes", nodes)
            src = self._node_stack[-1] if self._node_stack else "__root__"
            self._edges_buffer.append(_edge_key(src, name))
            self._node_stack.append(name)
            try:
                sub = self.build_namespace(kind)
                sub["params"] = params if params is not None else {}
                sub["result"] = None
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(code, sub)
                return sub.get("result")
            finally:
                if self._node_stack:
                    self._node_stack.pop()

        def suggest_next(from_node=None):
            edges = bb.get("node_edges") or {}
            nodes = bb.get("nodes") or {}
            src = from_node or (self._node_stack[-1] if self._node_stack else "__root__")
            prefix = src + "->"
            succ = sorted(((k[len(prefix):], w) for k, w in edges.items() if k.startswith(prefix)),
                          key=lambda kv: -kv[1])
            return [{"node": n, "weight": round(w, 3),
                     "proven": "%d/%d" % (int(nodes.get(n, {}).get("advances", 0)),
                                          int(nodes.get(n, {}).get("invocations", 0)))}
                    for n, w in succ if n in nodes]

        return save_node, call_node, suggest_next

    # ---- BIOS survival: reap deed-node files unused past node_ttl_seconds and never proven.
    #      A proven deed (advances>0) is immortal; throwaway code is truly thrown away from disk.
    def _reap_nodes(self):
        ttl = float(self.cfg.get("node_ttl_seconds", 0))
        if ttl <= 0:
            return
        now = time.time()
        nodes = self.bb.get("nodes") or {}
        edges = self.bb.get("node_edges") or {}
        reaped = []
        for path in self.root.glob("node_*.py"):
            name = path.stem[len("node_"):]
            meta = nodes.get(name)
            if meta is None:  # orphan file with no registry memory: reap by its own mtime
                if now - path.stat().st_mtime > ttl:
                    path.unlink(missing_ok=True); reaped.append(name)
                continue
            if int(meta.get("advances", 0)) > 0:
                continue  # proven: immortal
            last = float(meta.get("last_used") or meta.get("created_at") or 0)
            if now - last > ttl:
                path.unlink(missing_ok=True)
                nodes.pop(name, None)
                for k in [k for k in edges if k.startswith(name + "->") or k.endswith("->" + name)]:
                    del edges[k]
                reaped.append(name)
        if reaped:
            self.bb.set("nodes", nodes); self.bb.set("node_edges", edges); self.bb.save()
            sys.stderr.write("reap: unused unproven deed-nodes deleted from disk: %s\n" % reaped)
            self.loader.reload()
            self.prompt = Prompt(self.bb, self.loader, self.cfg)

    # ---- parallel recursion (distills spawn_actor) ----
    def _make_spawn(self, kind):
        def spawn_actor(subgoal, hint=""):
            if not isinstance(subgoal, str) or not subgoal.strip():
                raise RuntimeError("spawn_actor needeth a non-empty subgoal string")
            if self._spawn_left <= 0:
                raise RuntimeError("spawn_actor budget is exhausted this deed")
            self._spawn_left -= 1
            prompt = (Prompt.PREFIX + "\n\nThou art a SPAWNED parallel [actor], wired beside thy parent to "
                      "pursue one narrow sub-quarry and return its fruit. Author ONE Python script that "
                      "achieveth the sub-goal and setteth result to what thou didst produce. Thy work is "
                      "counsel to thy parent and is not itself witnessed.\n\nSUB-GOAL: " + subgoal +
                      (("\nHINT: " + hint) if hint else "") + "\n\nThe fresh environment before thee:\n" +
                      (self.bb.get("environment") or "(none)") + "\n\nReturn only JSON {\"code\": \"<the python>\"}.")
            reply = self.transport.ask_model(prompt, schema={"type": "object", "additionalProperties": False,
                                             "properties": {"code": {"type": "string"}}, "required": ["code"]})
            code = reply["code"] if isinstance(reply, dict) else str(reply)
            sub = self.build_namespace(kind)
            sub["result"] = None
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(code, sub)
                return {"subgoal": subgoal, "result": sub.get("result"),
                        "output": buf.getvalue().strip() or "(no output)", "spawns_left": self._spawn_left}
            except Exception:
                import traceback
                return {"subgoal": subgoal, "result": None, "error": traceback.format_exc(),
                        "spawns_left": self._spawn_left}
        return spawn_actor

    # ---- run a faculty's code in-process; signal defaults per faculty kind. The EMITTED output
    #      (what would cross into the blackboard) is the one budgeted boundary: a deed that emits
    #      more than max_area_chars is treated as a FAILURE - "script produced too much data" -
    #      exactly like any other fault, so recover bids execute NARROW THE LOOKING. The code the
    #      deed WRITES and the data it reads INTERNALLY are never capped; only its fruit. ----
    def run_exec(self, code, kind) -> tuple:
        buf = io.StringIO()
        verdict = None
        try:
            ns = self.build_namespace(kind)
            with contextlib.redirect_stdout(buf):
                exec(code, ns)
            sig = str(ns.get("signal") or ("ok" if kind == "actor" else "unwitnessed"))
            verdict = ns.get("verdict")
            out = buf.getvalue()
        except Exception:
            import traceback
            sig = "fault"
            partial = buf.getvalue()
            out = partial + (("\n" if partial and not partial.endswith("\n") else "") + traceback.format_exc())
        verdict_text = json.dumps(verdict, default=str) if verdict is not None else ""
        emitted = len(out) + len(verdict_text)
        cap = int(self.cfg.get("max_area_chars", 0))
        if cap and emitted > cap:
            # the flood is refused whole and never stored; the deed simply failed to be concise
            return ("fault", "script produced too much data: %d chars emitted, the blackboard "
                    "area holdeth at most %d. NARROW THE LOOKING, not the thing - print the one "
                    "fact, count, path, or field needed to prove this deed; distil in code, or "
                    "save a node that returneth only what mattereth. The output was NOT stored."
                    % (emitted, cap))
        if verdict is not None:
            self.bb.set("verdict", verdict)
            out = verdict_text + ("\n" + out if out else "")
        return sig, out.strip() or "(no output)"

    def _budget_switch(self, stage_name, faculty, fault):
        """Route an unsent office request through its existing honesty signal, with no new stage."""
        signal = "unwitnessed" if stage_name == "witness" else "fault"
        nxt = (faculty.ROUTES or {}).get(signal)
        if nxt is None:
            raise fault
        ex = faculty.EXEC
        if ex:
            self.bb.set(ex["output_to"], str(fault))
        signal = self._judge(stage_name, faculty, signal)
        state = self.bb.state
        state["stage"] = nxt
        state["last_signal"] = signal
        state["turn"] = int(state.get("turn", 0)) + 1
        self.bb.save()
        self._reap_nodes()
        sys.stderr.write("turn %d: stage=%s signal=%s -> %s (streak=%s; request switched before transport)\n"
                         % (state["turn"], stage_name, signal, nxt, state.get("failure_streak", 0)))
        return nxt, (nxt == "halt")

    # ---- the turn (distills turn()) ----
    def turn(self, dry=False):
        if self.loader.changed():
            sys.stderr.write("heal: a node file changed on disk; re-seating the cards\n")
            self.loader.reload()
            self.prompt = Prompt(self.bb, self.loader, self.cfg)
        state = self.bb.state
        stage_name = state.get("stage") or self.cfg["start"]
        faculties = self.loader.faculties()
        if stage_name not in faculties:
            raise RuntimeError("no faculty node seated for stage %r; seated: %s" % (stage_name, sorted(faculties)))
        faculty = faculties[stage_name]
        self.transport.turn_no = int(state.get("turn", 0))
        self.bb.set("failure_streak", state.get("failure_streak", 0))
        self._refresh_environment()

        system_text = self.prompt.render_system()
        user_text = self.prompt.render_user(faculty)
        try:
            user_text = self.transport.budget_user(system_text, user_text, faculty.RECORD)
            if dry:
                print(system_text + "\n\n===== USER =====\n\n" + user_text)
                return None, True
            reply = self.transport.call(system_text, user_text, faculty.RECORD)
        except _RequestBudget as budget:
            if dry:
                raise
            return self._budget_switch(stage_name, faculty, budget)
        except _AwaitProxy as ap:
            sys.stderr.write("[endgame-ai] A mind is needed. Request at %s; write your record to %s "
                             "as {\"id\": \"%s\", \"record\": {...the five fields...}} and re-run.\n"
                             % (ap.request_name, ap.response_name, ap.rid))
            return None, True

        if not (reply or "").strip():
            raise RuntimeError("model returned no text at stage " + stage_name)
        data = json.loads(_strip_fence(reply))
        if not isinstance(data, dict):
            raise RuntimeError("model reply is not a JSON object at stage " + stage_name)
        self._append_developer_feedback(stage_name, data)

        # THE UNIVERSAL WRITES - same for every office, so the kernel needeth no per-faculty WRITES map:
        # the plan-row is the living word; the code authored is laid bare for the witness to judge; the
        # named next deed is the action_frame the next actor readeth.
        if data.get("goal_interpretation"):
            self._set_living_word_row(stage_name, data["goal_interpretation"])
        if data.get("code"):
            self.bb.set("code", data["code"])
        if data.get("intent"):
            self.bb.set("action_frame", data["intent"])
        self.bb.save()

        signal = "ok"
        ex = faculty.EXEC
        if ex and data.get("code"):
            nodes_before = {n: int(v.get("invocations", 0)) for n, v in (self.bb.get("nodes") or {}).items()}
            if stage_name == self.cfg["start"]:
                self._spawn_left = int(self.cfg.get("spawn_budget", 0))
                self._edges_buffer = []
                self._node_stack = []
            signal, out = self.run_exec(str(data["code"]), ex.get("namespace", "actor"))
            self.bb.set(ex["output_to"], out)
            invoked = [n for n, v in (self.bb.get("nodes") or {}).items()
                       if int(v.get("invocations", 0)) > nodes_before.get(n, 0)]
            state["pending_node_credit"] = invoked
            state["pending_edges"] = list(self._edges_buffer)

        signal = self._judge(stage_name, faculty, signal)

        nxt = (faculty.ROUTES or {}).get(signal)
        if nxt is None:
            raise RuntimeError("unmapped signal %r at stage %s; routes: %s"
                               % (signal, stage_name, list((faculty.ROUTES or {}).keys())))
        state["stage"] = nxt
        state["last_signal"] = signal
        state["turn"] = int(state.get("turn", 0)) + 1
        self.bb.save()
        self._reap_nodes()  # BIOS survival: throwaway deed-nodes fade from disk; proven ones stay
        sys.stderr.write("turn %d: stage=%s signal=%s -> %s (streak=%s)\n"
                         % (state["turn"], stage_name, signal, nxt, state.get("failure_streak", 0)))
        return nxt, (nxt == "halt")

    # ---- the witness's ledger + stigmergy bookkeeping ----
    def _judge(self, stage_name, faculty, signal):
        state = self.bb.state
        if stage_name != "witness":
            if signal == "fault":
                state["failure_streak"] = int(state.get("failure_streak", 0)) + 1
            return signal
        if signal in ("confirmed", "halt"):
            self.stigmergy.confirm(state.get("pending_node_credit", []) or [],
                                   state.get("pending_edges", []) or [])
            self._append_ledger()
            state["pending_node_credit"] = []
            state["pending_edges"] = []
            state["failure_streak"] = 0
        elif signal in ("denied", "unwitnessed"):
            state["failure_streak"] = int(state.get("failure_streak", 0)) + 1
            self.stigmergy.decay_only()
            state["pending_node_credit"] = []
            state["pending_edges"] = []
        return signal

    def _append_ledger(self):
        verdict = self.bb.get("verdict")
        if isinstance(verdict, str):
            try:
                verdict = json.loads(verdict.split("\n", 1)[0])
            except Exception:
                verdict = None
        reason = ""
        if isinstance(verdict, dict):
            reason = str(verdict.get("reason") or "").strip().replace("\n", " ")
        if not reason:
            return
        ledger = self.bb.get("ledger") or []
        if reason not in ledger:
            ledger.append(reason)
            self.bb.set("ledger", ledger)

    def _append_developer_feedback(self, stage_name, data):
        feedback = data.get("developer_feedback")
        if not isinstance(feedback, str):
            raise RuntimeError("developer_feedback must be a string at stage " + stage_name)
        if not feedback.strip():
            return
        prior = self.bb.get("developer_feedback") or ""
        entry = json.dumps({stage_name: feedback}, ensure_ascii=False, separators=(",", ":"))
        self.bb.set("developer_feedback", prior + ("\n" if prior else "") + entry)

    def _set_living_word_row(self, faculty_name, sentence):
        rows = self.bb.get("living_word") or {"execute": "", "witness": "", "recover": ""}
        if isinstance(rows, str):
            rows = {"execute": "", "witness": "", "recover": ""}
        rows[faculty_name] = str(sentence or "").strip().replace("\n", " ")
        self.bb.set("living_word", rows)

    def run(self, once=False, dry=False):
        while True:
            nxt, stop = self.turn(dry=dry)
            if dry or once or stop:
                break


def _strip_fence(s):
    text = (s or "").strip()
    m = re.fullmatch(r"```(?:\w+)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def main():
    # The world's text is UTF-8 (screen scans carry any codepoint); the Windows console is not.
    # Force stdout/stderr to UTF-8 so the tee and --dry never die on a character (\u200e etc).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    # Ensure faculty files that `import endgame` bind to THIS running module, so their
    # Faculty subclasses share our Faculty identity (issubclass holds across the boundary).
    sys.modules.setdefault("endgame", sys.modules[__name__])
    if "endgame" in sys.modules and sys.modules["endgame"] is not sys.modules[__name__]:
        sys.modules["endgame"] = sys.modules[__name__]
    argv = sys.argv
    def flag(name): return name in argv
    wheel = Wheel(ROOT, CONFIG)
    if flag("--reset"):
        wheel.bb.seed()
        sys.stderr.write("factory reset: machine memory cleared; goal.md and counsel.md left untouched\n")
        return
    # A bare positional argument is the goal: write it to goal.md so the human's launch line still
    # works. The goal lives in the file (read fresh each turn); the CLI is just a convenience door.
    positional = [a for a in argv[1:] if not a.startswith("-")]
    if positional:
        goal_text = positional[-1].strip()
        if goal_text:
            (ROOT / "goal.md").write_text(goal_text, encoding="utf-8")
            sys.stderr.write("goal set from command line into goal.md (%d chars)\n" % len(goal_text))
    wheel.run(once=flag("--once"), dry=flag("--dry"))


if __name__ == "__main__":
    main()
