"""Detect and redact verbatim Kaggle Competition Data inside stdout_tail (release gate).

Kaggle Standard Rules 7.B forbids redistributing Competition Data. Cards keep the last 800
chars of execution output, and on extraction-QA style tasks the agent prints gold answers
and context passages, so a few tails carry real records.

Two lessons from the first pass are baked in:
  * Raw substring matching is dominated by FALSE POSITIVES -- 49 spaces and 40 '=' chars
    both "appear in the source". Any span whose distinct-character count is tiny, or which
    is pure whitespace/punctuation, is formatting, not data.
  * Sampling understates. This runs over every card of every task.

Redaction replaces the matched span with a marker so the surrounding log (metrics, errors,
tracebacks -- the scientifically useful part) survives intact.

Usage: python phase1/scrub_stdout.py IN.jsonl OUT.jsonl [--report-only]
"""
import glob, json, sys

DATA = "/research/d7/spc/yzyang4/mle-bench-data"
MINLEN = 40
MIN_DISTINCT = 12          # a real data span has vocabulary; rulers and padding do not
MARK = "[REDACTED:competition-data]"

src_in, dst_out = sys.argv[1], sys.argv[2]
REPORT_ONLY = "--report-only" in sys.argv


def load_source(task, budget=40_000_000):
    buf, n = [], 0
    for ext in ("csv", "json", "txt", "tsv"):
        for f in sorted(glob.glob(DATA + "/" + task + "/prepared/**/*." + ext,
                                  recursive=True)):
            if n >= budget:
                break
            try:
                with open(f, errors="ignore") as fh:
                    s = fh.read(budget - n)
            except OSError:
                continue
            buf.append(s)
            n += len(s)
    return "".join(buf)


def is_datalike(span):
    """Reject formatting artefacts: rulers, padding, separator runs."""
    if len(set(span)) < MIN_DISTINCT:
        return False
    stripped = "".join(c for c in span if not c.isspace())
    if len(stripped) < MINLEN * 0.6:
        return False
    return any(c.isalnum() for c in stripped)


def find_spans(tail, src):
    """Maximal data-like spans of tail that occur verbatim in src."""
    spans = []
    for line in tail.splitlines():
        if len(line) < MINLEN:
            continue
        i = 0
        while i <= len(line) - MINLEN:
            if line[i:i + MINLEN] in src:
                hi = i + MINLEN
                while hi < len(line) and line[i:hi + 1] in src:
                    hi += 1
                lo = i
                while lo > 0 and line[lo - 1:hi] in src:
                    lo -= 1
                span = line[lo:hi]
                if is_datalike(span):
                    spans.append(span)
                i = hi
            else:
                i += 1
    return spans


cards = [json.loads(l) for l in open(src_in)]
tasks = sorted({c["task"]["name"] for c in cards})
srcs, unscanned = {}, []
for t in tasks:
    s = load_source(t)
    if s:
        srcs[t] = s
    else:
        unscanned.append(t)

hit_cards, total_spans, per_task = 0, 0, {}
for c in cards:
    t = c["task"]["name"]
    if t not in srcs:
        continue
    tail = c["obs"].get("stdout_tail") or ""
    if len(tail) < MINLEN:
        continue
    spans = find_spans(tail, srcs[t])
    if not spans:
        continue
    hit_cards += 1
    total_spans += len(spans)
    d = per_task.setdefault(t, {"cards": 0, "spans": 0, "max": 0, "ex": ""})
    d["cards"] += 1
    d["spans"] += len(spans)
    for sp in spans:
        if len(sp) > d["max"]:
            d["max"], d["ex"] = len(sp), sp
        tail = tail.replace(sp, MARK)
    c["obs"]["stdout_tail"] = tail
    c["obs"]["stdout_redacted"] = True

print("scrub_stdout: " + str(len(cards)) + " cards, " + str(len(srcs)) + " tasks scanned")
if unscanned:
    print("  UNSCANNED (no prepared data on disk): " + str(unscanned))
print("  cards containing verbatim competition data: " + str(hit_cards) +
      " (" + format(hit_cards / max(len(cards), 1) * 100, ".2f") + "%), spans " +
      str(total_spans))
for t, d in sorted(per_task.items(), key=lambda kv: -kv[1]["cards"]):
    print("   " + t[:44].ljust(44) + " cards=" + str(d["cards"]) +
          " spans=" + str(d["spans"]) + " max=" + str(d["max"]))
    print("      e.g. " + repr(d["ex"][:110]))
if not REPORT_ONLY:
    with open(dst_out, "w") as f:
        for c in cards:
            f.write(json.dumps(c) + "\n")
    print("  wrote scrubbed corpus -> " + dst_out)
else:
    print("  (report only, nothing written)")
