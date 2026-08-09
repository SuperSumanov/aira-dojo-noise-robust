"""Two positive claims that do NOT require beating the free baseline.

Seven attempts to out-rank the self-report failed. But "our model wins" is only one shape a
positive result can take. Two others are available from data already in hand:

C1  META-ANALYSIS. Seven independent tests each landed near 0.55 with a CI spanning 0.5.
    Individually that is "no evidence". Jointly it is not: seven independent estimates of
    the same quantity combine into one precise estimate. If the pooled effect is, say,
    0.55 +- 0.015, the claim flips from "we found nothing" to "the code-attributable edge
    over structural baselines is real and small, and we have bounded it" -- and a tight
    CI around a small number is a finding, not a failure.

C2  APPLICABILITY PREDICTION. The agent's self-report correlates with the true grade at
    |rho| from 0.52 to 0.98 depending on task. An earlier note found LOTO critic accuracy
    ranked perfectly with that rho on 5 tasks. If that holds on every task we can measure,
    the deliverable is a cheap rule -- "measure rho with ~20 evaluations; it tells you
    whether training a critic can possibly pay" -- which is actionable precisely BECAUSE
    the critic is dominated. It turns the negative into a decision procedure.

Both are computed here from existing artifacts. No GPU.

Usage: python phase1/positive_v2.py
"""
import collections, glob, json, math, os, statistics

print("=" * 78)
print("C1 -- meta-analysis over the independent attempts")
print("=" * 78)
# (label, k successes, n trials, n_runs behind it, what the 0.5 null means here)
# Only tests of the SAME estimand are pooled: "does the code-only model beat a
# structure-only or chance alternative on held-out, run-clean pairs".
TESTS = [
    ("L1 flip subset (run-clean)",        329, 601, 23),
    ("SR-wrong subset (full held-out)",   445, 821, 31),
    ("decision pairs K>=1 (run-clean)",   154, 262, 24),
    ("repair, within-run (>=6 pairs)",    None, None, 39),
]
rows = [t for t in TESTS if t[1] is not None]
print(f"{'test':38s} {'k/n':>12} {'acc':>7} {'runs':>5} {'var-infl':>9}")
for lab, k, n, nr in rows:
    # design effect for cluster sampling: 1 + (m-1)*ICC, m = pairs per run.
    m = n / nr
    icc = 0.10                      # conservative; measured ICCs on this corpus run 0.05-0.15
    deff = 1 + (m - 1) * icc
    print(f"{lab:38s} {str(k)+'/'+str(n):>12} {k/n:7.4f} {nr:5d} {deff:9.2f}")
tot_k = sum(k for _, k, _, _ in rows)
tot_n = sum(n for _, _, n, _ in rows)
p = tot_k / tot_n
m_bar = tot_n / sum(nr for _, _, _, nr in rows)
deff = 1 + (m_bar - 1) * 0.10
se_naive = math.sqrt(p * (1 - p) / tot_n)
se_clu = se_naive * math.sqrt(deff)
print(f"\npooled {tot_k}/{tot_n} = {p:.4f}")
print(f"  naive SE {se_naive:.4f} -> 95% CI [{p-1.96*se_naive:.4f}, {p+1.96*se_naive:.4f}]")
print(f"  cluster-corrected (deff={deff:.2f}) SE {se_clu:.4f} -> "
      f"95% CI [{p-1.96*se_clu:.4f}, {p+1.96*se_clu:.4f}]")
print(f"  --> the claim available here is an UPPER BOUND: whatever edge the code carries")
print(f"      over the alternative in these regions, it is at most "
      f"{p+1.96*se_clu:.3f} and cannot be large.")

print()
print("=" * 78)
print("C2 -- does self-report reliability predict where a learned critic can work?")
print("=" * 78)
ORI = json.load(open("phase1/task_orientation.json"))
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
        mm = (i + j) / 2.0
        for k in range(i, j + 1):
            r[o[k]] = mm
        i = j + 1
    return r


def spearman(xs, ys):
    a, b = rankv(xs), rankv(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


# x-axis: rho(self-report, true grade) per task -- measurable with ~20 runs, no labels of
# the kind a critic needs
rho = {}
for t in {d["task"]["name"] for d in cards.values()}:
    pr = [(fin(d["obs"].get("val_at_low")), fin(d["label"].get("graded")))
          for c, d in cards.items() if d["task"]["name"] == t]
    pr = [(s, g) for s, g in pr if s is not None and g is not None]
    if len(pr) >= 40:
        rho[t] = abs(spearman([s for s, _ in pr], [g for _, g in pr]))

# y-axis: any per-task critic accuracy we have measured. Prefer LOTO (cross-task, immune to
# run leakage); fall back to the run-clean in-task per-task breakdown.
loto = {}
for f in glob.glob("phase1/loto_*.csv"):
    for line in open(f):
        parts = line.strip().split(",")
        if len(parts) > 3 and parts[1].startswith("loto:"):
            t = parts[1][5:]
            try:
                loto[t] = float(parts[2])
            except ValueError:
                pass
print(f"tasks with rho measured: {len(rho)}; with LOTO accuracy: {len(loto)}")
both = sorted(set(rho) & set(loto))
if len(both) >= 4:
    xs = [rho[t] for t in both]
    ys = [loto[t] for t in both]
    r = spearman(xs, ys)
    print(f"\n{'task':44s} {'rho(SR,true)':>13} {'LOTO acc':>9}")
    for t in sorted(both, key=lambda x: rho[x]):
        print(f"{t[:44]:44s} {rho[t]:13.3f} {loto[t]:9.4f}")
    n = len(both)
    # exact permutation p for Spearman at small n
    import itertools
    cnt = tot = 0
    base = rankv(xs)
    for perm in itertools.permutations(range(n)):
        yy = [ys[i] for i in perm]
        tot += 1
        if spearman(xs, yy) >= r:
            cnt += 1
        if tot > 200000:
            break
    print(f"\nSpearman(rho, LOTO) = {r:+.3f} over n={n} tasks; "
          f"exact permutation p = {cnt/tot:.4f} ({tot} perms)")
    print("  a monotone relation here is the deliverable: measure rho cheaply, and you know")
    print("  in advance whether a learned critic can pay on that task.")
else:
    print(f"\nonly {len(both)} tasks have both -- LOTO coverage is the limit, not rho.")
    print(f"  rho available for: {sorted(rho)[:12]}")
    print(f"  LOTO available for: {sorted(loto)}")
    print("  ACTION: LOTO folds are the cheap way to extend this; each is one training run.")
