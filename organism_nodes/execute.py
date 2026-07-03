import pyautogui
import time

def execute_action(action_code, desktop_tree_text, focused_title, step_description):
    if 'Opera' in focused_title and 'xAI' in focused_title and 'chat' not in focused_title.lower() and 'Grok' in focused_title:
        # Adaptive navigation: focus address bar, go to Grok chat, then query
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.4)
        pyautogui.write('https://grok.x.ai/')
        pyautogui.press('enter')
        time.sleep(2.0)
        # Now type the Grok query for fresh AI/tech news
        pyautogui.write('What is one fresh interesting AI or tech news item from today? Provide headline and source.')
        pyautogui.press('enter')
        return {'action': 'navigated_and_typed_grok_query', 'status': 'sent', 'adapted': True}
    else:
        # Fallback original for chat pages
        pyautogui.click(600, 900)
        time.sleep(0.3)
        pyautogui.write('What is one fresh interesting AI or tech news item from today? Provide headline and source.')
        pyautogui.press('enter')
        return {'action': 'typed_grok_query', 'status': 'sent'}

# Core execution entry for organism action bus
if __name__ == "__main__":
    print('execute.py evolved for Opera adaptivity')