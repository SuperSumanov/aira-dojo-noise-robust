"""Recon round 2: fix axis A's detector, and test whether B and C are actually PREDICTABLE.

Round 1 mis-detected failures (obs.error is never populated) yet showed the Debug operator
produced 47% of all nodes -- repair decisions are everywhere, I just looked at the wrong
field. Round 1 also showed B and C have the right *shape* (per-node variance / balanced
classes); shape is necessary, not sufficient. Before proposing GPU work, cheap observable
features must show SOME signal, and crucially some signal that is NOT just a restatement of
the self-report level itself.

A  failures redefined as "no self-report" (the node produced nothing scoreable). Measure the
   repair decision: does a Debug child's outcome vary, and is the parent's identity
   informative about it?
B  regress |gap| on cheap observables via leave-one-task-out Spearman. The control that
   matters: partial correlation holding the self-report LEVEL fixed -- otherwise "high
   reported score is more likely inflated" is regression to the mean, not a finding.
C  predict "will improve after step K" from step-K-visible features only, leave-one-task-out.

Usage: python phase1/recon2.py [cards.jsonl]
"""
import collections, json, math, statistics, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current_v7.jsonl"
ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open(PATH):
    d = json.loads(l)
    cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)


def _fin(x):
    """NaN grades exist in the corpus; they poison every downstream statistic."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def sr_of(d):
    return _fin(d["obs"].get("val_at_low"))


def spearman(xs, ys):
    def rank(v):
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
    a, b = rank(xs), rank(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def partial_spearman(x, y, z_):
    """rho(x,y | z) via rank residuals -- kills 'the level explains it' confounds."""
    rxy, rxz, ryz = spearman(x, y), spearman(x, z_), spearman(y, z_)
    den = math.sqrt(max((1 - rxz ** 2) * (1 - ryz ** 2), 1e-12))
    return (rxy - rxz * ryz) / den


# ---------------------------------------------------------------- A (redone)
print("=" * 78)
print("AXIS A (redone) -- repair decisions: op=Debug, failure = no self-report")
print("=" * 78)
noscore = {c for c, d in cards.items() if sr_of(d) is None}
dbg = [c for c, d in cards.items() if d["lineage"].get("op") == "Debug"]
print(f"nodes with no self-report: {len(noscore)}   Debug-produced nodes: {len(dbg)}")
par_broken = [c for c in dbg if cards[c]["lineage"].get("parent_id") in noscore]
print(f"Debug nodes whose PARENT had no self-report (true repair attempts): {len(par_broken)}")
rescued = [c for c in par_broken if sr_of(cards[c]) is not None]
graded = [c for c in par_broken if cards[c]["label"].get("graded") is not None]
print(f"  of those, the repair itself produced a score: {len(rescued)} "
      f"({len(rescued)/max(len(par_broken),1):.1%})  <- the decision's outcome variable")
print(f"  of those, graded: {len(graded)}")
byt = collections.Counter(cards[c]["task"]["name"] for c in par_broken)
print(f"  tasks with >=30 repair attempts: "
      f"{ {t: n for t, n in byt.items() if n >= 30} }")
tot = sum(n for n in byt.values() if n >= 30)
print(f"  VERDICT A: {'GO' if tot >= 300 else 'DEAD'} "
      f"(usable repair decisions on >=30-per-task tasks: {tot})")

# ---------------------------------------------------------------- B
print()
print("=" * 78)
print("AXIS B -- is |self-report - true grade| predictable from cheap observables?")
print("=" * 78)


def feats(d):
    code = d.get("code") or ""
    obs = d["obs"]
    try:
        rt = float(obs.get("runtime_s"))
    except (TypeError, ValueError):
        rt = 0.0
    vc = obs.get("val_curve")
    try:
        vcn = len(json.loads(vc)) if isinstance(vc, str) else len(vc or [])
    except Exception:
        vcn = 0
    low = code.lower()
    return {
        "code_len": float(len(code)),
        "runtime": rt,
        "val_curve_n": float(vcn),
        "depth": float(d["lineage"].get("depth") or 0),
        "n_siblings": float(d["lineage"].get("n_siblings") or 0),
        # mechanism-flavoured: signatures of tuning hard against one's own split
        "n_cv": float(low.count("kfold") + low.count("cross_val") + low.count("stratifiedk")),
        "n_seed": float(low.count("seed")),
        "n_ensemble": float(low.count("ensemble") + low.count("blend") + low.count("stack")),
        "n_earlystop": float(low.count("early_stop")),
        "n_param": float(low.count("param_grid") + low.count("optuna")
                         + low.count("hyperopt") + low.count("gridsearch")),
    }


rows = []
for cid, d in cards.items():
    s, g = sr_of(d), _fin(d["label"].get("graded"))
    if s is None or g is None:
        continue
    rows.append((d["task"]["name"], s, g, feats(d)))
tasks = [t for t, n in collections.Counter(r[0] for r in rows).items() if n >= 80]
print(f"rows={len(rows)}, tasks with >=80: {len(tasks)}")

FN = list(feats(next(iter(cards.values()))).keys())
agg = {f: [] for f in FN}
agg_part = {f: [] for f in FN}
for t in tasks:
    sub = [r for r in rows if r[0] == t]
    sgn = -1.0 if ORI.get(t, False) else 1.0
    ss = [sgn * r[1] for r in sub]
    gg = [sgn * r[2] for r in sub]
    mus, sds = statistics.mean(ss), statistics.pstdev(ss) or 1.0
    mug, sdg = statistics.mean(gg), statistics.pstdev(gg) or 1.0
    zs = [(v - mus) / sds for v in ss]
    zg = [(v - mug) / sdg for v in gg]
    gap = [abs(a - b) for a, b in zip(zs, zg)]
    for f in FN:
        xs = [r[3][f] for r in sub]
        if statistics.pstdev(xs) < 1e-12:
            continue
        agg[f].append(spearman(xs, gap))
        agg_part[f].append(partial_spearman(xs, gap, zs))
print(f"\n{'feature':14s} {'mean rho(|gap|)':>16} {'mean partial|SR':>17} {'tasks':>6}")
print("-" * 60)
best = []
for f in FN:
    if not agg[f]:
        continue
    m, mp = statistics.mean(agg[f]), statistics.mean(agg_part[f])
    best.append((abs(mp), f, m, mp, len(agg[f])))
    print(f"{f:14s} {m:16.3f} {mp:17.3f} {len(agg[f]):6d}")
best.sort(reverse=True)
top = best[0] if best else (0, "-", 0, 0, 0)
print(f"\nstrongest partial: {top[1]} rho={top[3]:+.3f}")
print(f"  VERDICT B: {'GO' if top[0] >= 0.12 else 'WEAK'} "
      f"(a cheap feature must survive controlling for the self-report level; "
      f"a learned model should beat this floor, not merely match it)")

# ---------------------------------------------------------------- C
print()
print("=" * 78)
print("AXIS C -- is 'will this run improve after step K' predictable at step K?")
print("=" * 78)
K = 5
runs = collections.defaultdict(list)
for cid, d in cards.items():
    g = _fin(d["label"].get("graded"))
    runs[d["run_id"]].append((d["lineage"].get("step") or 0, g, d, cid))
data = []
for r, v in runs.items():
    v.sort(key=lambda x: x[0])
    gr = [(s, g, d) for s, g, d in [(a, b, c) for a, b, c, _ in v] if g is not None]
    if len(gr) <= K:
        continue
    t = gr[0][2]["task"]["name"]
    pick = min if ORI.get(t, False) else max
    early = pick(g for _, g, _ in gr[:K])
    final = pick(g for _, g, _ in gr)
    improved = int((final < early - 1e-12) if ORI.get(t, False) else (final > early + 1e-12))
    head = [d for _, _, d in gr[:K]]
    srs = [x for x in (sr_of(d) for d in head) if x is not None]
    sgn = -1.0 if ORI.get(t, False) else 1.0
    zsr = [sgn * x for x in srs]
    # everything here is visible at step K -- no peeking at the future
    data.append((t, improved, {
        "n_graded_at_K": float(len(gr[:K])),
        "sr_spread": float(max(zsr) - min(zsr)) if len(zsr) > 1 else 0.0,
        "sr_best": float(max(zsr)) if zsr else 0.0,
        "sr_last_minus_best": float(zsr[-1] - max(zsr)) if zsr else 0.0,
        "improving_streak": float(sum(1 for a, b in zip(zsr, zsr[1:]) if b > a)),
        "mean_runtime": statistics.mean(
            [float(d["obs"].get("runtime_s") or 0) for d in head]),
        "n_no_score": float(sum(1 for d in head if sr_of(d) is None)),
        "mean_code_len": statistics.mean([float(len(d.get("code") or "")) for d in head]),
        "max_depth_at_K": float(max((d["lineage"].get("depth") or 0) for d in head)),
    }))
print(f"eligible runs (>{K} graded nodes): {len(data)}; "
      f"improve rate {sum(d[1] for d in data)/len(data):.1%}")
tsk = [t for t, n in collections.Counter(d[0] for d in data).items() if n >= 20]
print(f"tasks with >=20 eligible runs: {len(tsk)} {tsk}")
FN2 = list(data[0][2].keys())
print(f"\n{'feature':20s} {'pooled rho(improve)':>20}")
print("-" * 44)
scores = []
for f in FN2:
    xs = [d[2][f] for d in data]
    ys = [float(d[1]) for d in data]
    if statistics.pstdev(xs) < 1e-12:
        continue
    r = spearman(xs, ys)
    scores.append((abs(r), f, r))
    print(f"{f:20s} {r:20.3f}")
scores.sort(reverse=True)
print(f"\nstrongest: {scores[0][1]} rho={scores[0][2]:+.3f}" if scores else "")
print(f"  VERDICT C: {'GO' if scores and scores[0][0] >= 0.15 else 'WEAK'} "
      f"(cheap trajectory features must already carry signal; "
      f"n={len(data)} runs is the honest sample size)")
