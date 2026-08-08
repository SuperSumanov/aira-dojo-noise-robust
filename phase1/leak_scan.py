"""Does stdout_tail actually contain verbatim Kaggle Competition Data?

Kaggle Standard Rules 7.B forbids redistributing Competition Data. Our cards keep the last
800 chars of execution output, and agents habitually print df.head() / sample rows, so this
is the one field that could carry real records. Empirical question -- match the tails
against each competition's own prepared files.

Direction matters for speed: the tails are tiny (~800 chars each) and the source is tens of
MB, so push the search into C by calling str.find with tail-derived needles, instead of
sliding a window over the source in Python (the first version did that and timed out).

Note pandas reformats df.head() with column padding, so a printed row is usually NOT a
verbatim CSV line. That is why we also probe fixed-width windows inside each tail line --
free-text columns (comments, sentences) survive printing intact and are the real exposure.

Usage: python phase1/leak_scan.py [minlen] [max_cards_per_task] [src_budget_mb]
"""
import collections, glob, json, os, sys

MINLEN = int(sys.argv[1]) if len(sys.argv) > 1 else 40
CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 200
BUDGET = (int(sys.argv[3]) if len(sys.argv) > 3 else 40) * 1_000_000
DATA = "/research/d7/spc/yzyang4/mle-bench-data"

by_task = collections.defaultdict(list)
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    t = d["task"]["name"]
    if len(by_task[t]) < CAP:
        by_task[t].append(d["obs"].get("stdout_tail") or "")


def load_source(task):
    buf, n = [], 0
    for ext in ("csv", "json", "txt", "tsv"):
        for f in sorted(glob.glob(f"{DATA}/{task}/prepared/**/*.{ext}", recursive=True)):
            if n >= BUDGET:
                break
            try:
                with open(f, errors="ignore") as fh:
                    s = fh.read(BUDGET - n)
            except OSError:
                continue
            buf.append(s)
            n += len(s)
    return "".join(buf)


def needles(tail):
    """Candidate verbatim spans: whole long lines, plus windows inside them."""
    out = set()
    for line in tail.splitlines():
        line = line.strip()
        if len(line) < MINLEN:
            continue
        out.add(line)
        for i in range(0, len(line) - MINLEN + 1, max(MINLEN // 4, 1)):
            out.add(line[i:i + MINLEN])
    return out


print(f"stdout_tail vs prepared data | minlen={MINLEN} cap={CAP}/task "
      f"budget={BUDGET//1_000_000}MB", flush=True)
print(f"{'task':44s} {'cards':>6} {'hits':>5} {'rate':>7} {'longest':>8}", flush=True)
print("-" * 76, flush=True)

tot_hit = tot = 0
examples, nosrc = {}, []
for t in sorted(by_task):
    src = load_source(t)
    n = len(by_task[t])
    if not src:
        nosrc.append(t)
        print(f"{t[:44]:44s} {n:>6} {'-':>5} {'NO SRC':>7}", flush=True)
        continue
    hits, longest, ex = 0, 0, None
    for tail in by_task[t]:
        found = None
        for nd in needles(tail):
            if nd in src:
                if found is None or len(nd) > len(found):
                    found = nd
        if found:
            hits += 1
            if len(found) > longest:
                longest, ex = len(found), found
    tot_hit += hits
    tot += n
    if ex:
        examples[t] = ex
    print(f"{t[:44]:44s} {n:>6} {hits:>5} {hits/max(n,1):>6.1%} {longest:>8}", flush=True)

print(f"\nTOTAL sampled {tot} cards; {tot_hit} contain verbatim source text "
      f"({tot_hit/max(tot,1):.1%})", flush=True)
if nosrc:
    print(f"no prepared data on disk (unscanned): {nosrc}", flush=True)
print("\n--- longest verbatim match per affected task (repr, 240 chars) ---", flush=True)
for t, ex in sorted(examples.items(), key=lambda kv: -len(kv[1])):
    print(f"\n[{t}] {len(ex)} chars:\n   {ex[:240]!r}", flush=True)
