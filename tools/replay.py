"""replay.py - a what-if harness for the endgame-ai organism.

Replays a RECORDED transmission (any turn-*-record-*.json) verbatim against the live model,
OPTIONALLY with ONE change, N times, and reports what the model returned and what it cost.
Same request, same model, one variable moved: this is how we learn whether a change helps
BEFORE we touch the living body.

TWO WAYS TO MOVE THE ONE VARIABLE
  1. A SOURCE DIFF (the generic, faithful way).  --diff PATCH.diff
     The organism's system prompt (the cached [instructions]: the shared law, the one schema,
     every office docstring, the seated-tool manifest) is ASSEMBLED FROM SOURCE by the firmware's
     own Prompt/Loader. So to test a change to any of that, we RE-RENDER the prompt from the
     CURRENT source on BOTH sides - once clean (baseline), once with your diff `git apply`-ed onto
     a throwaway copy (patched) - and send the recorded turn with ONLY [instructions] swapped.
     The recorded [input] (the volatile board this turn read) is reused byte-for-byte on both
     sides, so the ONLY thing that moved is the law your diff edited (NOT any source drift since
     the turn was recorded). Any AI can produce such a diff; this tool turns it into evidence.
     NOTE: replay proves PROMPT/LAW changes (does the mind behave better?), NOT primitive behavior
     (does the code run?) - the latter needs the real wheel.

  2. A LITERAL MUTATION (a quick probe).  --field {instructions,input} --find OLD --replace NEW
     One literal find/replace in the named recorded field. Fails hard if the anchor is absent or
     ambiguous - a silent no-op would poison the experiment.

WHERE IT LIVES: under tools/, NOT at repo root - so the firmware's Loader (which seats every
top-level *.py as a node whose docstring joins the prompt) does NOT seat this instrument. A
developer tool must never cost the organism a single token of its mind.

WHERE IT RUNS: the API key lives in the Windows environment, so run through the Windows shell:
    powershell.exe -NoProfile -Command "cd '<repo>'; python tools/replay.py <record.json> [opts]"

USAGE
  python tools/replay.py RECORD.json                          # baseline, once
  python tools/replay.py RECORD.json -n 5                     # 5 baseline samples
  python tools/replay.py RECORD.json --diff fix.diff          # A/B: baseline vs patched-law, n each
  python tools/replay.py RECORD.json --diff fix.diff -n 5     # 5 each side, mean token delta
  python tools/replay.py RECORD.json --diff fix.diff --dry    # re-render + assemble only, send nothing
  python tools/replay.py RECORD.json --field input --find A --replace B   # literal probe
  python tools/replay.py RECORD.json --diff fix.diff --repo /path/to/repo # explicit repo root

  --diff FILE            a unified diff (git-style, a/ b/ prefixes) to apply to the source copy
  --field {instructions,input}   which recorded field to literally mutate (default: instructions)
  --find / --replace     literal, unique find/replace on --field (mutually exclusive with --diff)
  -n N                   samples per side (default 1)
  --repo DIR             repo root (default: the parent of this tools/ directory)
  --out DIR              output directory for raw responses (default: _replay under repo)
  --dry                  assemble bodies (re-render if --diff) and summarize; send nothing

OUTPUT
  Per sample: the returned record's [intent]/[code] head + token usage (in/out/total).
  With --diff or --find, BOTH sides ('baseline' and 'patched') run n times and a summary
  reports mean tokens per side and whether the returned [code] changed. Raw replies saved to
  <out>/<label>_<i>.json. Only the ONE variable ever moves; every other recorded byte is kept.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

API_URL = "https://api.x.ai/v1/responses"


# ---- the recorded turn ----
def load_body(record_path):
    rec = json.load(open(record_path, encoding="utf-8-sig"))
    body = (rec.get("request") or {}).get("body")
    if not isinstance(body, dict):
        sys.exit("no request.body in %s (is this a turn-*-record-*.json?)" % record_path)
    return body


# ---- way 1: a source diff, re-rendered through the real firmware ----
def render_system_from_source(repo_root, diff_path=None):
    """Copy the repo's top-level *.py + human files into a throwaway dir, optionally `git apply`
    the diff, then RE-RENDER the system prompt through the firmware IN ISOLATION (a subprocess with
    cwd on the copy), so `import endgame` binds the PATCHED kernel. Returns the rendered system text.
    Fails hard if the diff will not apply or the render errors - no silent fallback to the old law."""
    tmp = tempfile.mkdtemp(prefix="replay_src_")
    try:
        for name in os.listdir(repo_root):
            src = os.path.join(repo_root, name)
            if os.path.isfile(src) and (name.endswith(".py") or name in ("goal.md", "counsel.md")):
                shutil.copy2(src, os.path.join(tmp, name))
        # a minimal blackboard so Prompt can construct; render_system reads none of it, but the
        # firmware's Blackboard() touches goal.md/counsel.md which we already copied.
        if diff_path is not None:
            diff_abs = os.path.abspath(diff_path)
            applied = subprocess.run(["git", "apply", "--whitespace=nowarn", diff_abs],
                                     cwd=tmp, capture_output=True, text=True)
            if applied.returncode != 0:
                patched = subprocess.run(["patch", "-p1", "-i", diff_abs],
                                         cwd=tmp, capture_output=True, text=True)
                if patched.returncode != 0:
                    sys.exit("diff would not apply (git apply, then patch -p1 both failed):\n%s\n%s"
                             % (applied.stderr, patched.stderr))
        render = (
            "import endgame\n"
            "L = endgame.Loader(root='.')\n"
            "p = endgame.Prompt(endgame.Blackboard(root='.'), L)\n"
            "import sys\n"
            "sys.stdout.write(p.render_system())\n"
        )
        out = subprocess.run([sys.executable, "-c", render], cwd=tmp, capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit("re-render of the patched firmware failed:\n%s" % out.stderr)
        return out.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- way 2: a literal mutation ----
def literal_mutate(body, field, find, replace):
    text = body.get(field)
    if not isinstance(text, str):
        sys.exit("field %r is not a string in this body" % field)
    n = text.count(find)
    if n == 0:
        sys.exit("--find text not present in field %r; nothing to mutate (no silent no-op)" % field)
    if n > 1:
        sys.exit("--find occurs %d times in field %r; refine it to a unique anchor" % (n, field))
    new = dict(body)
    new[field] = text.replace(find, replace, 1)
    return new


# ---- transport + parsing (mirrors the firmware) ----
def extract_content(obj):
    if obj.get("choices"):
        return str(obj["choices"][0]["message"]["content"])
    if str(obj.get("output_text") or "").strip():
        return str(obj["output_text"])
    parts = []
    for item in obj.get("output", []):
        if isinstance(item, dict) and item.get("type") != "reasoning":
            c = item.get("content")
            if isinstance(c, list):
                parts += [str(p.get("text")) for p in c if isinstance(p, dict) and p.get("text")]
            elif isinstance(c, str) and c.strip():
                parts.append(c)
    return "\n".join(parts)


def strip_fence(s):
    text = (s or "").strip()
    m = re.fullmatch(r"```(?:\w+)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def usage_of(obj):
    u = obj.get("usage") or {}
    return (u.get("input_tokens") or u.get("prompt_tokens"),
            u.get("output_tokens") or u.get("completion_tokens"),
            u.get("total_tokens"))


def send(body):
    key = os.environ.get("XAI_API_KEY")
    if not key:
        sys.exit("XAI_API_KEY not in environment. Run through the Windows shell so the key is present.")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=240) as r:
        return r.read().decode()


def run_side(body, label, n, out_dir):
    """Send `body` n times; save raw replies; return list of (in,out,total,code) per sample."""
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for i in range(1, n + 1):
        try:
            raw = send(body)
        except Exception as e:
            print("  [%s] sample %d: ERROR %r" % (label, i, e))
            continue
        open(os.path.join(out_dir, "%s_%d.json" % (label, i)), "w", encoding="utf-8").write(raw)
        obj = json.loads(raw)
        content = extract_content(obj)
        it, ot, tt = usage_of(obj)
        code = intent = ""
        try:
            rec = json.loads(strip_fence(content))
            code = rec.get("code") or ""
            intent = rec.get("intent") or ""
        except Exception:
            code = "(reply is not a record; raw content saved)"
        results.append((it, ot, tt, code))
        head = (intent or code).strip().splitlines()[:3]
        print("  [%s] sample %d | tokens in=%s out=%s total=%s | head:" % (label, i, it, ot, tt))
        for line in head:
            print("      %s" % line[:100])
    return results


def summarize(baseline, patched):
    def mean_total(rows):
        vals = [r[2] for r in rows if r[2] is not None]
        return sum(vals) / len(vals) if vals else None
    mb, mp = mean_total(baseline), mean_total(patched)
    print("\n===== A/B summary =====")
    print("  baseline: n=%d  mean total tokens=%s" % (len(baseline), round(mb) if mb else "n/a"))
    print("  patched : n=%d  mean total tokens=%s" % (len(patched), round(mp) if mp else "n/a"))
    if mb and mp:
        print("  delta   : %+d tokens/turn (%.1f%%)" % (round(mp - mb), 100.0 * (mp - mb) / mb))
    codes_b = {r[3].strip() for r in baseline}
    codes_p = {r[3].strip() for r in patched}
    print("  returned [code] changed under the patch: %s" % (codes_b != codes_p))


def main():
    ap = argparse.ArgumentParser(description="Replay a recorded endgame-ai transmission, optionally patched, N times.")
    ap.add_argument("record", help="path to a turn-*-record-*.json")
    ap.add_argument("--diff", help="unified diff to apply to the source copy, then re-render the system prompt")
    ap.add_argument("--field", default="instructions", choices=["instructions", "input"],
                    help="which recorded field to LITERALLY mutate (default: instructions)")
    ap.add_argument("--find", help="literal text to find (unique) in --field")
    ap.add_argument("--replace", help="text to replace it with")
    ap.add_argument("-n", type=int, default=1, help="samples per side (default 1)")
    ap.add_argument("--repo", help="repo root (default: parent of this tools/ dir)")
    ap.add_argument("--out", help="output dir for raw responses (default: <repo>/_replay)")
    ap.add_argument("--dry", action="store_true", help="assemble/re-render and summarize; send nothing")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = args.out or os.path.join(repo, "_replay")

    if args.diff and args.find:
        sys.exit("choose ONE variable to move: --diff (re-render the law) OR --find/--replace (literal). Not both.")
    if args.find is not None and args.replace is None:
        sys.exit("--find given without --replace")

    baseline_body = load_body(args.record)
    baseline_body["store"] = False  # never persist server-side during experiments

    patched_body = None
    if args.diff:
        # Faithful A/B: re-render BOTH sides from CURRENT source so the ONLY moved variable is the
        # diff. (Sending the RECORDED instructions as baseline would conflate the diff with every
        # source change since the recording - e.g. a tool since unseated.) The recorded [input]
        # is reused byte-for-byte on both sides; only the law your diff edits differs.
        base_system = render_system_from_source(repo, None)
        patched_system = render_system_from_source(repo, args.diff)
        baseline_body = dict(baseline_body)
        baseline_body["instructions"] = base_system
        patched_body = dict(baseline_body)
        patched_body["instructions"] = patched_system
    elif args.find is not None:
        patched_body = literal_mutate(baseline_body, args.field, args.find, args.replace)
        patched_body["store"] = False

    if args.dry:
        print("DRY | record=%s | repo=%s" % (os.path.basename(args.record), repo))
        print("  baseline instructions=%d chars, input=%d chars"
              % (len(baseline_body.get("instructions") or ""), len(baseline_body.get("input") or "")))
        if patched_body is not None:
            src = "re-rendered from patched source" if args.diff else ("literal %s mutation" % args.field)
            print("  patched  instructions=%d chars (%s)"
                  % (len(patched_body.get("instructions") or ""), src))
            di = len(patched_body.get("instructions") or "") - len(baseline_body.get("instructions") or "")
            print("  system-prompt delta: %+d chars/turn" % di)
        return

    print("replaying %s | repo=%s | n=%d | %s"
          % (os.path.basename(args.record), repo, args.n,
             "A/B (baseline vs patched)" if patched_body is not None else "baseline only"))
    baseline = run_side(baseline_body, "baseline", args.n, out_dir)
    if patched_body is not None:
        patched = run_side(patched_body, "patched", args.n, out_dir)
        summarize(baseline, patched)


if __name__ == "__main__":
    main()
