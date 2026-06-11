"""Debug tool: dumps exactly what each LLM agent sees as context.
Run: python debug_context.py [agent_name] [--goal "text"]
Writes to _debug_context_dump.txt"""
import sys, os, json, time, argparse
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

import config, log
from token_state import initial_state
from agents import ObserverAgent, _render_field

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", nargs="?", default="planner", choices=["planner", "actor", "verifier", "reflector"])
    parser.add_argument("--goal", default="")
    args = parser.parse_args()

    log.init(50)
    board = {
        "goal": args.goal, "plan": [], "done_when": "", "history": [], "completed": [],
        "power": 0.0, "start_time": time.time(),
        "screen": "", "screen_elements": {}, "desktop_summary": "", "focused_window": "",
        "consecutive_failures": 0, "stagnation": 0.0, "progress_history": [],
        "lorenz_x": 8.48, "lorenz_y": 8.48, "lorenz_z": 27.0, "energy": 1.74, "wing_crossed": False,
        "pid_output": 0.0, "pid_integral": 0.0, "pid_prev": 0.0,
        "last_reflect_time": 0.0,
        "token_state": initial_state(),
    }

    if config.GUI_MODE_PATH.exists():
        obs = ObserverAgent()
        obs_ctx = {k: board[k] for k in obs.reads if k in board}
        obs_result = obs.run(obs_ctx)
        board.update(obs_result.get("writes", {}))

    fields = config.CONTEXT_POLICY.get(args.agent, [])
    output = [f"{'='*80}", f"CONTEXT FOR: {args.agent.upper()}", f"{'='*80}"]
    for field in fields:
        rendered = _render_field(board, field, "")
        if rendered:
            output.append(f"\n--- {field.upper()} ---")
            output.append(rendered)
        else:
            output.append(f"\n--- {field.upper()} --- (empty)")

    output.append(f"\n{'='*80}")
    output.append(f"Screen chars: {len(board.get('screen', ''))}")
    output.append(f"GUI mode: {'ON' if config.GUI_MODE_PATH.exists() else 'OFF'}")

    with open("_debug_context_dump.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print(f"Wrote to _debug_context_dump.txt ({len(output)} lines)")
    print(f"GUI mode: {'ON' if config.GUI_MODE_PATH.exists() else 'OFF'}")

if __name__ == "__main__":
    main()
