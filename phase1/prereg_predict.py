"""Pre-register the collapse predictions BEFORE collecting the data that tests them.

The hypothesis: how far a reward model's cross-generator accuracy falls on a task is predictable
from how diverse that task's solutions are, measured as the Shannon entropy of imported modules.
It rests on 4 measured tasks, where the ordering is monotone -- which happens by chance about
1 in 12 times, and three metrics were tried. That is a hypothesis.

The way to make it testable rather than post-hoc is to fit on those 4 and write down the
predictions for every other task NOW, then collect Qwen data and check. Recorded predictions
that survive are evidence; a curve fitted after seeing all the points is not.

Entropy is computed at a COMMON sample size (n=112, the smallest of the four), averaged over
200 draws, because Shannon entropy is biased upward by sample size and the tasks differ in size.
"""
import ast, collections, json, math, random

cards = collections.defaultdict(list)
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["task"]["name"]].append(d.get("code") or "")


def imports_of(code):
    try:
        tree = ast.parse(code)
    except Exception:
        return None
    s = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            s.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            s.add(n.module.split(".")[0])
    return s


def entropy(c):
    tot = sum(c.values())
    return -sum((v / tot) * math.log2(v / tot) for v in c.values() if v) if tot else 0.0


MEASURED = {"spooky-author-identification": 32.7, "leaf-classification": 26.6,
            "random-acts-of-pizza": 17.5, "tabular-playground-series-dec-2021": 4.2}
rng = random.Random(7)
N = 112
rows = []
for t, cs in cards.items():
    fs = [f for f in (imports_of(c) for c in cs) if f is not None]
    if len(fs) < N:
        continue
    vals = []
    for _ in range(200):
        c = collections.Counter()
        for s in rng.sample(fs, N):
            c.update(s)
        vals.append(entropy(c))
    rows.append((t, sum(vals) / len(vals), len(fs)))

xs = [h for t, h, _ in rows if t in MEASURED]
ys = [MEASURED[t] for t, h, _ in rows if t in MEASURED]
mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
b = my - a * mx
ss = sum((y - my) ** 2 for y in ys)
rs = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
print(f"fit on the 4 measured tasks: gap = {a:.1f} * import_H {b:+.1f}   R2 = {1 - rs / ss:.3f}")
print("(R2 on 4 points with 2 free parameters is not a validation -- it is the fit being recorded.)")
print()
print(f"{'task':42s} {'import_H':>9} {'cards':>6}   {'cross-gen gap (pts)':>22}")
print("-" * 84)
for t, h, n in sorted(rows, key=lambda r: r[1]):
    if t in MEASURED:
        print(f"{t[:42]:42s} {h:>9.3f} {n:>6}   {MEASURED[t]:>13.1f} measured")
    else:
        print(f"{t[:42]:42s} {h:>9.3f} {n:>6}   {a * h + b:>13.1f} PREDICTED")
print()
print("Falsification rule, fixed in advance:")
print("  collect Qwen data on the extremes and check the SIGN and ORDER, not the exact value.")
print("  The hypothesis dies if a low-entropy task collapses more than a high-entropy one,")
print("  or if Spearman rho over all measured tasks drops below 0.6.")
