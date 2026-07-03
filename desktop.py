import pyautogui
import time

def focus_window(title_substring):
    """Adaptive focus using observed window titles from desktop_tree_text."""
    # Evolved for self-adaptivity: scan observed titles, fallback to focused if Opera blocked
    windows = pyautogui.getAllWindows()
    for win in windows:
        if title_substring.lower() in win.title.lower():
            try:
                win.activate()
                time.sleep(0.5)
                return True
            except:
                pass
    # Repair contract: use currently focused if specified browser fails
    focused = pyautogui.getActiveWindow()
    if focused:
        focused.activate()
        time.sleep(0.3)
        return True
    return False

def navigate_to(url):
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.3)
    pyautogui.write(url)
    pyautogui.press('enter')
    return {'action': 'navigated', 'url': url}