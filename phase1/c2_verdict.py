"""C2 verdict, exactly as pre-registered on 2026-08-09 before any fold was run.

Claim under test: rho(self-report, true grade) -- measurable on a new task with ~20 runs and
no critic training -- predicts how well a learned critic transfers to that task (LOTO
accuracy). If it holds, the deliverable is a cheap go/no-go rule, and it does not require
the critic to beat anything.

Pre-registered criteria, not editable now:
  1. one-sided exact permutation p < 0.01 for Spearman(rho, LOTO), n >= 8 folds
  2. out-of-sample: excluding the five pilot tasks, the direction must still be positive
  3. partial Spearman controlling pair count, card count and grade variance must stay >= +0.5,
     else the relation is confounded by "this task simply has more/cleaner data"

Usage: python phase1/c2_verdict.py
"""
import collections, itertools, json, math, statistics

ORI = json.load(open("phase1/task_orientation.json"))
PILOT = {"mlsp-2013-birds", "chaii-hindi-and-tamil-question-answering",
         "petfinder-pawpularity-score",
         "nomad2018-predict-transparent-conductors", "spooky-author-identification"}

cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def rankv(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        m = (i + j) / 2.0
        for k in range(i, j + 1):
            r[o[k]] = m
        i = j + 1
    return r


def spearman(xs, ys):
    a, b = rankv(xs), rankv(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def partial(x, y, ctrls):
    rx, ry = rankv(x), rankv(y)
    for c in ctrls:
        rc = rankv(c)
        n = len(rc)
        mc = sum(rc) / n
        vc = sum((v - mc) ** 2 for v in rc) or 1e-12
        for tgt in (rx, ry):
            mt = sum(tgt) / n
            beta = sum((p - mc) * (q - mt) for p, q in zip(rc, tgt)) / vc
            for i in range(n):
                tgt[i] -= beta * (rc[i] - mc)
    return spearman(rx, ry)


# --- y: LOTO accuracy, one row per fold -----------------------------------
loto = {}
for line in open("phase1/loto_v4.csv"):
    p = line.strip().split(",")
    if len(p) > 2 and p[1].startswith("loto:"):
        try:
            loto[p[1][5:]] = float(p[2])
        except ValueError:
            pass

# --- x: rho(self-report, true grade), and the confound controls -----------
rho, npairs, ncards, gvar = {}, collections.Counter(), {}, {}
for l in open("phase1/value_pairs_v4.jsonl"):
    npairs[json.loads(l)["task"]] += 1
for t in set(loto):
    sub = [(fin(d["obs"].get("val_at_low")), fin(d["label"].get("graded")))
           for d in cards.values() if d["task"]["name"] == t]
    sub = [(s, g) for s, g in sub if s is not None and g is not None]
    rho[t] = abs(spearman([s for s, _ in sub], [g for _, g in sub]))
    ncards[t] = len(sub)
    gvar[t] = statistics.pstdev([g for _, g in sub]) if len(sub) > 1 else 0.0

tasks = sorted(set(loto) & set(rho))
print(f"folds complete: {len(tasks)}\n")
print(f"{'task':44s} {'rho':>6} {'LOTO':>7} {'pairs':>7} {'cards':>6} {'pilot':>6}")
for t in sorted(tasks, key=lambda x: rho[x]):
    print(f"{t[:44]:44s} {rho[t]:6.3f} {loto[t]:7.4f} {npairs[t]:7d} "
          f"{ncards[t]:6d} {'yes' if t in PILOT else '':>6}")

xs = [rho[t] for t in tasks]
ys = [loto[t] for t in tasks]
r = spearman(xs, ys)
n = len(tasks)
import math as _m, random as _rnd
if _m.factorial(n) <= 4_000_000:
    ge = tot = 0
    for perm in itertools.permutations(range(n)):
        tot += 1
        if spearman(xs, [ys[i] for i in perm]) >= r:
            ge += 1
    method = 'exact'
else:
    # +1 in numerator and denominator: the unbiased Monte-Carlo p, which can never
    # report 0 and stays conservative at small counts
    _g = _rnd.Random(7)
    tot = 200_000
    idx = list(range(n))
    ge = 1
    for _ in range(tot):
        _g.shuffle(idx)
        if spearman(xs, [ys[i] for i in idx]) >= r:
            ge += 1
    tot += 1
    method = 'Monte Carlo'
p1 = ge / tot
print(f"\n[1] Spearman(rho, LOTO) = {r:+.4f}, n={n}")
print(f"    one-sided {method} permutation p = {p1:.4f} over {tot:,} draws")
c1 = (p1 < 0.01 and n >= 8)
print(f"    criterion 1 (p < 0.01, n >= 8): {'PASS' if c1 else 'FAIL'}")

new = [t for t in tasks if t not in PILOT]
if len(new) >= 3:
    rn = spearman([rho[t] for t in new], [loto[t] for t in new])
    print(f"\n[2] out-of-sample on the {len(new)} non-pilot tasks: Spearman = {rn:+.4f}")
    c2 = rn > 0
    print(f"    criterion 2 (direction still positive): {'PASS' if c2 else 'FAIL'}")
else:
    c2 = False
    print("\n[2] too few non-pilot folds")

pr = partial(xs, ys, [[float(npairs[t]) for t in tasks],
                      [float(ncards[t]) for t in tasks],
                      [gvar[t] for t in tasks]])
print(f"\n[3] partial Spearman | pairs, cards, grade-sd = {pr:+.4f}")
c3 = pr >= 0.5
print(f"    criterion 3 (>= +0.50): {'PASS' if c3 else 'FAIL'}")

print(f"\nC2 VERDICT: {'PASS' if (c1 and c2 and c3) else 'FAIL'} "
      f"({'all three pre-registered criteria met' if (c1 and c2 and c3) else 'writes up as a negative / descriptive result per the pre-registration'})")
print("\nfor the record, the pilot (n=5) gave Spearman +1.000, p=0.0083; adding five folds")
print("is the honest test of whether that was a small-sample artefact.")
