"""tools.py — minimal external research helpers for terminal faculty.

Exposes web_search(query, num_results=10) and open_page(url, start_line=None)
using only stdlib (urllib + re). Results are returned as plain Python structures
so they can be recorded as capability actions.
"""
import json
import re
import subprocess
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
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href and title:
            results.append({"title": title, "url": href})
        if len(results) >= n:
            break
    if not results:
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


def read_file(path: str, max_bytes: int | None = None) -> Dict[str, Any]:
    """Deterministic full-content read of a local file.

    Returns a recorded-action dict with complete content, size, and SHA-256.
    Guarantees no truncation markers when max_bytes is None or sufficient.
    Raises RuntimeError on missing file or size violation.
    """
    p = __import__("pathlib").Path(path)
    if not p.exists() or not p.is_file():
        raise RuntimeError(f"read_file target does not exist or is not a file: {path}")
    size = p.stat().st_size
    if max_bytes is not None and size > max_bytes:
        raise RuntimeError(f"read_file target exceeds max_bytes limit: {size} > {max_bytes}")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"read_file failed: {type(exc).__name__}: {exc}") from exc
    import hashlib
    sha = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return {
        "ok": True,
        "action": "read_file",
        "path": str(p.resolve()),
        "size": size,
        "content": content,
        "content_chars": len(content),
        "content_sha256": sha,
    }


def github_create_issue(repo: str, title: str, body: str, labels: list | None = None) -> Dict[str, Any]:
    """Create a GitHub issue via gh CLI and return a recorded action."""
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    if labels:
        for label in labels:
            cmd.extend(["--label", str(label)])
    try:
        result = subprocess.run(cmd, cwd=__import__("pathlib").Path.cwd(), capture_output=True, text=True, timeout=60)
        return {
            "ok": result.returncode == 0,
            "action": "github_create_issue",
            "repo": repo,
            "title": title,
            "body": body,
            "labels": labels or [],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "action": "github_create_issue", "repo": repo, "error": f"{type(exc).__name__}: {exc}"}


def github_comment_issue(repo: str, issue_number: int, comment: str) -> Dict[str, Any]:
    """Comment on a GitHub issue via gh CLI and return a recorded action."""
    cmd = ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", comment]
    try:
        result = subprocess.run(cmd, cwd=__import__("pathlib").Path.cwd(), capture_output=True, text=True, timeout=60)
        return {
            "ok": result.returncode == 0,
            "action": "github_comment_issue",
            "repo": repo,
            "issue_number": issue_number,
            "comment": comment,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "action": "github_comment_issue", "repo": repo, "error": f"{type(exc).__name__}: {exc}"}


def github_list_issues(repo: str, state: str = "open") -> Dict[str, Any]:
    """List issues on a repo via gh CLI and return a recorded action."""
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", state, "--json", "number,title,state,labels,createdAt,updatedAt,body"]
    try:
        result = subprocess.run(cmd, cwd=__import__("pathlib").Path.cwd(), capture_output=True, text=True, timeout=60)
        issues = []
        if result.returncode == 0 and result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
            except Exception:
                issues = []
        return {
            "ok": result.returncode == 0,
            "action": "github_list_issues",
            "repo": repo,
            "state": state,
            "issues": issues,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "action": "github_list_issues", "repo": repo, "error": f"{type(exc).__name__}: {exc}"}


def github_push(branch: str | None = None) -> Dict[str, Any]:
    """Push current or specified branch to origin and return a recorded action."""
    cmd = ["git", "push", "origin"]
    if branch:
        cmd.append(branch)
    try:
        result = subprocess.run(cmd, cwd=__import__("pathlib").Path.cwd(), capture_output=True, text=True, timeout=120)
        return {
            "ok": result.returncode == 0,
            "action": "github_push",
            "branch": branch or "current",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "action": "github_push", "error": f"{type(exc).__name__}: {exc}"}