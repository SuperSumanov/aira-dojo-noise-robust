"""Did truncating the judge's reasoning change its answers?

79% of answers were salvaged by regex from a cut-off reasoning trace rather than read from
a completed `content` field. If the completed subset behaves differently, the measurement
is about our token budget, not about the judge, and the run has to be repeated with room
to think.
"""
import collections, json, math, random, sys

rows = [json.loads(l) for l in open(sys.argv[1])]
ok = [r for r in rows if r.get("correct") is not None]
clean = [r for r in ok if not r.get("truncated")]
salv = [r for r in ok if r.get("truncated")]


def boot(rs, nb=4000):
    by = collections.defaultdict(list)
    for r in rs:
        by[r["run"]].append(float(r["correct"]))
    runs = list(by)
    if not runs:
        return float("nan"), float("nan")
    rnd = random.Random(7)
    d = []
    for _ in range(nb):
        v = [x for q in (rnd.choice(runs) for _ in runs) for x in by[q]]
        d.append(sum(v) / len(v))
    d.sort()
    return d[int(.025 * nb)], d[int(.975 * nb)]


for name, rs in (("completed reasoning", clean), ("salvaged from cut-off", salv)):
    if not rs:
        continue
    acc = sum(r["correct"] for r in rs) / len(rs)
    lo, hi = boot(rs)
    print(f"{name:24s} n={len(rs):4d}  acc={acc:.4f}  CI [{lo:.4f}, {hi:.4f}]")
# per-call basis here (not order-averaged) so the two subsets are directly comparable
print("\nnote: per-call accuracy, not order-averaged, so the two rows are comparable.")
