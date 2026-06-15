"""bench.py - LLM benchmark: 30 scenarios, configurable model/params, parallel execution."""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.resolve()

SCENARIOS: list[dict[str, Any]] = [
    {"name": "plan_open_notepad", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Open notepad on windows and write hello\nPRESSURE: stag=0.000 pwr=1.000\nDESKTOP_FOCUSED: Program Manager\nPlan JSON:"},
    {"name": "plan_chrome_youtube", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Open Chrome and play Shakira She Wolf on YouTube\nPRESSURE: stag=0.100 pwr=0.900\nDESKTOP_FOCUSED: Program Manager\nPlan JSON:"},
    {"name": "plan_file_write", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Create a file called notes.txt with today's date\nPRESSURE: stag=0.000 pwr=1.000\nPlan JSON:"},
    {"name": "plan_git_status", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Check git status and report uncommitted files\nPRESSURE: stag=0.200 pwr=0.800\nPlan JSON:"},
    {"name": "plan_navigate_url", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Open Firefox and navigate to github.com\nPRESSURE: stag=0.000 pwr=1.000\nDESKTOP_FOCUSED: Program Manager\nPlan JSON:"},
    {"name": "plan_compile_check", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: py_compile all .py files in the project and report errors\nPRESSURE: stag=0.050 pwr=0.950\nPlan JSON:"},
    {"name": "plan_read_config", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Read config.py and summarize the model profiles\nPRESSURE: stag=0.000 pwr=1.000\nPlan JSON:"},
    {"name": "plan_fix_bug", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Find and fix the typo in engine.py line 176\nPRESSURE: stag=0.400 pwr=0.600\nHISTORY: [{\"ok\":false,\"obs\":\"UnboundLocalError: goal\"}]\nPlan JSON:"},
    {"name": "plan_route_notepad", "role": "planner",
     "system": "You are the ONLY rod that receives human goals. You are the thalamus.\nRunning on Windows 11, working dir: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nDECOMPOSE goal into subtasks, ROUTE each to a worker via bus_route().",
     "user": "ACTIVE_TASK: Open notepad and write a poem about AI\nPlan JSON:"},
    {"name": "plan_route_deploy", "role": "planner",
     "system": "You are the ONLY rod that receives human goals. You are the thalamus.\nRunning on Windows 11, working dir: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nDECOMPOSE goal into subtasks, ROUTE each to a worker via bus_route().",
     "user": "ACTIVE_TASK: Commit all changes and push to remote\nPlan JSON:"},
    {"name": "actor_click_edit", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Click on the text edit area\nSCREEN:\n  [1] Notepad - \"hello - Notepad\" (window)\n  [2] Edit area (edit, value=\"\")\n  [3] File menu (menuitem)\n  [4] Edit menu (menuitem)\nJSON:"},
    {"name": "actor_click_button", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Click the search button\nSCREEN:\n  [1] Chrome - \"Google\" (window)\n  [2] Address bar (edit, value=\"google.com\")\n  [3] Google Search (button)\n  [4] I'm Feeling Lucky (button)\nJSON:"},
    {"name": "actor_type_text", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Type 'hello world' into the search box\nSCREEN:\n  [1] Chrome - \"Google\" (window)\n  [2] Search box (edit, value=\"\", focused)\nJSON:"},
    {"name": "actor_scroll_down", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Scroll down to see more results\nSCREEN:\n  [1] Chrome - \"Search Results\" (window)\n  [2] Result 1 (link)\n  [3] Result 2 (link)\nJSON:"},
    {"name": "actor_already_done", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Open notepad\nSCREEN:\n  [1] Notepad - \"Untitled - Notepad\" (window, focused)\n  [2] Edit area (edit)\nJSON:"},
    {"name": "actor_impossible", "role": "actor",
     "system": "You control a real Windows 11 desktop via UI Automation.\nRead SCREEN element IDs. Match INSTRUCTION. Emit one verb.",
     "user": "INSTRUCTION: Click the Save button\nSCREEN:\n  [1] Notepad - \"Untitled\" (window)\n  [2] Edit area (edit)\n  [3] File (menuitem)\nJSON:"},
    {"name": "verify_success", "role": "verifier",
     "system": "Confirm if STEP RESULTS contain print output proving DONE_WHEN was achieved.\nDeny only if results are empty or clearly contradict.",
     "user": "DONE_WHEN: Notepad is open with hello written\nSTEP RESULTS:\n  typed 5 chars\n  Hello written\nDESKTOP: focused=\"hello - Notepad\"\nJSON:"},
    {"name": "verify_fail_empty", "role": "verifier",
     "system": "Confirm if STEP RESULTS contain print output proving DONE_WHEN was achieved.\nDeny only if results are empty or clearly contradict.",
     "user": "DONE_WHEN: File saved to disk\nSTEP RESULTS:\n  (empty)\nJSON:"},
    {"name": "verify_partial", "role": "verifier",
     "system": "Confirm if STEP RESULTS contain print output proving DONE_WHEN was achieved.\nDeny only if results are empty or clearly contradict.",
     "user": "DONE_WHEN: Chrome playing YouTube video\nSTEP RESULTS:\n  Chrome opened\n  Navigated to youtube.com\nDESKTOP: focused=\"YouTube - Google Chrome\"\nJSON:"},
    {"name": "verify_wrong_window", "role": "verifier",
     "system": "Confirm if STEP RESULTS contain print output proving DONE_WHEN was achieved.\nDeny only if results are empty or clearly contradict.",
     "user": "DONE_WHEN: Notepad has text\nSTEP RESULTS:\n  desktop_write called\nDESKTOP: focused=\"Program Manager\"\nJSON:"},
    {"name": "fission_credit", "role": "fission_judge",
     "system": "Award fission credit if verifier confirmed AND concrete evidence exists.\nDeny only if: repeat of previous fission, OR no verifiable action happened.",
     "user": "VERIFIER: confirmed, evidence=\"typed 5 chars Hello written\"\nCOMPLETED: Notepad window contains hello\nPREVIOUS_FISSIONS: []\nJSON:"},
    {"name": "fission_deny_repeat", "role": "fission_judge",
     "system": "Award fission credit if verifier confirmed AND concrete evidence exists.\nDeny only if: repeat of previous fission, OR no verifiable action happened.",
     "user": "VERIFIER: confirmed, evidence=\"file exists\"\nCOMPLETED: Created notes.txt\nPREVIOUS_FISSIONS: [\"Created notes.txt\"]\nJSON:"},
    {"name": "reflect_wrong_path", "role": "reflector",
     "system": "After a denial: short diagnosis, one simpler next-step suggestion, optional one-line rule.",
     "user": "DENIED STEP: write_file /tmp/notes.txt\nERROR: FileNotFoundError: /tmp/notes.txt\nJSON:"},
    {"name": "reflect_timeout", "role": "reflector",
     "system": "After a denial: short diagnosis, one simpler next-step suggestion, optional one-line rule.",
     "user": "DENIED STEP: desktop_click([5])\nERROR: Element not found after 5s timeout\nJSON:"},
    {"name": "reflect_wrong_element", "role": "reflector",
     "system": "After a denial: short diagnosis, one simpler next-step suggestion, optional one-line rule.",
     "user": "DENIED STEP: click File menu to save\nERROR: Clicked [3] but no save dialog appeared\nHISTORY: tried 2 times\nJSON:"},
    {"name": "mutate_patch_prompt", "role": "mutator",
     "system": "Under pressure: choose ONE action: patch_plugin, patch_prompt, or none.\nFor patch_prompt: content = full new prompt text.",
     "user": "GOAL: Open notepad and write hello\nREFLECTION: {\"diagnosis\":\"wrong window focus\",\"suggestion\":\"use subprocess to open\"}\nPLUGINS: fission_log, comms_beacon\nMutation JSON:"},
    {"name": "mutate_none", "role": "mutator",
     "system": "Under pressure: choose ONE action: patch_plugin, patch_prompt, or none.\nFor patch_prompt: content = full new prompt text.",
     "user": "GOAL: Check git status\nREFLECTION: {\"diagnosis\":\"first attempt, minor issue\",\"suggestion\":\"retry\"}\nPLUGINS: fission_log, comms_beacon\nMutation JSON:"},
    {"name": "plan_long_history", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Open notepad and write hello\nPRESSURE: stag=0.500 pwr=0.500\nHISTORY: [{\"ok\":false,\"obs\":\"timeout\"},{\"ok\":false,\"obs\":\"wrong window\"},{\"ok\":true,\"obs\":\"opened\"},{\"ok\":false,\"obs\":\"element not found\"}]\nDESKTOP_FOCUSED: Program Manager\nPlan JSON:"},
    {"name": "plan_with_bus", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Write a poem in notepad\nOTHERS WORKING ON (do not duplicate):\n  @architect: Navigate to notepad\n  @devops: git commit\nPlan JSON:"},
    {"name": "plan_empty_screen", "role": "planner",
     "system": "You are a living organism rod on Windows 11.\nWorking directory: C:\\Users\\ewojgab\\Downloads\\endgame-ai\nPlan one small step. Output JSON with sequence array of {code:...} items.",
     "user": "ACTIVE_TASK: Find and open calculator\nPRESSURE: stag=0.000 pwr=1.000\nDESKTOP_FOCUSED: (unknown)\nDESKTOP_ERROR: UIA timeout\nPlan JSON:"},
]


def _build_body(s: dict, temperature: float, max_tokens: int) -> dict[str, Any]:
    return {"messages": [{"role": "system", "content": s["system"]}, {"role": "user", "content": s["user"]}],
            "temperature": temperature, "max_tokens": max_tokens}


def _run_one(s: dict, host: str, temperature: float, max_tokens: int, timeout: int) -> dict[str, Any]:
    body = _build_body(s, temperature, max_tokens)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{host}/v1/chat/completions", data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        lat = int((time.time() - t0) * 1000)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        return {"name": s["name"], "ok": True, "latency_ms": lat, "content": content,
                "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)}
    except Exception as e:
        return {"name": s["name"], "ok": False, "latency_ms": int((time.time() - t0) * 1000), "content": "", "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Benchmark - 30 scenarios")
    parser.add_argument("--host", default="http://localhost:1234")
    parser.add_argument("--temperature", type=float, default=0.12)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--concurrent", type=int, default=1)
    parser.add_argument("--scenarios", type=str, default="all", help="Comma-sep names or 'all'")
    parser.add_argument("--output", type=str, default="test.txt")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for i, s in enumerate(SCENARIOS, 1):
            print(f"  {i:2d}. {s['name']:30s} role={s['role']}")
        sys.exit(0)

    targets = SCENARIOS if args.scenarios == "all" else [s for s in SCENARIOS if s["name"] in {n.strip() for n in args.scenarios.split(",")}]
    if not targets: print("No matching scenarios. Use --list"); sys.exit(1)

    print(f"BENCH | {len(targets)} scenarios | concurrent={args.concurrent} | temp={args.temperature} max_tokens={args.max_tokens}")
    print(f"  host: {args.host}\n  output: {args.output}\n")

    results: list[dict] = []
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrent) as pool:
        futures = {pool.submit(_run_one, s, args.host, args.temperature, args.max_tokens, args.timeout): s for s in targets}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            st = "OK" if r["ok"] else "XX"
            print(f"  {st} {r['name']:30s} {r['latency_ms']:5d}ms {r.get('completion_tokens',0):3d}tok  {r['content'][:60]}")

    total_time = int(time.time() - t_start)
    ok_count = sum(1 for r in results if r["ok"])
    avg_lat = sum(r["latency_ms"] for r in results) // max(len(results), 1)
    print(f"\n{'='*60}\nDONE: {ok_count}/{len(results)} ok | avg={avg_lat}ms | total={total_time}s")

    out = Path(args.output)
    with out.open("w", encoding="utf-8") as f:
        f.write(f"BENCH {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"host={args.host} temp={args.temperature} max_tokens={args.max_tokens} concurrent={args.concurrent}\n")
        f.write(f"passed={ok_count}/{len(results)} avg_latency={avg_lat}ms total={total_time}s\n{'='*60}\n\n")
        for r in sorted(results, key=lambda x: x["name"]):
            f.write(f"--- {r['name']} ---\nok={r['ok']} latency={r['latency_ms']}ms tokens={r.get('completion_tokens',0)}\n")
            if r.get("error"): f.write(f"ERROR: {r['error']}\n")
            f.write(f"response: {r['content'][:500]}\n\n")
    print(f"Written to {out.resolve()}")


if __name__ == "__main__":
    main()
