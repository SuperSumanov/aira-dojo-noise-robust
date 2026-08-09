"""Hold the winner's-curse refutation to the same yardstick that killed seven directions.

The claim: the val->test gap in MLE agents is NOT best-of-k selection noise. Evidence so
far is a pooled rho(sibling count, |gap|) = -0.185 and sibling-best nodes having SMALLER
gaps. Before this is written down as a finding it must survive exactly what the failures
did not:
  1. per-task consistency -- five earlier directions were one task in disguise
  2. run-clustered CIs, not pair/node-level ones
  3. the positive control: winner's curse makes a SIGNED prediction. The inflation of the
     argmax of k draws grows roughly like sqrt(2 ln k) * sigma, so the signed gap of the
     sibling-best node should become more negative (true < reported) as k rises. Testing
     the signed, k-scaled form is much stronger than testing |gap|.
  4. a sanity check that the machinery CAN see a curse: simulate one on our own numbers by
     replacing the true grade with self-report + noise, then re-run the same estimator. If
     the simulated curse shows up and the real data does not, the null is informative
     rather than merely underpowered.

Usage: python phase1/curse_rigor.py
"""
import collections, json, math, random, statistics

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


def build(grade_fn):
    """recs of (task, run, k_sib, is_best, signed z-gap, |z-gap|) under a grade source."""
    out = []
    for t in {d["task"]["name"] for d in cards.values()}:
        sub = []
        for c, d in cards.items():
            if d["task"]["name"] != t:
                continue
            s, g = fin(d["obs"].get("val_at_low")), grade_fn(c, d)
            if s is not None and g is not None:
                sub.append((c, s, g))
        if len(sub) < 80:
            continue
        sgn = -1.0 if ORI.get(t, False) else 1.0
        ss = [sgn * s for _, s, _ in sub]
        gg = [sgn * g for _, _, g in sub]
        ms, ds = statistics.mean(ss), statistics.pstdev(ss) or 1.0
        mg, dg = statistics.mean(gg), statistics.pstdev(gg) or 1.0
        for (c, _, _), s, g in zip(sub, ss, gg):
            zs, zg = (s - ms) / ds, (g - mg) / dg
            p = cards[c]["lineage"].get("parent_id")
            sib = [(x, fin(cards[x]["obs"].get("val_at_low")))
                   for x in (kids.get(p, []) if p else []) if x in cards]
            sib = [(x, v) for x, v in sib if v is not None]
            k = len(sib)
            best = 0
            if k >= 2:
                top = max(sib, key=lambda kv: sgn * kv[1])[0]
                best = int(top == c)
            out.append({"task": t, "run": RUN.get(c), "k": k, "best": best,
                        "signed": zg - zs, "abs": abs(zg - zs)})
    return out


def clustered_ci(vals_by_run, nb=3000, seed=7):
    runs = list(vals_by_run)
    rng = random.Random(seed)
    dr = []
    for _ in range(nb):
        vals = [v for x in (rng.choice(runs) for _ in runs) for v in vals_by_run[x]]
        dr.append(sum(vals) / len(vals))
    dr.sort()
    return dr[int(.025 * nb)], dr[int(.975 * nb)], len(runs)


real = build(lambda c, d: fin(d["label"].get("graded")))
print(f"nodes with both scores: {len(real)}")

print("\n" + "=" * 78)
print("1+2) per task, with run-clustered CI on the signed gap of sibling-BEST nodes")
print("=" * 78)
print(f"{'task':40s} {'n_best':>7} {'signed':>8} {'run-clustered CI':>22} {'rho(k,|gap|)':>13}")
print("-" * 94)
consistent = [0, 0]
for t in sorted({r["task"] for r in real}):
    sub = [r for r in real if r["task"] == t and r["k"] >= 2]
    bst = [r for r in sub if r["best"] == 1]
    if len(bst) < 25:
        continue
    by = collections.defaultdict(list)
    for r in bst:
        by[r["run"]].append(r["signed"])
    lo, hi, nr = clustered_ci(by)
    m = statistics.mean([r["signed"] for r in bst])
    rho = spearman([r["k"] for r in sub], [r["abs"] for r in sub]) if len(sub) > 30 else float("nan")
    consistent[0] += int(rho < 0)
    consistent[1] += 1
    print(f"{t[:40]:40s} {len(bst):7d} {m:+8.3f} [{lo:+.3f}, {hi:+.3f}] ({nr:2d}r) {rho:13.3f}")
print(f"\ntasks with NEGATIVE rho(sibling count, |gap|): {consistent[0]}/{consistent[1]}")

print("\n" + "=" * 78)
print("3) the signed, k-scaled test -- winner's curse predicts signed gap falls with k")
print("=" * 78)
for lo_k, hi_k in ((2, 2), (3, 3), (4, 5), (6, 99)):
    bst = [r for r in real if r["best"] == 1 and lo_k <= r["k"] <= hi_k]
    if len(bst) < 30:
        continue
    by = collections.defaultdict(list)
    for r in bst:
        by[r["run"]].append(r["signed"])
    lo, hi, nr = clustered_ci(by)
    print(f"  k in [{lo_k},{hi_k if hi_k<99 else '+'}]  n={len(bst):5d}  "
          f"mean signed = {statistics.mean([r['signed'] for r in bst]):+.4f}  "
          f"CI [{lo:+.4f}, {hi:+.4f}]  ({nr} runs)")
print("  winner's curse would make these increasingly negative; flat or rising refutes it.")

print("\n" + "=" * 78)
print("4) positive control -- can this estimator SEE a curse that is really there?")
print("=" * 78)
rng = random.Random(11)
noise_sd = {}
for t in {d["task"]["name"] for d in cards.values()}:
    vs = [fin(d["obs"].get("val_at_low")) for c, d in cards.items()
          if d["task"]["name"] == t]
    vs = [v for v in vs if v is not None]
    if len(vs) >= 80:
        noise_sd[t] = (statistics.pstdev(vs) or 1.0)
# simulate: true grade = self-report + independent noise. Then the argmax over siblings is
# inflated purely by selection -- a textbook curse, with no code-attributable component.
sim_cache = {}
for c, d in cards.items():
    t = d["task"]["name"]
    s = fin(d["obs"].get("val_at_low"))
    if s is None or t not in noise_sd:
        continue
    sim_cache[c] = s + rng.gauss(0, noise_sd[t])
sim = build(lambda c, d: sim_cache.get(c))
for lo_k, hi_k in ((2, 2), (3, 3), (4, 5), (6, 99)):
    bst = [r for r in sim if r["best"] == 1 and lo_k <= r["k"] <= hi_k]
    if len(bst) < 30:
        continue
    print(f"  SIMULATED k in [{lo_k},{hi_k if hi_k<99 else '+'}]  n={len(bst):5d}  "
          f"mean signed = {statistics.mean([r['signed'] for r in bst]):+.4f}")
rho_sim = spearman([r["k"] for r in sim if r["k"] >= 2],
                   [r["abs"] for r in sim if r["k"] >= 2])
rho_real = spearman([r["k"] for r in real if r["k"] >= 2],
                    [r["abs"] for r in real if r["k"] >= 2])
print(f"\n  rho(k, |gap|): SIMULATED curse {rho_sim:+.3f} vs REAL data {rho_real:+.3f}")
print("  if the simulated curse is clearly positive and the real one is not, the refutation")
print("  is a measurement, not a failure to measure.")
