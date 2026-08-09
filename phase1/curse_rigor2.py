"""Winner's curse, tested with the generative model the right way round.

My first pass simulated "grade = self-report + independent noise" and then selected the
sibling-best BY self-report. Under that model the noise is independent of the selection, so
no regression can occur by construction -- the positive control was guaranteed to show
nothing, and its silence said nothing about the estimator.

The correct model: latent quality is what the grade measures; the self-report is a NOISY
VIEW of it; the search selects on the noisy view. The selected sibling's view then overstates
its latent quality, by an amount that grows with the number of siblings.

  positive control : synthetic_SR = grade + noise, select argmax(synthetic_SR), measure
                     signed gap (grade - synthetic_SR) in z units. A curse MUST appear.
  negative control : same synthetic SR, but pick a sibling at RANDOM. No curse may appear.
  real data        : the same estimator on the observed self-report and grade.

Reported per k, with run-clustered CIs, and per task -- the two checks that killed seven
directions.

Usage: python phase1/curse_rigor2.py [noise_mult]
"""
import collections, json, math, random, statistics, sys

NOISE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def analyse(view, truth, label, chooser="argmax"):
    """view: cid -> observed score (what selection sees). truth: cid -> ground truth."""
    rng = random.Random(5)
    recs = []
    for t in {d["task"]["name"] for d in cards.values()}:
        pool = [(c, view.get(c), truth.get(c)) for c, d in cards.items()
                if d["task"]["name"] == t]
        pool = [(c, v, g) for c, v, g in pool if v is not None and g is not None]
        if len(pool) < 80:
            continue
        sgn = -1.0 if ORI.get(t, False) else 1.0
        vv = [sgn * v for _, v, _ in pool]
        gg = [sgn * g for _, _, g in pool]
        mv, dv = statistics.mean(vv), statistics.pstdev(vv) or 1.0
        mg, dg = statistics.mean(gg), statistics.pstdev(gg) or 1.0
        zv = {c: (sgn * v - mv) / dv for c, v, _ in pool}
        zg = {c: (sgn * g - mg) / dg for c, _, g in pool}
        for c, _, _ in pool:
            p = cards[c]["lineage"].get("parent_id")
            sib = [x for x in (kids.get(p, []) if p else []) if x in zv]
            k = len(sib)
            if k < 2:
                continue
            if chooser == "argmax":
                sel = max(sib, key=lambda x: zv[x])
            else:
                sel = rng.choice(sib)
            if sel != c:
                continue
            recs.append({"task": t, "run": RUN.get(c), "k": k,
                         "signed": zg[c] - zv[c]})
    print(f"\n--- {label} ---")
    for lo_k, hi_k in ((2, 2), (3, 3), (4, 5), (6, 99)):
        sub = [r for r in recs if lo_k <= r["k"] <= hi_k]
        if len(sub) < 30:
            continue
        by = collections.defaultdict(list)
        for r in sub:
            by[r["run"]].append(r["signed"])
        runs = list(by)
        rng2 = random.Random(7)
        dr = []
        for _ in range(3000):
            vals = [v for x in (rng2.choice(runs) for _ in runs) for v in by[x]]
            dr.append(sum(vals) / len(vals))
        dr.sort()
        print(f"  k in [{lo_k},{hi_k if hi_k < 99 else '+'}]  n={len(sub):5d}  "
              f"signed = {statistics.mean([r['signed'] for r in sub]):+.4f}  "
              f"CI [{dr[75]:+.4f}, {dr[2925]:+.4f}]  ({len(runs)} runs)")
    return recs


grade = {c: fin(d["label"].get("graded")) for c, d in cards.items()}
sr = {c: fin(d["obs"].get("val_at_low")) for c, d in cards.items()}

# synthetic self-report: a noisy VIEW of the grade, noise scaled to each task's grade spread
rng = random.Random(11)
sd = {}
for t in {d["task"]["name"] for d in cards.values()}:
    vs = [grade[c] for c, d in cards.items()
          if d["task"]["name"] == t and grade[c] is not None]
    if len(vs) >= 80:
        sd[t] = (statistics.pstdev(vs) or 1.0) * NOISE
synth = {}
for c, d in cards.items():
    t = d["task"]["name"]
    if grade[c] is None or t not in sd:
        continue
    synth[c] = grade[c] + rng.gauss(0, sd[t])

print(f"positive/negative controls use synthetic self-report = grade + N(0, {NOISE}x task sd)")
analyse(synth, grade, "POSITIVE CONTROL (select argmax of the noisy view) -- curse MUST appear")
analyse(synth, grade, "NEGATIVE CONTROL (select a random sibling) -- no curse may appear",
        chooser="random")
real = analyse(sr, grade, "REAL DATA (observed self-report vs true grade)")

print("\n--- REAL DATA, per task (sibling-best only, k>=2) ---")
byt = collections.defaultdict(list)
for r in real:
    byt[r["task"]].append(r["signed"])
print(f"{'task':44s} {'n':>5} {'signed':>8}")
neg = 0
for t, v in sorted(byt.items(), key=lambda kv: -len(kv[1])):
    if len(v) < 25:
        continue
    m = statistics.mean(v)
    neg += int(m < 0)
    print(f"{t[:44]:44s} {len(v):5d} {m:+8.4f}")
tot = sum(1 for t, v in byt.items() if len(v) >= 25)
print(f"tasks with negative (inflated) mean: {neg}/{tot}")
