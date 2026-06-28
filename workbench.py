"""workbench — a minimal, dependency-free human+AI debug/control surface.

Run alongside the organism:  python workbench.py    (then open http://localhost:8800)

It serves one HTML page and a few JSON endpoints that read the organism's live files:
  - state.json        current state, plan, history, narration, reasoning chain, transport
  - comms/request.json + comms/response.json   the file_proxy brain handoff

It lets a human (or an AI operator) DEBUG and CONTROL without touching the loop:
  - watch the organism think and act in near-real-time
  - read the pending file_proxy request and write a response (acting as the swapped brain)
  - set a goal for the next run (writes goal.json, which the organism can pick up)

No frameworks, no build step. stdlib http.server only.
"""
from __future__ import annotations

import json
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).parent.resolve()
PORT = 8800


def _read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>endgame-ai workbench</title>
<style>
 :root{--bg:#0d1117;--fg:#c9d1d9;--mut:#8b949e;--ac:#58a6ff;--ok:#3fb950;--err:#f85149;--pnl:#161b22;--bd:#30363d}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 ui-monospace,Menlo,Consolas,monospace}
 header{padding:10px 16px;border-bottom:1px solid var(--bd);display:flex;gap:16px;align-items:center}
 header b{color:var(--ac)} .pill{padding:2px 8px;border:1px solid var(--bd);border-radius:10px;color:var(--mut)}
 .pill.core{color:var(--ok);border-color:var(--ok)}
 main{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}
 .panel{background:var(--pnl);border:1px solid var(--bd);border-radius:8px;padding:10px;min-height:80px;overflow:auto;max-height:46vh}
 .panel h2{margin:0 0 8px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
 .row{padding:3px 0;border-bottom:1px solid #21262d;white-space:pre-wrap;word-break:break-word}
 .k{color:var(--ac)} .mut{color:var(--mut)} .ok{color:var(--ok)} .err{color:var(--err)}
 textarea{width:100%;height:120px;background:#0d1117;color:var(--fg);border:1px solid var(--bd);border-radius:6px;font:12px ui-monospace,monospace;padding:6px}
 input{background:#0d1117;color:var(--fg);border:1px solid var(--bd);border-radius:6px;padding:6px;width:70%}
 button{background:var(--ac);color:#0d1117;border:0;border-radius:6px;padding:7px 12px;font-weight:600;cursor:pointer}
 button.alt{background:#21262d;color:var(--fg);border:1px solid var(--bd)}
 .full{grid-column:1/3}
</style></head><body>
<header><b>endgame-ai</b> <span id="node" class="pill">node: –</span>
 <span id="transport" class="pill core">brain: –</span>
 <span id="goal" class="pill">goal: –</span>
 <span id="proxy" class="pill">proxy: idle</span>
 <span class="mut" style="margin-left:auto" id="tick">–</span></header>
<main>
 <div class="panel"><h2>Narration</h2><div id="narration"></div></div>
 <div class="panel"><h2>Plan</h2><div id="plan"></div></div>
 <div class="panel"><h2>History</h2><div id="history"></div></div>
 <div class="panel"><h2>Reasoning chain</h2><div id="reasoning"></div></div>
 <div class="panel full"><h2>file_proxy brain handoff — answer as the brain</h2>
   <div id="reqmeta" class="mut"></div>
   <div class="row mut">SYSTEM+USER prompt the organism is waiting on:</div>
   <textarea id="prompt" readonly></textarea>
   <div class="row mut">Your response (JSON record the circuit expects, e.g. {"record_type":"action",...}):</div>
   <textarea id="answer"></textarea>
   <div style="margin-top:8px"><button onclick="respond()">Send as brain</button></div>
 </div>
 <div class="panel full"><h2>Control</h2>
   <input id="goalbox" placeholder="set a goal for the next run (writes goal.json)"/>
   <button onclick="setGoal()">Set goal</button>
   <button class="alt" onclick="setGoal('')">Clear goal</button>
 </div>
</main>
<script>
const $=id=>document.getElementById(id);
function rows(el,items,fmt){el.innerHTML=(items||[]).map(fmt).join('')||'<div class="row mut">–</div>';}
async function tick(){
 const s=await (await fetch('/state')).json();
 $('node').textContent='node: '+(s._node||'–');
 $('transport').textContent='brain: '+(s._transport||'–');
 $('goal').textContent='goal: '+(s.goal||'(none)');
 $('tick').textContent=new Date().toLocaleTimeString();
 rows($('narration'),(s._narration||[]).slice().reverse(),x=>`<div class="row">${esc(x)}</div>`);
 rows($('plan'),s.plan,(x,i)=>`<div class="row"><span class="k">${i+1}.</span> ${esc(x.description||'')}<br><span class="mut">done_when: ${esc(x.done_when||'')}</span></div>`);
 rows($('history'),(s.history||[]).slice().reverse(),x=>`<div class="row"><span class="${(x.outcome||'').toUpperCase().startsWith('FAILED')?'err':'ok'}">${esc(x.action||'')}</span><br><span class="mut">${esc(x.outcome||'')}</span></div>`);
 rows($('reasoning'),(s.reasoning_chain||[]).slice().reverse(),x=>`<div class="row"><span class="k">${esc(x.circuit||'')}</span> ${esc((x.reasoning||'').slice(0,400))}</div>`);
 const p=await (await fetch('/proxy')).json();
 $('proxy').textContent='proxy: '+(p.pending?'WAITING':'idle');
 $('proxy').className='pill'+(p.pending?' err':'');
 if(p.pending){$('reqmeta').textContent='id '+(p.id||'')+'  •  waiting for a brain to answer';$('prompt').value=p.prompt||'';}
 else{$('reqmeta').textContent='no pending request';$('prompt').value='';}
}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function respond(){await fetch('/respond',{method:'POST',body:$('answer').value});$('answer').value='';tick();}
async function setGoal(v){const g=v===''?'':$('goalbox').value;await fetch('/goal',{method:'POST',body:g});tick();}
setInterval(tick,1500);tick();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/state":
            return self._send(200, json.dumps(_read_json(ROOT / "state.json", {})))
        if self.path == "/proxy":
            model = _read_json(ROOT / "wiring.json", {}).get("model", {})
            fp = model.get("file_proxy", {})
            req = _read_json(ROOT / fp.get("request_path", "comms/request.json"), {})
            pending = bool(req) and req.get("status") == "pending"
            prompt = ""
            if pending:
                msgs = req.get("messages", [])
                prompt = "\n\n".join(f"[{m.get('role')}]\n{m.get('content','')}" for m in msgs)
            return self._send(200, json.dumps({"pending": pending, "id": req.get("id"), "prompt": prompt}))
        return self._send(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n).decode("utf-8") if n else ""
        if self.path == "/respond":
            model = _read_json(ROOT / "wiring.json", {}).get("model", {})
            fp = model.get("file_proxy", {})
            req = _read_json(ROOT / fp.get("request_path", "comms/request.json"), {})
            resp_path = ROOT / fp.get("response_path", "comms/response.json")
            resp_path.parent.mkdir(parents=True, exist_ok=True)
            resp_path.write_text(json.dumps({"id": req.get("id"), "content": body}, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._send(200, '{"ok":true}')
        if self.path == "/goal":
            (ROOT / "goal.json").write_text(json.dumps({"goal": body}, ensure_ascii=False), encoding="utf-8")
            return self._send(200, '{"ok":true}')
        return self._send(404, "{}")


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"workbench on http://localhost:{PORT}  (Ctrl+C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
