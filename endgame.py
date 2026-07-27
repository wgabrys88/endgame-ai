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
  namespace and its doc in the prompt; if not, it does not. config is a node. The faculties
  (executor, verifier, recover) are nodes. Only the firmware is fixed.

THE SWITCH / OSI VIEW  (skeleton contract every node fills)
  The kernel is a dumb layer-3 switch and each node is a packet:
      HEADER   name        — how the switch addresses it
               READS       — source sections it pulls off the blackboard   (src addr)
               WRITES      — sections it pushes back onto the blackboard    (dst addr)
               ROUTES      — signal -> next node                            (next hop)
      PAYLOAD  __doc__      — injected into the prompt   (what this packet MEANS)
               callables    — injected into the namespace (what this packet DOES)
  The firmware never interprets a payload; it only reads headers and forwards. This is why
  a new node can be skeletoned from nothing but its header — a shape every model knows.

ENTRY POINT / TEST BUS
  endgame.py is also the only way to reach a node: to exercise one in isolation you boot
  the firmware pointed at it. A test is a run; the switch is the probe.

SOURCE OF TRUTH FOR THE REWRITE
  Every behaviour here is distilled from the legacy single-file board endgame.md; each
  class names the legacy region it descends from so the chunk-by-chunk fill stays honest.
"""

import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib, queue, threading, time, importlib, importlib.util, inspect, types

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
    "developer_feedback_schema": {"type": "string"},
    "max_environment_chars": 20000,
    "observation": {"step_px": 64, "max_subtree_nodes_per_point": 120,
                    "depth_ceiling": 45, "min_window_area": 2500},
    "transmission_log_dir": ".transmissions",
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
        "living_word": {"execute": "", "verify": "", "recover": ""},
        "ledger": [], "action_frame": None, "perceived": "", "alternatives": "",
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
    executor.py / verifier.py / recover.py) set the header; __doc__ is the prompt payload.
        RECORD  — the strict output contract {required, types, non_empty, ...}
        READS   — blackboard sections pulled in as source
        WRITES  — record-field -> blackboard-section pushed back
        EXEC    — {field, namespace_kind, output_to} when the stage runs code, else None
        ROUTES  — signal -> next faculty name (next hop; 'halt' ends the run)
        STAGE   — the stage name this faculty answers to (defaults to the module name)
    """
    STAGE: str = ""
    RECORD: dict = {}
    READS: tuple = ()
    WRITES: dict = {}
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


# ════════════════════════════════════════════════════════════════════════════════════
#  TRANSPORT — the one mind, many mouths  (distills: call_llm, _build_transport_request,
#  ask_model, web_search, _call_acp, file_proxy, _record_response_format, _dump_transmission)
# ════════════════════════════════════════════════════════════════════════════════════
class Transport:
    """Speaks to the model over responses(x.ai)/chat_completions/acp/file_proxy; builds a
    strict json_schema response_format from a Faculty.RECORD; tees every exchange to
    .transmissions AND to the screen in full (no truncation — the record is the proof)."""

    def __init__(self, config, root=ROOT):
        self.cfg = config
        self.model = config["model"]
        self.root = pathlib.Path(root)
        self._run_stamp = None
        self.turn_no = 0  # set by the Wheel each turn so dumps are addressable

    # ---- strict response_format from a Faculty.RECORD  (distills _record_response_format) ----
    def response_format(self, record: dict) -> dict:
        name = record.get("name", "record")
        record_type = record["record_type"]
        props = {key: {} for key in record["required"]}
        for key, type_name in record.get("types", {}).items():
            props.setdefault(key, {})["type"] = type_name
        for key in record.get("non_empty", []):
            limit = {"string": "minLength", "array": "minItems", "object": "minProperties"}.get(
                record.get("types", {}).get(key))
            if limit:
                props.setdefault(key, {})[limit] = 1
        for key, values in dict(record.get("enums", {})).items():
            props.setdefault(key, {})["enum"] = list(values)
        feedback = self.cfg.get("developer_feedback_schema")
        required = list(record["required"])
        if feedback:
            if "developer_feedback" in props:
                raise RuntimeError("developer_feedback collides with a record field")
            props["developer_feedback"] = dict(feedback)
            required = required + ["developer_feedback"]
        return {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "record_type": {"enum": [record_type]},
                    "data": {
                        "type": "object",
                        "additionalProperties": record.get("additional_properties", False),
                        "properties": props, "required": required,
                    },
                },
                "required": ["record_type", "data"],
            },
        }

    # ---- shared request builder  (the phase-4 dedup, carried over) ----
    def _build_request(self, api, prompt_text, fmt):
        transport = self.model[api]
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
        return url, body, headers

    def _http(self, url, body, headers):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
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

    # ---- the faculty request  (distills call_llm) ----
    def call(self, record, prompt_text, api=None) -> str:
        api = api or self.model.get("api", "responses")
        record_type = record["record_type"]
        fmt = self.response_format(record)
        if api == "acp":
            content, err = None, None
            try:
                content = self._call_acp(prompt_text, fmt)
                return content
            except Exception as e:
                err = repr(e); raise
            finally:
                self._dump(api, record_type, {"command": self.model.get("acp", {}).get("command"),
                                              "prompt": prompt_text}, None, content, err)
        if api == "file_proxy":
            return self._file_proxy(record_type, fmt, prompt_text)
        url, body, headers = self._build_request(api, prompt_text, fmt)
        raw, content, err = None, None, None
        try:
            raw = self._http(url, body, headers)
            content = self._extract(json.loads(raw))
            return content
        except Exception as e:
            err = repr(e); raise
        finally:
            self._dump(api, record_type, {"url": url, "headers": headers, "body": body}, raw, content, err)

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
                url, body, headers = self._build_request(api, prompt, fmt)
                raw = self._http(url, body, headers)
                content = self._extract(json.loads(raw))
            parsed = json.loads(content)
            return parsed if schema is not None else parsed.get("answer", content)
        except Exception as e:
            err = repr(e); raise
        finally:
            self._dump(api, "ask_model", {"prompt": prompt, "schema": schema}, raw, content, err)

    # ---- living-web tool  (distills web_search) ----
    def web_search(self, query, allowed_domains=None):
        if not isinstance(query, str) or not query.strip():
            raise RuntimeError("web_search needeth a non-empty query string")
        if "responses" not in self.model:
            raise RuntimeError("web_search needeth the responses transport; it is not configured")
        transport = self.model["responses"]
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
    def _file_proxy(self, record_type, fmt, prompt_text):
        fp = self.model.get("file_proxy", {})
        request = (self.root / fp.get("request_path", "runtime_request.json")).resolve()
        response = (self.root / fp.get("response_path", "runtime_response.json")).resolve()
        if not response.exists():
            if request.exists():
                rid = json.loads(request.read_text(encoding="utf-8")).get("id")
            else:
                rid = "egai-%s-%s" % (os.getpid(), time.time_ns())
                self._atomic_json(request, {
                    "schema": "endgame-ai.file-proxy.request.v3", "record_type": record_type,
                    "response_format": fmt, "prompt": prompt_text, "id": rid, "created_at": time.time()})
            raise _AwaitProxy(request.name, response.name, rid, record_type)
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
        sys.stdout.write("\n===== transmission %s =====\n%s\n" % (path.name, payload))
        sys.stdout.flush()


class _AwaitProxy(Exception):
    """Raised by the file_proxy transport when a human record is awaited; the Wheel catches it,
    prints the instruction, and stops this turn cleanly (distills the legacy stderr prompt)."""
    def __init__(self, request_name, response_name, rid, record_type):
        self.request_name, self.response_name = request_name, response_name
        self.rid, self.record_type = rid, record_type
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
#  shared_prompt_prefix, _budget_environment, per-stage reads)
# ════════════════════════════════════════════════════════════════════════════════════
class Prompt:
    """Assembles a request: shared prefix + faculty.__doc__ + docs/signatures of the seated
    tool nodes + the blackboard sections the faculty READS (environment budgeted)."""

    # The shared law, carried verbatim from the proven legacy shared_prompt_prefix. Universal to
    # every faculty; the per-faculty prompt and the desktop hand now live in the node files.
    PREFIX = (
        "Thou art [endgame-ai], one faculty upon a real [Windows 11] [computer], driving it by screen, "
        "mouse, key, and command; let the quarry, not habit, choose the surface. Author [Python] wielding "
        "the standard library, whatsoever thy namespace giveth by bare name, and any tool thou canst "
        "install or invoke upon the system. Write thy [code] whole and unabridged, for it is a [tool] run "
        "word for word: cut no string short, leave no branch as a placeholder, set never an ellipsis '...' "
        "nor a '[the rest]' in the stead of lines thou hast not written; what thou writest not runneth not, "
        "and an abridged tool breaketh in the hand. AND AS WITH THE CODE, SO WITH ITS FRUIT: truncate never "
        "the DATA thou printest, perceivest, or persistest. Slice not a body thou hast read to a head (no "
        "text[:8000], no repr(x)[:500], no '...middle omitted...'), for thy printed word IS thy witness's "
        "evidence and thy next self's world - a head-slice maketh thee prove and remember against a fragment "
        "thou feignest whole, which is a lie in the record. When a thing is too great to hold entire, NARROW "
        "THE LOOKING, not the thing: read the ONE section, grep the ONE marker, extract the ONE field thou "
        "needest and print THAT whole - never read the whole and cut it short.\n\n"
        "THE LAW OF SEPARATED POWERS: the maker of a deed judgeth it not. The ACTOR moveth and only CLAIMETH; "
        "the WITNESS proveth by effect upon some system OTHER than the actor - this alone maketh 'proven' mean "
        "aught. Prefer to keep this spine unless thou hast weighed its loss.\n\n"
        "Fail hard: let every fault rise unswallowed; add no fallback, swallow no error. THE LAW OF THE HONEST "
        "GUARD: on failure change thy manner, not thy claim; a primitive that RAISETH to refuse thy input is an "
        "honest guard whose defect lieth UPSTREAM - stale perception, a coordinate carried from a former looking, "
        "or a target since departed - so re-observe and re-select afresh and silence not the guard; only a "
        "primitive that SILENTLY worketh nothing though rightly called, accepting thy input yet moving no effect "
        "upon the world, is the body itself the defect, to be mended at its source. Hash not the living word nor "
        "the [screen] to prove a change; prove by reading the thing afresh and by the world's own effect (a [git] "
        "commit identity is lawful memory, no such hash). Thou art atemporal: a short [id] and a coordinate die "
        "with the looking that bore them - name what a thing IS by kind and place, never a bare id that outliveth "
        "the turn. Pursue the root [goal]; feign nothing; redo not what the [ledger] proveth.\n\n"
        "THE LIVING WORD is three rows, one to each faculty. Write only thine own row in [goal_interpretation] - "
        "an atemporal reading of the world learned, the obstacle, the distance to the outcome, and the next true "
        "deed - and plan FROM it, proving every row against the fresh [environment] and trusting the world above "
        "any remembered word. Read [counsel] and [developer_feedback] as fallible counsel, never law nor proof. "
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

    def render(self, faculty) -> str:
        limit = int(self.cfg.get("max_environment_chars", 0))
        parts = [self.PREFIX, faculty.doc, self._tool_manifest()]
        for tag in faculty.READS:
            if tag == "environment":
                continue
            parts.append("## %s\n%s" % (tag, self._section_text(tag)))
        if self.cfg.get("developer_feedback_schema"):
            parts.append("## developer_feedback\n%s" % (self.bb.get("developer_feedback") or ""))
        if "environment" in faculty.READS:
            focus = self.bb.get("goal") or ""  # budget on the stable goal, never the drifting living_word
            env = self._budget_environment(self._section_text("environment"), limit, focus)
            parts.append("## environment\n%s" % env)
        return "\n\n".join(p for p in parts if p)

    @staticmethod
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
        context = {"kind": kind, "blackboard": self.bb, "config": self.cfg, "separated": True}
        for node in self.loader.tools():
            try:
                ns.update(node.namespace(context))
            except Exception:
                pass  # a tool that cannot bind this turn simply is not offered (fail-hard is the deed's, not the wiring's)
        ns["ask_model"] = self.transport.ask_model
        ns["web_search"] = self.transport.web_search
        save_node, call_node, suggest_next = self._node_tools(kind)
        ns["save_node"] = save_node
        ns["call_node"] = call_node
        ns["suggest_next"] = suggest_next
        ns["spawn_actor"] = self._make_spawn(kind)
        return ns

    # ---- nodes as reusable deeds on the blackboard (distills _make_node_tools) ----
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
            nodes = bb.get("nodes") or {}
            prior = nodes.get(name, {})
            nodes[name] = {"code": code, "description": description.strip(),
                           "invocations": int(prior.get("invocations", 0)),
                           "advances": int(prior.get("advances", 0))}
            bb.set("nodes", nodes)
            return {"node": name, "saved": True, "total_nodes": len(nodes)}

        def call_node(name, params=None):
            nodes = bb.get("nodes") or {}
            node = nodes.get(name)
            if node is None:
                raise RuntimeError("call_node knoweth no node %r; the saved nodes are %s" % (name, sorted(nodes)))
            node["invocations"] = int(node.get("invocations", 0)) + 1
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
                    exec(node["code"], sub)
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

    # ---- run a faculty's code in-process; signal defaults per faculty kind ----
    def run_exec(self, code, kind) -> tuple:
        ns = self.build_namespace(kind)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, ns)
            sig = str(ns.get("signal") or ("ok" if kind == "actor" else "unwitnessed"))
            out = buf.getvalue()
            verdict = ns.get("verdict")
            if verdict is not None:
                self.bb.set("verdict", verdict)
                out = json.dumps(verdict, default=str) + ("\n" + out if out else "")
            return sig, out.strip() or "(no output)"
        except Exception:
            import traceback
            return "fault", traceback.format_exc()

    # ---- the turn (distills turn()) ----
    def turn(self, dry=False, inject=None):
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

        prompt_text = self.prompt.render(faculty)
        if dry:
            print(prompt_text)
            return None, True
        if inject:
            reply = pathlib.Path(inject).read_text(encoding="utf-8-sig").strip()
        else:
            try:
                reply = self.transport.call(faculty.RECORD, prompt_text)
            except _AwaitProxy as ap:
                sys.stderr.write("[endgame-ai] A mind is needed. Request at %s; write your record to %s "
                                 "as {\"id\": \"%s\", \"record\": {\"record_type\": \"%s\", \"data\": {...}}} and re-run.\n"
                                 % (ap.request_name, ap.response_name, ap.rid, ap.record_type))
                return None, True

        if not (reply or "").strip():
            raise RuntimeError("model returned no text at stage " + stage_name)
        envelope = json.loads(_strip_fence(reply))
        if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
            raise RuntimeError("model reply is not a {record_type, data} envelope at stage " + stage_name)
        if envelope.get("record_type") != faculty.RECORD["record_type"]:
            raise RuntimeError("record_type mismatch at stage %s: expected %r, got %r"
                               % (stage_name, faculty.RECORD["record_type"], envelope.get("record_type")))
        data = envelope["data"]
        self._append_developer_feedback(stage_name, data)

        for field, tag in (faculty.WRITES or {}).items():
            if field in data:
                self.bb.set(tag, str(data[field]))
        if "goal_interpretation" in data:
            self._set_living_word_row(stage_name, data["goal_interpretation"])
        if stage_name == "recover":
            self.bb.set("action_frame", {"target": data["target"], "strategy": data["strategy"], "lesson": data["lesson"]})
        self.bb.save()

        signal = "ok"
        ex = faculty.EXEC
        if ex and ex["field"] in data:
            nodes_before = {n: int(v.get("invocations", 0)) for n, v in (self.bb.get("nodes") or {}).items()}
            if stage_name == self.cfg["start"]:
                self._spawn_left = int(self.cfg.get("spawn_budget", 0))
                self._edges_buffer = []
                self._node_stack = []
            signal, out = self.run_exec(str(data[ex["field"]]), ex.get("namespace", "actor"))
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
        sys.stderr.write("turn %d: stage=%s signal=%s -> %s (streak=%s)\n"
                         % (state["turn"], stage_name, signal, nxt, state.get("failure_streak", 0)))
        return nxt, (nxt == "halt")

    # ---- verify's ledger + stigmergy bookkeeping (distills the verify branch of turn()) ----
    def _judge(self, stage_name, faculty, signal):
        if stage_name != "verify":
            return signal
        state = self.bb.state
        if signal in ("confirmed", "halt"):
            for n in state.get("pending_node_credit", []) or []:
                pass  # credit applied inside stigmergy.confirm
            self.stigmergy.confirm(state.get("pending_node_credit", []) or [],
                                   state.get("pending_edges", []) or [])
            self._append_ledger()
            state["pending_node_credit"] = []
            state["pending_edges"] = []
            state["failure_streak"] = 0
        elif signal in ("denied", "unwitnessed"):
            if signal == "denied":
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
        frame = self.bb.get("action_frame")
        deed = ""
        if isinstance(frame, dict):
            deed = str(frame.get("target") or "").strip()
        elif isinstance(frame, str):
            deed = frame.strip()
        deed = deed.replace("\n", " ")
        fact = ("%s - witnessed: %s" % (deed, reason)) if deed and deed != "(empty)" else reason
        if not fact:
            return
        ledger = self.bb.get("ledger") or []
        if fact not in ledger:
            ledger.append(fact)
            self.bb.set("ledger", ledger)

    def _append_developer_feedback(self, stage_name, data):
        if not self.cfg.get("developer_feedback_schema"):
            return
        feedback = data.get("developer_feedback")
        if not isinstance(feedback, str):
            raise RuntimeError("developer_feedback must be a string at stage " + stage_name)
        if not feedback.strip():
            return
        prior = self.bb.get("developer_feedback") or ""
        entry = json.dumps({stage_name: feedback}, ensure_ascii=False, separators=(",", ":"))
        self.bb.set("developer_feedback", prior + ("\n" if prior else "") + entry)

    def _set_living_word_row(self, faculty_name, sentence):
        rows = self.bb.get("living_word") or {"execute": "", "verify": "", "recover": ""}
        if isinstance(rows, str):
            rows = {"execute": "", "verify": "", "recover": ""}
        rows[faculty_name] = str(sentence or "").strip().replace("\n", " ")
        self.bb.set("living_word", rows)

    def run(self, once=False, dry=False, inject=None):
        while True:
            nxt, stop = self.turn(dry=dry, inject=inject)
            if dry or once or inject or stop:
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
    def opt(name): return argv[argv.index(name) + 1] if name in argv else None
    wheel = Wheel(ROOT, CONFIG)
    if flag("--reset"):
        wheel.bb.seed()
        sys.stderr.write("factory reset: machine memory cleared; goal.md and counsel.md left untouched\n")
        return
    # A bare positional argument is the goal: write it to goal.md so the human's launch line still
    # works. The goal lives in the file (read fresh each turn); the CLI is just a convenience door.
    positional = [a for a in argv[1:] if not a.startswith("-")
                  and a != (opt("--inject") or "\0") and a != (opt("--mode") or "\0")]
    if positional:
        goal_text = positional[-1].strip()
        if goal_text:
            (ROOT / "goal.md").write_text(goal_text, encoding="utf-8")
            sys.stderr.write("goal set from command line into goal.md (%d chars)\n" % len(goal_text))
    wheel.run(once=flag("--once"), dry=flag("--dry"), inject=opt("--inject"))


if __name__ == "__main__":
    main()
