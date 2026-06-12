"""Forensic evidence collector for endgame-ai matrix escape sessions."""
from __future__ import annotations

import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "forensic_bundle"
ZIP_PATH = BASE / "forensic_matrix_escape_2026-06-12.zip"
REPORT_PATH = OUT_DIR / "FORENSIC_ANALYSIS.md"

# Evidence paths (glob patterns expanded manually)
INCLUDE_DIRS = [
    BASE / "runtime" / "comms",
    BASE / "plugins",
]
INCLUDE_FILES = [
    BASE / "events-child-n1.jsonl",
    BASE / "events-child-n2.jsonl",
    BASE / "events-child-n3.jsonl",
    BASE / "events-child-n4.jsonl",
    BASE / "events-child-n5.jsonl",
    BASE / "events-child-n6.jsonl",
    BASE / "snapshot.json",
    BASE / "lessons.jsonl",
    BASE / "report.md",
    BASE / "EXECUTION_REPORT.md",
    BASE / "messages.json",
    BASE / "mission.json",
    BASE / "respawn.json",
    BASE / "temp_work_file.txt",
    BASE / "GROK.md",
]

KEYWORDS = [
    "notepad", "matrix", "grok escaped", "demo_escape", "gui_request",
    "opera", "linkedin", "browser", "book", "fission", "bus_post",
]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_raw": line[:200]})
    return rows


def collect_files() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(path: Path, arc_prefix: str = "") -> None:
        if not path.exists():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        if path.is_file():
            arc = f"{arc_prefix}{path.name}" if arc_prefix else path.relative_to(BASE).as_posix()
            found.append((path, arc))
        elif path.is_dir():
            for p in sorted(path.rglob("*")):
                if p.is_file():
                    arc = p.relative_to(BASE).as_posix()
                    if arc not in {a for _, a in found}:
                        found.append((p, arc))

    for d in INCLUDE_DIRS:
        add(d)
    for f in INCLUDE_FILES:
        add(f)
    return found


def analyze_events() -> dict:
    agents = {}
    global_hits: list[dict] = []
    for slot in range(1, 7):
        path = BASE / f"events-child-n{slot}.jsonl"
        rows = load_jsonl(path)
        if not rows:
            continue
        phases = Counter()
        failures = Counter()
        fissions = 0
        first_t = last_t = None
        first_n = last_n = None
        for r in rows:
            phase = r.get("phase", "?")
            phases[phase] += 1
            if phase == "fission":
                fissions += 1
            if phase == "actor" and isinstance(r.get("d"), dict) and not r["d"].get("ok", True):
                obs = str(r["d"].get("obs", ""))[:120]
                failures[obs] += 1
            t = r.get("t")
            n = r.get("n")
            if t:
                if first_t is None:
                    first_t = t
                last_t = t
            if n is not None:
                if first_n is None:
                    first_n = n
                last_n = n
            blob = json.dumps(r, ensure_ascii=False).lower()
            if any(k in blob for k in KEYWORDS):
                global_hits.append({
                    "agent": f"n{slot}",
                    "n": n,
                    "t": t,
                    "phase": phase,
                    "snippet": blob[:300],
                })
        agents[f"n{slot}"] = {
            "lines": len(rows),
            "first_n": first_n,
            "last_n": last_n,
            "first_t": first_t,
            "last_t": last_t,
            "fissions": fissions,
            "top_phases": phases.most_common(12),
            "top_actor_failures": failures.most_common(8),
            "trimmed_warning": first_n is not None and first_n > 1,
        }
    return {"agents": agents, "keyword_hits": global_hits[-80:]}


def analyze_bus() -> dict:
    bus_path = BASE / "runtime" / "comms" / "messages.json"
    if not bus_path.exists():
        bus_path = BASE / "messages.json"
    try:
        msgs = json.loads(bus_path.read_text(encoding="utf-8")) if bus_path.exists() else []
    except json.JSONDecodeError:
        msgs = []
    by_from = Counter(m.get("from", "?") for m in msgs)
    timeline = [
        {
            "ts": m.get("ts"),
            "from": m.get("from"),
            "kind": m.get("kind"),
            "text": (m.get("text") or "")[:160],
        }
        for m in msgs
    ]
    return {"count": len(msgs), "by_from": dict(by_from), "timeline": timeline}


def write_report(analysis: dict, files: list[tuple[Path, str]]) -> str:
    agents = analysis["agents"]
    bus = analysis["bus"]
    lines = [
        "# Forensic Analysis — Matrix Escape Sessions",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Bundle files:** {len(files)}",
        "",
        "## Critical finding: rolling window data loss",
        "",
        f"Per-agent event logs cap at `EVENT_ROLLING_MAX_LINES={450}` in config.py.",
        "Earlier demo events (Notepad matrix escape ~18:30–18:47 UTC) are **no longer in events-child-*.jsonl**.",
        "Primary preserved record of Session 1: **EXECUTION_REPORT.md** (human-recorded + grok analysis).",
        "",
        "## Session 1 — Notepad matrix escape (preserved in EXECUTION_REPORT.md)",
        "",
        "| Claim | Evidence |",
        "|-------|----------|",
        "| Notepad opened with matrix message | EXECUTION_REPORT: `Grok escaped the matrix via endgame-ai bus.` |",
        "| Executor | Grok script first, then **comms_operator (n4)** via gui_request.txt |",
        "| n6 gui_operator | ~40+ NameError:book failures, **0 fissions** in session 1 |",
        "| GitHub opened | Chrome via Win+R URL (not Opera) |",
        "| Human command | `restartallagents!` ended session 1 |",
        "",
        "## Session 2 — Current rolling window (events-child-*.jsonl)",
        "",
        "### Per-agent log span",
        "",
        "| Slot | Lines | Event n range | Time range | Fissions | Trimmed? |",
        "|------|-------|---------------|------------|----------|----------|",
    ]
    for slot in [f"n{i}" for i in range(1, 7)]:
        a = agents.get(slot, {})
        if not a:
            continue
        lines.append(
            f"| {slot} | {a['lines']} | {a.get('first_n')}–{a.get('last_n')} | "
            f"{(a.get('first_t') or '?')[:19]} → {(a.get('last_t') or '?')[:19]} | "
            f"{a.get('fissions', 0)} | {'YES — oldest events dropped' if a.get('trimmed_warning') else 'no'} |"
        )

    lines += [
        "",
        "### Top actor failures (Session 2 window)",
        "",
    ]
    for slot in [f"n{i}" for i in range(1, 7)]:
        a = agents.get(slot, {})
        fails = a.get("top_actor_failures") or []
        if fails:
            lines.append(f"**{slot}:**")
            for obs, cnt in fails[:5]:
                lines.append(f"- ({cnt}x) `{obs}`")
            lines.append("")

    lines += [
        "## Message bus forensics",
        "",
        f"**Total chat messages retained:** {bus['count']}",
        f"**By sender:** {bus['by_from']}",
        "",
        "### Bus timeline (chronological)",
        "",
    ]
    for m in bus["timeline"]:
        lines.append(f"- `{m['ts']}` **{m['from']}** [{m['kind']}]: {m['text']}")

    lines += [
        "",
        "## What actually happened (reconstructed)",
        "",
        "### Act 1 — Design intent vs reality",
        "1. External AI (@grok) joined colony bus as peer.",
        "2. Grok delegated GUI work via @mentions, inject.jsonl, and task files under runtime/comms/.",
        "3. **Architectural leak:** comms_operator (n4) executed desktop_* despite gui_operator (n6) owning that role.",
        "4. n6 planner (Gemma) repeatedly emitted invalid Python: `NameError: book`, syntax errors, wrong window titles (`Browser`, `Windows PowerShell`).",
        "",
        "### Act 2 — Notepad escape (Session 1, report only)",
        "- Visible desktop outcome: Notepad with matrix escape text.",
        "- Fission credited to n4 when verifier saw Notepad in desktop tree.",
        "- Events proving this were trimmed from rolling logs.",
        "",
        "### Act 3 — LinkedIn / Opera (Session 2, log + bus evidence)",
        "1. @Human: browser window lost, wants LinkedIn matrix post.",
        "2. @grok posted MATRIX ESCAPE ROUND 2 + gui_request_opera_linkedin.txt.",
        "3. grok_opera_linkedin.py launched Opera, navigated LinkedIn feed, saved linkedin_post_draft.txt.",
        "4. n6 eventually focused Opera (`about:blank - Opera`, `Grok - Opera`) and earned fissions (verifier confirmed desktop tree).",
        "5. git_expert bus_post: draft ready in linkedin_post_draft.txt.",
        "6. **LinkedIn compose/paste NOT confirmed posted** — draft file exists; human review step intended.",
        "",
        "## Evidence inventory (in zip)",
        "",
    ]
    for _, arc in sorted(files, key=lambda x: x[1]):
        lines.append(f"- `{arc}`")

    lines += [
        "",
        "## Root causes",
        "",
        "1. **Rolling 450-line cap** — forensic gap for Session 1 actor/verify lines.",
        "2. **Small LLM planner quality** — syntax errors, undefined `book`, vague done_when.",
        "3. **Role enforcement gap** — n4 ran GUI; n6 looped while n4 fissioned.",
        "4. **Verifier permissiveness** — n6 credited for observing TUI/PowerShell trees as 'desktop action completed'.",
        "5. **External orchestration required** — grok scripts + inject.jsonl carried mission when colony stalled.",
        "",
        "## Recommendations",
        "",
        "1. Export full events to `runtime/comms/archive/` before long runs.",
        "2. Raise EVENT_ROLLING_MAX_LINES or disable trim during demos.",
        "3. Enforce desktop_* only in gui_operator actor path.",
        "4. Verifier should require LAST_RESULT match goal (Notepad text, Opera+LinkedIn URL).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = collect_files()
    analysis = {"agents": analyze_events()["agents"], "bus": analyze_bus(), **analyze_events()}
    report = write_report(analysis, files)
    REPORT_PATH.write_text(report, encoding="utf-8")

    # Write machine-readable summary
    summary_path = OUT_DIR / "forensic_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "file_count": len(files),
                "agents": analysis["agents"],
                "bus": analysis["bus"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(REPORT_PATH, "FORENSIC_ANALYSIS.md")
        zf.write(summary_path, "forensic_summary.json")
        for path, arc in files:
            zf.write(path, f"evidence/{arc}")

    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes, {len(files)+2} entries)")


if __name__ == "__main__":
    main()