"""replay.py — a what-if harness for the endgame-ai organism.

Replays a RECORDED transmission (any turn-*-record-*.json under .transmissions/) verbatim
against the live model, OPTIONALLY with a single mutation, N times, and reports what the
model returned. This lets you ask "what if the prompt had said X?" and MEASURE the effect
on real requests instead of guessing — the same request, the same model, one variable changed.

It is task-agnostic: it knows nothing of any goal, office, or fix. It mutates a field you
name by a literal find/replace, sends, and shows the returned record + token usage. Diffing
baseline vs mutated across many recorded turns is how we learn whether a prompt change helps
BEFORE we ever touch the body.

WHY IT LIVES HERE: the organism is improved by evidence, not opinion. This is the instrument
that produces the evidence. It reuses the firmware's own transport shape (the /responses API,
the Bearer XAI_API_KEY header, the JSON body as recorded), so a replay is faithful.

WHERE IT RUNS: the API key lives in the Windows environment, so run it through the Windows
shell so os.environ carries the key:

    powershell.exe -NoProfile -Command "cd '<repo>'; python replay.py <record.json> [opts]"

USAGE
  python replay.py RECORD.json                         # replay as-is, once (baseline)
  python replay.py RECORD.json -n 5                    # 5 baseline samples
  python replay.py RECORD.json --find "OLD" --replace "NEW"        # mutate instructions
  python replay.py RECORD.json --field input --find A --replace B  # mutate the user message
  python replay.py RECORD.json --find X --replace Y -n 5 --label myclause
  python replay.py RECORD.json --find X --replace Y --dry          # build only, no API call

  --field {instructions,input}  which body field to mutate (default: instructions)
  --find TEXT --replace TEXT     literal find/replace applied ONCE; fails hard if not found
  -n N                           number of samples to send (default 1)
  --label NAME                   tag for saved responses (default: 'baseline' or 'mutated')
  --out DIR                      output directory (default: _replay)
  --dry                          assemble the (mutated) body and print a summary; send nothing

OUTPUT
  For each sample: the extracted [code] field (if the reply is a record) or the raw content,
  plus input/output/total token usage. Raw responses saved to <out>/<label>_<i>.json.
  Only the chosen field is ever changed; every other byte of the recorded request is preserved.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

API_URL = "https://api.x.ai/v1/responses"


def load_body(record_path):
    rec = json.load(open(record_path, encoding="utf-8-sig"))
    req = rec.get("request") or {}
    body = req.get("body")
    if not isinstance(body, dict):
        sys.exit("no request.body in %s (is this a turn-*-record-*.json?)" % record_path)
    return body


def mutate(body, field, find, replace):
    """Return a copy of body with ONE literal find/replace in the named field. Fail hard if
    the anchor text is absent or ambiguous — a silent no-op would poison the experiment."""
    text = body.get(field)
    if not isinstance(text, str):
        sys.exit("field %r is not a string in this body" % field)
    n = text.count(find)
    if n == 0:
        sys.exit("--find text not present in field %r; nothing to mutate (no silent no-op)" % field)
    if n > 1:
        sys.exit("--find text occurs %d times in field %r; refine it to a unique anchor" % (n, field))
    new = dict(body)
    new[field] = text.replace(find, replace, 1)
    new["store"] = False  # never persist server-side during experiments
    return new


def extract_content(obj):
    """Mirror the firmware's Transport._extract for the /responses and chat shapes."""
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


def main():
    ap = argparse.ArgumentParser(description="Replay a recorded endgame-ai transmission, optionally mutated, N times.")
    ap.add_argument("record", help="path to a turn-*-record-*.json")
    ap.add_argument("--field", default="instructions", choices=["instructions", "input"],
                    help="which body field to mutate (default: instructions)")
    ap.add_argument("--find", help="literal text to find (unique) in the field")
    ap.add_argument("--replace", help="text to replace it with")
    ap.add_argument("-n", type=int, default=1, help="number of samples to send")
    ap.add_argument("--label", help="tag for saved responses")
    ap.add_argument("--out", default="_replay", help="output directory")
    ap.add_argument("--dry", action="store_true", help="assemble and summarize; send nothing")
    args = ap.parse_args()

    body = load_body(args.record)
    mutated = args.find is not None
    if mutated and args.replace is None:
        sys.exit("--find given without --replace")
    if mutated:
        body = mutate(body, args.field, args.find, args.replace)
    label = args.label or ("mutated" if mutated else "baseline")

    if args.dry:
        f = body.get(args.field, "")
        print("DRY: record=%s field=%s mutated=%s length=%d chars" % (args.record, args.field, mutated, len(f)))
        if mutated:
            i = f.find(args.replace)
            print("  mutation context: ...%s..." % f[max(0, i - 60):i + len(args.replace) + 60].replace("\n", " "))
        print("  model=%s temperature=%s reasoning=%s"
              % (body.get("model"), body.get("temperature"), body.get("reasoning")))
        return

    os.makedirs(args.out, exist_ok=True)
    print("replaying %s | field=%s | mutated=%s | n=%d | label=%s"
          % (os.path.basename(args.record), args.field, mutated, args.n, label))
    for i in range(1, args.n + 1):
        try:
            raw = send(body)
        except Exception as e:
            print("  sample %d: ERROR %r" % (i, e))
            continue
        out_path = os.path.join(args.out, "%s_%d.json" % (label, i))
        open(out_path, "w", encoding="utf-8").write(raw)
        obj = json.loads(raw)
        content = extract_content(obj)
        it, ot, tt = usage_of(obj)
        code = ""
        try:
            code = json.loads(strip_fence(content)).get("code") or ""
        except Exception:
            code = "(reply is not a record; raw content saved)"
        head = code.strip().splitlines()[:3]
        print("  sample %d -> %s | tokens in=%s out=%s total=%s | code head:"
              % (i, os.path.basename(out_path), it, ot, tt))
        for line in head:
            print("      %s" % line[:100])


if __name__ == "__main__":
    main()
