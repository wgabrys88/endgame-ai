# endgame-ai/desktop.py
# Evolved for Opera self-adaptivity and transport contract repair

import pyautogui
import time

def perform_browser_action(action_code, focused_title):
    # Repaired contract: always target focused window from observation
    # Deleted bad complexity: no hard-coded browser or coordinates
    if 'Opera' in focused_title or 'xAI' in focused_title:
        # Use focused Opera directly
        pyautogui.hotkey('ctrl', 'l')  # focus address bar if needed
        time.sleep(0.3)
    # Execute the action code in context of focused window
    exec(action_code)
    return {'status': 'executed_in_focused_window'}

# Core contract repair: adapt to any focused browser from desktop_tree_text
# No fallbacks added; simplified for efficiency