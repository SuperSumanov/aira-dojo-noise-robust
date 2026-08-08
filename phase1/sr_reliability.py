"""rho(self-report, true grade) per task -- the free competitor's strength spectrum.

Direction B of the 08-06 critique doc: before training a critic on a new task, measure
this with ~20 evaluations. rho > 0.85 means a learned critic can only parrot the
self-report; rho < 0.70 means there is room but learning is hardest there. |Spearman| is
used because half the tasks are lower-is-better.

Usage: python phase1/sr_reliability.py [cards.jsonl] [min_n]
"""
import collections, json, math, sys

path = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current.jsonl"
MIN_N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

seen, by = set(), collections.defaultdict(list)
for l in open(path):
    d = json.loads(l)
    if d["id"] in seen:
        continue
    seen.add(d["id"])
    g = (d.get("label") or {}).get("graded")
    t = (d.get("task") or {}).get("name")
    try:
        s = float((d.get("obs") or {}).get("val_at_low"))
    except (TypeError, ValueError):
        continue
    if g is not None and t:
        by[t].append((s, float(g)))


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):          # mean ranks for ties, else heavy-tie tasks distort
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            m = (i + j) / 2.0
            for k in range(i, j + 1):
                r[order[k]] = m
            i = j + 1
        return r
    a, b = rank(xs), rank(ys)
    n = len(xs)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


out = []
for t, v in by.items():
    if len(v) >= MIN_N:
        out.append((abs(spearman([x for x, _ in v], [y for _, y in v])), len(v), t))
out.sort()
print(f"unique cards with (self-report, grade): {sum(len(v) for v in by.values())}")
print(f"\n{'task':46s} {'n':>5} {'|rho|':>7} {'R2':>6}")
print("-" * 68)
for r, n, t in out:
    print(f"{t[:46]:46s} {n:5d} {r:7.3f} {r*r:6.3f}")
print("-" * 68)
w = sum(n for _, n, _ in out)
print(f"weighted |rho| = {sum(n*r for r, n, _ in out)/w:.3f}   "
      f"weighted R2 = {sum(n*r*r for r, n, _ in out)/w:.3f}   tasks = {len(out)}")
print(f"rho<0.70 (room): {[t[:24] for r,_,t in out if r < 0.70]}")
print(f"rho>0.90 (no room): {[t[:24] for r,_,t in out if r > 0.90]}")
