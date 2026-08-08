"""How long are the verbatim spans, really?

leak_scan reported 'longest 40' for chaii and google-quest, but 40 is exactly its needle
size -- a floor, not a measurement. The scrub-vs-no-action decision turns on whether these
are ~40-char incidental overlaps or whole passages, so extend each hit greedily in both
directions and report the true span, with the full card context.

Usage: python phase1/leak_extent.py [task ...]
"""
import glob, json, sys

DATA = "/research/d7/spc/yzyang4/mle-bench-data"
MINLEN = 40
TASKS = sys.argv[1:] or ["chaii-hindi-and-tamil-question-answering",
                         "google-quest-challenge"]


def load_source(task, budget=40_000_000):
    buf, n = [], 0
    for ext in ("csv", "json", "txt", "tsv"):
        for f in sorted(glob.glob(f"{DATA}/{task}/prepared/**/*.{ext}", recursive=True)):
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


cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    if d["task"]["name"] in TASKS:
        cards.setdefault(d["task"]["name"], []).append(d)

for task in TASKS:
    src = load_source(task)
    lst = cards.get(task, [])
    print(f"\n{'='*78}\n{task}: {len(lst)} cards, source {len(src)/1e6:.1f}MB")
    worst = []
    for d in lst:
        tail = d["obs"].get("stdout_tail") or ""
        best = ""
        for line in tail.splitlines():
            line = line.strip()
            if len(line) < MINLEN:
                continue
            for i in range(0, len(line) - MINLEN + 1, 5):
                w = line[i:i + MINLEN]
                if w not in src:
                    continue
                lo, hi = i, i + MINLEN
                while hi < len(line) and line[lo:hi + 1] in src:
                    hi += 1
                while lo > 0 and line[lo - 1:hi] in src:
                    lo -= 1
                if hi - lo > len(best):
                    best = line[lo:hi]
        if best:
            worst.append((len(best), d["id"], best, tail))
    worst.sort(reverse=True)
    print(f"cards with verbatim source: {len(worst)}/{len(lst)}")
    if worst:
        print(f"span lengths: {[w[0] for w in worst]}")
    for n, cid, span, tail in worst[:3]:
        print(f"\n--- {cid[-24:]}  span={n} chars ---")
        print(f"  MATCH: {span[:300]!r}")
        print(f"  FULL TAIL ({len(tail)} chars): {tail[:400]!r}")
