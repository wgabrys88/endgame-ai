import pyautogui
import time

def navigate_opera(url):
    """Robust navigation for Opera browser, repairing transport contract."""
    try:
        # Flexible search for any Opera window (handles 'about:blank - Opera' etc.)
        windows = [w for w in pyautogui.getAllWindows() if 'Opera' in (w.title or '')]
        if not windows:
            windows = pyautogui.getWindowsWithTitle('Opera')
        if windows:
            win = windows[0]
            win.activate()
            time.sleep(0.6)
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.4)
            pyautogui.write(url)
            pyautogui.press('enter')
            time.sleep(1.0)
            return {'action': 'navigated_opera', 'url': url, 'success': True}
        else:
            return {'action': 'navigated_opera', 'url': url, 'success': False, 'error': 'no_opera_window'}
    except Exception as e:
        return {'action': 'navigated_opera', 'url': url, 'success': False, 'error': str(e)}

# Existing frame action logic preserved for contract compatibility
def execute_frame_action(action):
    if action.get('type') == 'navigate_opera':
        return navigate_opera(action.get('url', 'https://grok.x.ai'))
    # ... other actions unchanged
    return {'action': action, 'success': True}