"""tools.py — minimal external research helpers for terminal faculty.

Exposes web_search(query, num_results=10) and open_page(url, start_line=None)
using only stdlib (urllib). Results are returned as plain Python structures
so they can be recorded as capability actions.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def web_search(query: str, num_results: int = 10) -> List[Dict[str, Any]]:
    """Perform a DuckDuckGo HTML search and return a list of result dicts."""
    q = (query or "").strip()
    if not q:
        return []
    n = max(1, min(30, int(num_results or 10)))
    params = urllib.parse.urlencode({"q": q, "kl": "us-en"})
    url = f"https://html.duckduckgo.com/html/?{params}"
    try:
        html = _http_get(url)
    except Exception:
        return []
    results: List[Dict[str, Any]] = []
    # Very lightweight extraction of result links/titles
    import re
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href and title:
            results.append({"title": title, "url": href})
        if len(results) >= n:
            break
    if not results:
        # Fallback: try to find any <a> with result links
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            href = m.group(1)
            if "duckduckgo" not in href.lower() and len(results) < n:
                results.append({"title": href, "url": href})
    return results[:n]


def open_page(url: str, start_line: int | None = None) -> str:
    """Fetch page text content. Optionally return only from start_line (1-based)."""
    u = (url or "").strip()
    if not u:
        return ""
    try:
        html = _http_get(u)
    except Exception as exc:
        return f"[open_page error] {type(exc).__name__}: {exc}"
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if start_line is not None:
        lines = text.split(". ")
        try:
            start = max(0, int(start_line) - 1)
            text = ". ".join(lines[start:])
        except Exception:
            pass
    return text
