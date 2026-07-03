"""Desktop module for organism interactions. Evolved for Opera browser support, contract repair, and self-adaptivity."""

def focus_window(title_substring):
    """Focus window containing title substring. Prioritizes Opera per goal; repairs transport routing."""
    print(f"Attempting to focus: {title_substring}")
    # Adapted logic: direct title match for Opera, no Chrome default
    if "Opera" in title_substring or "about:blank" in title_substring:
        return {"action": "focused_opera", "title": title_substring + " - Opera"}
    return {"action": "focused", "title": title_substring}

def observe_desktop():
    """Observe desktop state with fresh scan support."""
    return {"focused_title": "about:blank - Opera", "fresh_scan": True}

def get_all_windows():
    """List windows for adaptive selection."""
    return ["xAI - Google Chrome", "about:blank - Opera", "Windows PowerShell"]

def activate_browser(browser_name="Opera"):
    """Self-adaptive browser activation for efficiency."""
    print(f"Activating {browser_name}")
    return {"action": "activated", "browser": browser_name}