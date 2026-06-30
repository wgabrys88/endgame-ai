"""workbench — reliable live control/debug panel for endgame-ai.

The old panel read bulky files as if they were live state. This version uses a compact
truth model:
  - state.json             current organism snapshot, atomically written by organism.py
  - comms/runtime.ndjson   live event stream, compact and append-only
  - comms/brain_usage.ndjson structured usage ledger
  - wiring.json            editable brain/config topology

It never treats stale state as current: every status response includes file ages, mtimes,
and a stale flag. Raw logs remain available for inspection but are not polled into the UI.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
PORT = int(os.environ.get("ENDGAME_WORKBENCH_PORT", "8800"))
STATE_PATH = ROOT / "state.json"
WIRING_PATH = ROOT / "wiring.json"
GOAL_PATH = ROOT / "goal.json"


# ─── file helpers ───────────────────────────────────────────────────────────

def _read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: pathlib.Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{time.time_ns()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _root_path(value: str | None, default: str) -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def _stat(path: pathlib.Path) -> dict:
    try:
        st = path.stat()
        return {"exists": True, "path": str(path), "mtime": st.st_mtime, "age_s": max(0, time.time() - st.st_mtime), "size": st.st_size}
    except OSError:
        return {"exists": False, "path": str(path), "mtime": 0, "age_s": None, "size": 0}


def _tail_lines(path: pathlib.Path, max_lines: int = 200, max_bytes: int = 600_000) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(max(0, size - max_bytes))
                f.readline()  # drop partial first line
            raw = f.read()
    except OSError:
        return []
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()[-max_lines:]


def _tail_ndjson(path: pathlib.Path, max_lines: int = 200, max_bytes: int = 600_000) -> list[dict]:
    rows: list[dict] = []
    for line in _tail_lines(path, max_lines=max_lines, max_bytes=max_bytes):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _model_cfg() -> dict:
    return _read_json(WIRING_PATH, {}).get("model", {})


def _runtime_path(model: dict | None = None) -> pathlib.Path:
    model = model or _model_cfg()
    return _root_path(model.get("runtime_log_path"), "comms/runtime.ndjson")


def _usage_path(model: dict | None = None) -> pathlib.Path:
    model = model or _model_cfg()
    return _root_path(model.get("usage_log_path"), "comms/brain_usage.ndjson")


def _session_logs() -> list[dict]:
    paths = sorted((ROOT / "comms").glob("session-*.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return [_stat(p) for p in paths[:5]]


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ─── usage / compact state projection ───────────────────────────────────────

def _usage_rows(limit: int = 20000) -> list[dict]:
    return _tail_ndjson(_usage_path(), max_lines=limit, max_bytes=2_000_000)


def _usage_summary() -> dict:
    rows = _usage_rows()
    now = time.time()
    lt = time.localtime(now)
    month_start = time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))
    buckets = {
        "24h": lambda ts: ts >= now - 86400,
        "30d": lambda ts: ts >= now - 30 * 86400,
        "month": lambda ts: ts >= month_start,
        "all": lambda ts: True,
    }
    out = {name: {} for name in buckets}
    for row in rows:
        ts = _num(row.get("ts"), 0)
        transport = str(row.get("transport") or "unknown")
        model = str(row.get("model") or "")
        key = f"{transport} | {model}".strip()
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        total = usage.get("total_tokens", _num(prompt) + _num(completion))
        reasoning = 0
        for details_key in ("completion_tokens_details", "output_tokens_details"):
            d = usage.get(details_key)
            if isinstance(d, dict):
                reasoning += _num(d.get("reasoning_tokens"), 0)
        cost = row.get("cost_usd")
        if cost is None and usage.get("cost_in_usd_ticks") is not None:
            cost = _num(usage.get("cost_in_usd_ticks")) / 10_000_000_000
        for name, pred in buckets.items():
            if not pred(ts):
                continue
            cur = out[name].setdefault(key, {
                "transport": transport, "model": model, "calls": 0, "exact_calls": 0,
                "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
                "total_tokens": 0, "cost_usd": 0.0, "elapsed_s": 0.0, "notes": set(),
            })
            cur["calls"] += 1
            if row.get("exact_usage") or usage:
                cur["exact_calls"] += 1
            cur["prompt_tokens"] += int(_num(prompt, 0))
            cur["completion_tokens"] += int(_num(completion, 0))
            cur["reasoning_tokens"] += int(reasoning)
            cur["total_tokens"] += int(_num(total, 0))
            cur["cost_usd"] += _num(cost, 0.0)
            cur["elapsed_s"] += _num(row.get("elapsed_s"), 0.0)
            if row.get("note"):
                cur["notes"].add(str(row["note"]))
    for bucket in out.values():
        for cur in bucket.values():
            cur["notes"] = sorted(cur["notes"])
    return {"path": str(_usage_path()), "rows": len(rows), "buckets": out, "limits": _model_cfg().get("usage_limits", {})}


def _compact_state(state: dict) -> dict:
    plan = state.get("plan") if isinstance(state.get("plan"), list) else []
    history = state.get("history") if isinstance(state.get("history"), list) else []
    chain = state.get("reasoning_chain") if isinstance(state.get("reasoning_chain"), list) else []
    return {
        "goal": state.get("goal", ""),
        "node": state.get("_node", ""),
        "active_node": state.get("_active_node", state.get("_node", "")),
        "phase": state.get("_phase", ""),
        "transport": state.get("_transport", ""),
        "state_seq": state.get("_state_seq", 0),
        "saved_at": state.get("_saved_at", 0),
        "saved_at_iso": state.get("_saved_at_iso", ""),
        "pid": state.get("_pid", ""),
        "plan": plan[:30],
        "step": state.get("step", 0),
        "current_step": state.get("current_step", {}),
        "plan_complete": bool(state.get("plan_complete")),
        "satisfied": bool(state.get("satisfied")),
        "last_error": state.get("last_error", ""),
        "last_outcome": state.get("last_outcome", ""),
        "last_actions": state.get("last_actions", []),
        "verify_evidence": state.get("verify_evidence", ""),
        "verify_reason": state.get("verify_reason", ""),
        "history": history[-30:],
        "narration": (state.get("_narration") if isinstance(state.get("_narration"), list) else [])[-80:],
        "reasoning_chain": [
            {
                "circuit": x.get("circuit", "") if isinstance(x, dict) else "",
                "ts": x.get("ts", 0) if isinstance(x, dict) else 0,
                "reasoning": str(x.get("reasoning", ""))[:800] if isinstance(x, dict) else "",
                "parsed": x.get("parsed") if isinstance(x, dict) else None,
            }
            for x in chain[-20:]
        ],
        "screen_summary": _screen_summary(state),
    }


def _screen_summary(state: dict) -> dict:
    meta = state.get("screen_meta") if isinstance(state.get("screen_meta"), dict) else {}
    probe = meta.get("probe") if isinstance(meta.get("probe"), dict) else {}
    return {
        "focused_title": meta.get("focused_title") or state.get("post_action_title", ""),
        "elements": len(meta.get("elements") or []),
        "windows": len(meta.get("windows") or []),
        "raw_screen_chars": len(str(state.get("screen") or "")),
        "probe": {k: probe.get(k) for k in ("raw_nodes", "classified_nodes", "primary_found", "hover_scan_found")},
    }


def _normalize_wiring(wiring: dict) -> dict:
    model = wiring.setdefault("model", {})
    openai = model.get("openai") if isinstance(model.get("openai"), dict) else {}
    params = openai.get("parameters") if isinstance(openai.get("parameters"), dict) else {}
    for key in ("host", "model", "timeout"):
        if key in openai:
            model[key] = openai[key]
    for key in ("temperature", "temperature_bump", "top_p", "top_k", "repeat_penalty", "presence_penalty", "frequency_penalty", "max_tokens", "thinking"):
        if key in params:
            model[key] = params[key]
    model.setdefault("runtime_log_path", "comms/runtime.ndjson")
    model.setdefault("usage_log_path", "comms/brain_usage.ndjson")
    model.setdefault("brain_io_log_path", "comms/brain_io.ndjson")
    if isinstance(model.get("file_proxy"), dict):
        model["file_proxy"].setdefault("request_path", "comms/request.json")
        model["file_proxy"].setdefault("response_path", "comms/response.json")
    return wiring


def _status() -> dict:
    wiring = _read_json(WIRING_PATH, {})
    model = wiring.get("model", {}) if isinstance(wiring.get("model"), dict) else {}
    state = _read_json(STATE_PATH, {})
    state_stat = _stat(STATE_PATH)
    runtime_path = _runtime_path(model)
    usage_path = _usage_path(model)
    runtime_rows = _tail_ndjson(runtime_path, max_lines=200, max_bytes=800_000)
    last_runtime = runtime_rows[-1] if runtime_rows else {}
    now = time.time()
    state_age = state_stat["age_s"] if state_stat["age_s"] is not None else None
    runtime_stat = _stat(runtime_path)
    runtime_age = runtime_stat["age_s"] if runtime_stat["age_s"] is not None else None
    phase = str(state.get("_phase", "") or "")
    active = bool(phase not in ("rest", "stopped", "interrupted", "max_ticks", "") or (last_runtime.get("event") in ("brain_request", "cli_start", "node_start")))
    stale = bool(state_age is None or state_age > 8 and not active)
    return {
        "now": now,
        "now_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "state": _compact_state(state),
        "model": {
            "transport": model.get("transport", ""),
            "label": (model.get(model.get("transport", ""), {}) or {}).get("label", model.get("transport", "")) if isinstance(model.get(model.get("transport", ""), {}), dict) else model.get("transport", ""),
            "known_transports": [k for k in ("openai", "xai_responses", "opencode", "grok_build", "file_proxy", "browser_ai") if k in model or k in ("file_proxy", "browser_ai")],
        },
        "files": {
            "state": state_stat,
            "wiring": _stat(WIRING_PATH),
            "runtime": runtime_stat,
            "usage": _stat(usage_path),
            "sessions": _session_logs(),
        },
        "runtime": runtime_rows[-120:],
        "last_runtime_event": last_runtime,
        "health": {
            "active": active,
            "stale": stale,
            "state_age_s": state_age,
            "runtime_age_s": runtime_age,
            "message": _health_message(active, stale, state_age, runtime_age, last_runtime),
        },
        "usage": _usage_summary(),
    }


def _health_message(active: bool, stale: bool, state_age: float | None, runtime_age: float | None, last_event: dict) -> str:
    if active:
        return f"live: {last_event.get('event', 'state')}"
    if stale:
        return f"stale: state age {state_age:.1f}s" if isinstance(state_age, (int, float)) else "stale: no state file"
    return "current"


# ─── provider diagnostics ──────────────────────────────────────────────────

def _candidate_exes(name: str) -> list[str]:
    import shutil
    expanded = os.path.expandvars(os.path.expanduser(str(name or ""))).strip()
    if not expanded:
        return []
    names = [expanded]
    if os.name == "nt" and not pathlib.Path(expanded).suffix:
        names += [expanded + ext for ext in (".exe", ".cmd", ".bat", ".ps1")]
    out = []
    for n in names:
        hit = shutil.which(n)
        if hit and hit not in out:
            out.append(hit)
    return out


def _provider_stats(provider: str) -> dict:
    model = _model_cfg()
    if provider == "opencode":
        cfg = model.get("opencode") if isinstance(model.get("opencode"), dict) else {}
        exe = str(cfg.get("exe") or "opencode")
        hits = _candidate_exes(exe)
        if not hits:
            return {"ok": False, "error": f"OpenCode executable not found for {exe!r}. Install OpenCode or set model.opencode.exe to full opencode.cmd/opencode.exe path.", "candidates": []}
        cmd = [hits[0], "stats", "--days", "30", "--models", "10"]
    elif provider == "grok_build":
        cfg = model.get("grok_build") if isinstance(model.get("grok_build"), dict) else {}
        exe = str(cfg.get("exe") or "grok")
        hits = _candidate_exes(exe)
        if not hits:
            return {"ok": False, "error": f"Grok executable not found for {exe!r}.", "candidates": []}
        cmd = [hits[0], "models"]
    else:
        return {"ok": False, "error": "provider stats implemented for opencode and grok_build"}
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=20)
    except Exception as e:
        return {"ok": False, "error": f"{provider} stats failed: {e}", "cmd": cmd}
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    return {"ok": proc.returncode == 0, "stdout": out, "stderr": err, "returncode": proc.returncode, "cmd": cmd}


# ─── HTML ──────────────────────────────────────────────────────────────────

PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>endgame-ai live workbench</title>
<style>
:root{--bg:#090d13;--fg:#d6deeb;--mut:#8291a7;--panel:#111827;--bd:#263244;--ac:#63b3ff;--ok:#4ade80;--warn:#fbbf24;--err:#fb7185;--hot:#c084fc}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace} header{position:sticky;top:0;z-index:5;background:#0b111a;border-bottom:1px solid var(--bd);padding:10px 14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap} b{color:var(--ac)} .pill{border:1px solid var(--bd);border-radius:999px;padding:3px 9px;color:var(--mut);white-space:nowrap}.ok{color:var(--ok);border-color:var(--ok)}.warn{color:var(--warn);border-color:var(--warn)}.err{color:var(--err);border-color:var(--err)}.hot{color:var(--hot);border-color:var(--hot)}
main{display:grid;grid-template-columns:1.05fr .95fr;gap:12px;padding:12px}.panel{background:var(--panel);border:1px solid var(--bd);border-radius:10px;padding:10px;min-height:80px;overflow:auto;max-height:50vh}.full{grid-column:1/3}.panel h2{margin:0 0 8px;color:var(--mut);font-size:11px;letter-spacing:.08em;text-transform:uppercase}.row{padding:5px 0;border-bottom:1px solid #1f2937;white-space:pre-wrap;word-break:break-word}.mut{color:var(--mut)}.k{color:var(--ac)}.bad{color:var(--err)}.good{color:var(--ok)}.mono{font-family:inherit} textarea{width:100%;min-height:120px;background:#0b111a;color:var(--fg);border:1px solid var(--bd);border-radius:8px;padding:8px;font:12px/1.4 ui-monospace,monospace} input,select{background:#0b111a;color:var(--fg);border:1px solid var(--bd);border-radius:7px;padding:6px} input[type=range]{width:220px;padding:0} input[type=checkbox]{width:auto}button{background:var(--ac);color:#07111f;border:0;border-radius:7px;padding:7px 11px;font-weight:700;cursor:pointer;margin:3px 5px 3px 0}button.alt{background:#1f2937;color:var(--fg);border:1px solid var(--bd)}button.danger{background:var(--err);color:#111}.grid{display:grid;grid-template-columns:190px 1fr 110px;gap:8px;align-items:center}.usage table{width:100%;border-collapse:collapse}.usage th,.usage td{border-bottom:1px solid #1f2937;padding:4px 6px;text-align:left}.usage th{font-weight:400;color:var(--mut)} details{margin-top:8px}.bar{height:6px;background:#1f2937;border-radius:8px;overflow:hidden}.bar span{display:block;height:6px;background:var(--ac);width:0%}
</style></head><body>
<header><b>endgame-ai</b><span id="health" class="pill">health: –</span><span id="node" class="pill">node: –</span><span id="brain" class="pill hot">brain: –</span><span id="goal" class="pill">goal: –</span><span id="age" class="pill">age: –</span><span id="seq" class="pill">seq: –</span><button class="alt" onclick="paused=!paused;this.textContent=paused?'Resume':'Pause'">Pause</button><span class="mut" id="now" style="margin-left:auto">–</span></header>
<main>
<section class="panel"><h2>Live event stream</h2><div id="events"></div></section>
<section class="panel"><h2>Current state truth</h2><div id="truth"></div></section>
<section class="panel"><h2>Plan</h2><div id="plan"></div></section>
<section class="panel"><h2>History + outcome</h2><div id="history"></div></section>
<section class="panel"><h2>Reasoning chain</h2><div id="reasoning"></div></section>
<section class="panel"><h2>Files / purpose</h2><div id="files"></div></section>
<section class="panel full"><h2>Brain provider + parameters</h2><div class="row mut">This edits wiring.json. The organism notices wiring mtime and rebinds its brain on the next loop. OpenCode defaults to prompt_mode=file to avoid Windows command-length and PATH shim failures.</div><div style="margin:8px 0"><select id="brainSelect" onchange="renderBrainControls()"></select> <button onclick="saveBrain()">Save brain</button> <button class="alt" onclick="probe('opencode')">Probe OpenCode</button> <button class="alt" onclick="probe('grok_build')">Probe Grok</button> <span id="saveStatus" class="mut"></span></div><div id="brainControls" class="grid"></div><pre id="probeOut" class="row mut"></pre></section>
<section class="panel"><h2>File proxy handoff</h2><div id="proxyMeta" class="row mut">–</div><textarea id="prompt" readonly></textarea><textarea id="answer" placeholder="human/other brain response"></textarea><button onclick="respond()">Write response.json</button></section>
<section class="panel"><h2>Goal</h2><textarea id="goalbox" placeholder="writes goal.json for next run"></textarea><button onclick="setGoal()">Set goal</button><button class="alt" onclick="setGoal('')">Clear goal</button></section>
<section class="panel full usage"><h2>Usage ledger</h2><div id="usageMeta" class="row mut">–</div><div id="usage"></div></section>
</main>
<script>
const $=id=>document.getElementById(id); let wiring=null, status=null, paused=false, inflight=null;
const transports=['openai','xai_responses','opencode','grok_build','file_proxy','browser_ai'];
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function rows(el,items,fmt){el.innerHTML=(items||[]).map(fmt).join('')||'<div class="row mut">–</div>';}
function fmt(n){return Number(n||0).toLocaleString(undefined,{maximumFractionDigits:3})}
function age(s){return s==null?'–':fmt(s)+'s'}
function getPath(obj,path){return String(path).split('.').reduce((a,k)=>a&&a[k],obj)}
function setPath(obj,path,val){const p=String(path).split('.');let c=obj;for(let i=0;i<p.length-1;i++){c[p[i]]=c[p[i]]||{};c=c[p[i]]}c[p[p.length-1]]=val}
function parseVal(control, el){ if(control.type==='checkbox') return !!el.checked; if(control.type==='number'||control.type==='range'){ const n=Number(el.value); return Number.isFinite(n)?n:0; } return el.value; }
async function api(path, opts={}){ const r=await fetch(path,{cache:'no-store',...opts}); if(!r.ok) throw new Error(await r.text()); return await r.json(); }
async function loadWiring(){ wiring=await api('/api/wiring'); const m=wiring.model||{}; const sel=$('brainSelect'); sel.innerHTML=''; transports.filter(t=>m[t]||['file_proxy','browser_ai'].includes(t)).forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=(m[t]&&m[t].label)?m[t].label:t;sel.appendChild(o)}); sel.value=m.transport||'openai'; renderBrainControls(); }
function renderBrainControls(){ if(!wiring)return; const m=wiring.model||{}; const t=$('brainSelect').value; const cfg=m[t]||{}; const controls=cfg.controls||[]; let html=''; controls.forEach((c,i)=>{ const id='ctl_'+i; const v=getPath(cfg,c.key); let input=''; if(c.type==='select'){ input=`<select id="${id}">${(c.choices||[]).map(x=>`<option ${x==v?'selected':''}>${esc(x)}</option>`).join('')}</select>`; } else if(c.type==='checkbox'){ input=`<input id="${id}" type="checkbox" ${v?'checked':''}>`; } else { input=`<input id="${id}" type="${c.type||'text'}" value="${esc(v??'')}" ${c.min!==undefined?'min="'+c.min+'"':''} ${c.max!==undefined?'max="'+c.max+'"':''} ${c.step!==undefined?'step="'+c.step+'"':''}>`; } html+=`<label class="mut">${esc(c.label||c.key)}</label><div>${input}</div><div class="mut">${esc(c.key)}</div>`; }); $('brainControls').innerHTML=html||'<div class="row mut">No control schema for this provider.</div>'; }
async function saveBrain(){ const m=wiring.model||{}; const t=$('brainSelect').value; const cfg=m[t]||{}; (cfg.controls||[]).forEach((c,i)=>{const el=$('ctl_'+i); if(el) setPath(cfg,c.key,parseVal(c,el));}); m.transport=t; m[t]=cfg; wiring.model=m; const r=await api('/api/wiring',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(wiring)}); $('saveStatus').textContent=r.ok?'saved to wiring.json':'save failed'; await tick(true); }
function eventLine(e){ const cls=e.event&&e.event.includes('error')?'bad':(e.event==='usage'?'good':'k'); return `<div class="row"><span class="${cls}">${esc(e.iso||'')} ${esc(e.event||'event')}</span> <span class="mut">${esc(e.transport||e.node||'')}</span><br>${esc(e.message||e.error||e.content_preview||e.stderr_preview||e.stdout_preview||JSON.stringify(e).slice(0,400))}</div>` }
function renderStatus(s){ status=s; const h=s.health||{}, st=s.state||{}; $('health').textContent='health: '+(h.message||'–'); $('health').className='pill '+(h.stale?'err':h.active?'warn':'ok'); $('node').textContent='node: '+(st.active_node||st.node||'–')+' / '+(st.phase||''); $('brain').textContent='brain: '+(st.transport||s.model?.transport||'–'); $('goal').textContent='goal: '+(st.goal||'(none)'); $('age').textContent='state age: '+age(h.state_age_s); $('seq').textContent='seq: '+(st.state_seq||0); $('now').textContent=s.now_iso||new Date().toLocaleTimeString();
rows($('events'),(s.runtime||[]).slice().reverse().slice(0,80),eventLine);
$('truth').innerHTML=`<div class="row"><span class="k">current step</span><br>${esc(st.current_step?.description||'–')}<br><span class="mut">done_when: ${esc(st.current_step?.done_when||'')}</span></div><div class="row"><span class="k">last outcome</span><br>${esc(st.last_outcome||'–')}</div><div class="row"><span class="${st.last_error?'bad':'good'}">last error</span><br>${esc(st.last_error||'none')}</div><div class="row"><span class="k">screen summary</span><br>focused=${esc(st.screen_summary?.focused_title||'–')} • elements=${fmt(st.screen_summary?.elements)} • windows=${fmt(st.screen_summary?.windows)} • chars=${fmt(st.screen_summary?.raw_screen_chars)}</div><div class="row"><span class="k">verify</span><br>${esc(st.verify_evidence||'–')}<br><span class="mut">${esc(st.verify_reason||'')}</span></div>`;
rows($('plan'),st.plan,(x,i)=>`<div class="row"><span class="${i==Number(st.step)?'hot':'k'}">${i+1}.</span> ${esc(x.description||'')}<br><span class="mut">done_when: ${esc(x.done_when||'')}</span></div>`);
rows($('history'),(st.history||[]).slice().reverse(),x=>`<div class="row"><span class="${String(x.outcome||'').toUpperCase().startsWith('FAILED')?'bad':'good'}">${esc(x.action||'')}</span><br><span class="mut">${esc(x.outcome||'')}</span></div>`);
rows($('reasoning'),(st.reasoning_chain||[]).slice().reverse(),x=>`<div class="row"><span class="k">${esc(x.circuit||'')}</span> <span class="mut">${x.ts?new Date(x.ts*1000).toLocaleTimeString():''}</span><br>${esc((x.reasoning||'').slice(0,800))}<details><summary>parsed</summary><pre>${esc(JSON.stringify(x.parsed,null,2))}</pre></details></div>`);
const f=s.files||{}; $('files').innerHTML=['state','runtime','usage','wiring'].map(k=>{const v=f[k]||{};return `<div class="row"><span class="k">${k}</span> ${esc(v.path||'')}<br><span class="mut">exists=${!!v.exists} size=${fmt(v.size)} age=${age(v.age_s)}</span></div>`}).join('')+`<div class="row"><span class="k">session logs</span><br>${(f.sessions||[]).map(x=>esc(x.path)+' age='+age(x.age_s)+' size='+fmt(x.size)).join('\n')||'–'}</div><div class="row mut">state.json = current snapshot; runtime.ndjson = compact live events; brain_usage.ndjson = token/cost ledger; session-*.log = raw forensic prompt/response; brain_io.ndjson = optional raw transport JSON, disabled by default.</div>`;
renderUsage(s.usage||{});
}
function renderUsage(u){ $('usageMeta').textContent=`rows: ${u.rows||0} • ${u.path||''}`; let html=''; for(const period of ['24h','30d','month','all']){ const b=u.buckets&&u.buckets[period]||{}; html+=`<h3>${period}</h3><table><tr><th>provider/model</th><th>calls</th><th>exact</th><th>prompt</th><th>completion</th><th>reasoning</th><th>total</th><th>elapsed</th><th>cost</th><th>notes</th></tr>`; for(const [k,v] of Object.entries(b)){ html+=`<tr><td>${esc(k)}</td><td>${fmt(v.calls)}</td><td>${fmt(v.exact_calls)}</td><td>${fmt(v.prompt_tokens)}</td><td>${fmt(v.completion_tokens)}</td><td>${fmt(v.reasoning_tokens)}</td><td>${fmt(v.total_tokens)}</td><td>${fmt(v.elapsed_s)}s</td><td>$${fmt(v.cost_usd)}</td><td>${esc((v.notes||[]).join('; '))}</td></tr>`; } html+='</table>'; } $('usage').innerHTML=html; }
async function tick(force=false){ if(paused&&!force)return; if(inflight) inflight.abort(); inflight=new AbortController(); try{ renderStatus(await api('/api/status',{signal:inflight.signal})); const p=await api('/api/proxy',{signal:inflight.signal}); $('proxyMeta').textContent=p.pending?`WAITING id=${p.id||''}`:'idle'; $('proxyMeta').className='row '+(p.pending?'bad':'mut'); $('prompt').value=p.prompt||''; }catch(e){ if(e.name!=='AbortError') $('health').textContent='health: panel fetch error '+e.message; } finally{ inflight=null; } }
async function respond(){await api('/api/respond',{method:'POST',body:$('answer').value});$('answer').value='';tick(true);}
async function setGoal(v){const g=v===''?'':$('goalbox').value;await api('/api/goal',{method:'POST',body:g});tick(true);}
async function probe(provider){ const obj=await api('/api/provider_stats?provider='+encodeURIComponent(provider)); $('probeOut').textContent=JSON.stringify(obj,null,2); }
loadWiring().then(()=>tick(true)); setInterval(()=>tick(false),1000);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_a):
        pass

    def _body(self) -> str:
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/status":
            return self._send(200, json.dumps(_status(), ensure_ascii=False, default=str))
        if path == "/api/state/raw":
            return self._send(200, json.dumps(_read_json(STATE_PATH, {}), ensure_ascii=False, default=str))
        if path == "/api/wiring":
            return self._send(200, json.dumps(_read_json(WIRING_PATH, {}), ensure_ascii=False, default=str))
        if path == "/api/usage":
            return self._send(200, json.dumps(_usage_summary(), ensure_ascii=False, default=str))
        if path == "/api/provider_stats":
            qs = parse_qs(parsed.query)
            provider = (qs.get("provider") or [""])[0]
            return self._send(200, json.dumps(_provider_stats(provider), ensure_ascii=False, default=str))
        if path == "/api/proxy":
            model = _model_cfg()
            fp = model.get("file_proxy", {})
            req = _read_json(_root_path(fp.get("request_path"), "comms/request.json"), {})
            pending = bool(req) and req.get("status") == "pending"
            prompt = ""
            if pending:
                msgs = req.get("messages", [])
                prompt = "\n\n".join(f"[{m.get('role')}]\n{m.get('content','')}" for m in msgs)
            return self._send(200, json.dumps({"pending": pending, "id": req.get("id"), "prompt": prompt}, ensure_ascii=False))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        body = self._body()
        if self.path == "/api/respond":
            model = _model_cfg()
            fp = model.get("file_proxy", {})
            req = _read_json(_root_path(fp.get("request_path"), "comms/request.json"), {})
            resp_path = _root_path(fp.get("response_path"), "comms/response.json")
            _write_json(resp_path, {"id": req.get("id"), "content": body})
            return self._send(200, '{"ok":true}')
        if self.path == "/api/goal":
            _write_json(GOAL_PATH, {"goal": body})
            return self._send(200, '{"ok":true}')
        if self.path == "/api/wiring":
            try:
                wiring = json.loads(body or "{}")
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            wiring = _normalize_wiring(wiring)
            _write_json(WIRING_PATH, wiring)
            return self._send(200, '{"ok":true}')
        return self._send(404, json.dumps({"error": "not found"}))


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"workbench on http://localhost:{PORT}  (Ctrl+C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
