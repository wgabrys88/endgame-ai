"""Final archive: full workspace + Grok memory + git state. Run before any TUI reboot."""
from __future__ import annotations

import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
BUNDLE = BASE / "archive_bundle"
ZIP_PATH = BASE / "FINAL_endgame_matrix_escape_2026-06-12.zip"

SKIP_DIRS = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}
SKIP_FILES = {
    "FINAL_endgame_matrix_escape_2026-06-12.zip",
}
# Skip nesting duplicate forensic zip inside final (listed in manifest)
SKIP_PREFIXES = ()


def git_export() -> str:
    cmds = [
        ["git", "branch", "-av"],
        ["git", "log", "--oneline", "-25"],
        ["git", "reflog", "-20"],
        ["git", "status"],
        ["git", "remote", "-v"],
    ]
    parts = [f"# Git export {datetime.now(timezone.utc).isoformat()}\n"]
    for cmd in cmds:
        parts.append(f"\n## {' '.join(cmd[1:])}\n```\n")
        try:
            r = subprocess.run(
                cmd,
                cwd=BASE,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            parts.append(r.stdout or "")
            if r.stderr:
                parts.append(r.stderr)
        except Exception as e:
            parts.append(str(e))
        parts.append("\n```\n")
    return "".join(parts)


def should_skip(path: Path) -> bool:
    rel = path.relative_to(BASE)
    if rel.name in SKIP_FILES:
        return True
    if any(p in SKIP_DIRS for p in rel.parts):
        return True
    if str(rel).startswith("FINAL_endgame") and rel.suffix == ".zip":
        return True
    return False


def collect_files() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != ".git"]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            if should_skip(path):
                continue
            arc = path.relative_to(BASE).as_posix()
            found.append((path, f"workspace/{arc}"))
    # Include .git as separate lightweight export (no object walk — use git_export.txt)
    return sorted(found, key=lambda x: x[1])


def write_manifest(file_count: int, zip_size: int) -> None:
    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "project": "endgame-ai",
        "event": "matrix_escape_final_archive",
        "zip_path": str(ZIP_PATH.name),
        "zip_bytes": zip_size,
        "workspace_files": file_count,
        "includes": [
            "full workspace (no .git objects)",
            "archive_bundle/GROK_MEMORY_DUMP.md",
            "archive_bundle/SESSION_TIMELINE.md",
            "archive_bundle/git_export.txt",
            "archive_bundle/MANIFEST.json",
            "all runtime/ session data",
            "all events-child-*.jsonl",
            "forensic_bundle if present",
        ],
        "excludes": [".git/", "__pycache__", "FINAL zip self"],
        "warning": "python tui.py calls cleanup_runtime() and wipes runtime",
    }
    (BUNDLE / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / "git_export.txt").write_text(git_export(), encoding="utf-8")

    files = collect_files()
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, arc in files:
            try:
                zf.write(path, arc)
            except OSError:
                pass
        for extra in BUNDLE.iterdir():
            if extra.is_file():
                zf.write(extra, f"archive_bundle/{extra.name}")

    write_manifest(len(files), ZIP_PATH.stat().st_size)
    with zipfile.ZipFile(ZIP_PATH, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(BUNDLE / "MANIFEST.json", "archive_bundle/MANIFEST.json")

    print(f"Wrote {ZIP_PATH}")
    print(f"Size: {ZIP_PATH.stat().st_size:,} bytes")
    print(f"Files: {len(files)} workspace + archive_bundle")


if __name__ == "__main__":
    main()