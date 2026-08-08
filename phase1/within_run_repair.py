"""Last standing candidate: the repair question posed WITHIN a run.

The cross-run pairing threw power away -- 883 pairs collapsed to 30 independent test runs.
Inside one run, the run-level variance cancels, which is exactly why the decision-point
result reached p=1.1e-14 on comparatively few pairs. 86 runs contain repairs that disagree.

Pre-registered bar (written before this ran): a paired sign test over runs, p<0.05 AND
effect >= 0.606 -- the smallest effect 86 runs can resolve.

Cheap features are checked FIRST, deliberately. On this corpus a learned model has never
materially exceeded the cheap-feature floor, so if the floor is flat here, a 3-hour training
run is very unlikely to change the verdict, and the check costs seconds.

Per-run score = fraction of that run's discordant pairs the feature gets right; the sign
test then asks how many runs land above 0.5. That keeps the run as the unit throughout.

Usage: python phase1/within_run_repair.py [OUT.jsonl]
"""
import collections, json, math, random, sys
from math import comb

OUT = sys.argv[1] if len(sys.argv) > 1 else "phase1/repair_pairs_withinrun.jsonl"
RUN = json.load(open("phase1/card_run_map.json"))
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


scoreless = {c for c, d in cards.items() if fin(d["obs"].get("val_at_low")) is None}
outcome = {}
for c, d in cards.items():
    p = d["lineage"].get("parent_id")
    if d["lineage"].get("op") == "Debug" and p in scoreless:
        outcome[p] = max(outcome.get(p, 0),
                         int(fin(d["obs"].get("val_at_low")) is not None))

by_run = collections.defaultdict(list)
for c, y in outcome.items():
    if c in RUN:
        by_run[RUN[c]].append((c, y))
mixed = {r: v for r, v in by_run.items() if len({y for _, y in v}) > 1}
print(f"informative runs (repairs disagree within the run): {len(mixed)}")

pairs = []
for r, v in mixed.items():
    wins = [c for c, y in v if y == 1]
    loss = [c for c, y in v if y == 0]
    for a in wins:
        for b in loss:
            pairs.append({"task": cards[a]["task"]["name"], "better": a, "worse": b,
                          "run": r, "budget": 0, "loto_fold": cards[a]["task"]["name"],
                          "clears_tau": None, "src": "repair_withinrun"})
print(f"within-run discordant pairs: {len(pairs)}")
byt = collections.Counter(p["task"] for p in pairs)
print(f"by task: { {t[:26]: n for t, n in byt.most_common(8)} }")


def feat(cid):
    d = cards[cid]
    tail = (d["obs"].get("stdout_tail") or "").lower()
    code = d.get("code") or ""
    return {
        "code_len": float(len(code)),
        "runtime": float(d["obs"].get("runtime_s") or 0),
        "tail_len": float(len(tail)),
        "n_lines": float(code.count(chr(10))),
        "depth": float(d["lineage"].get("depth") or 0),
        "step": float(d["lineage"].get("step") or 0),
        "n_sibs": float(d["lineage"].get("n_siblings") or 0),
    }


FN = list(feat(pairs[0]["better"]).keys())
print(f"\n{'feature':10s} {'pooled':>8} {'runs>.5':>9} {'runs<.5':>9} "
      f"{'sign p':>10} {'mean per-run':>13}")
print("-" * 64)
best = None
for f in FN:
    per_run = {}
    pooled = [0, 0]
    for p in pairs:
        a, b = feat(p["better"])[f], feat(p["worse"])[f]
        if a == b:
            continue
        ok = 1 if a > b else 0
        per_run.setdefault(p["run"], [0, 0])
        per_run[p["run"]][0] += ok
        per_run[p["run"]][1] += 1
        pooled[0] += ok
        pooled[1] += 1
    if pooled[1] < 50 or len(per_run) < 20:
        print(f"{f:10s} (too few: {pooled[1]} pairs / {len(per_run)} runs)")
        continue
    fr = [k / n for k, n in per_run.values()]
    up = sum(1 for v in fr if v > 0.5)
    dn = sum(1 for v in fr if v < 0.5)
    m = up + dn
    pv = min(1.0, sum(comb(m, i) for i in range(0, min(up, dn) + 1)) / 2 ** m * 2) if m else 1.0
    mean_r = sum(fr) / len(fr)
    print(f"{f:10s} {pooled[0]/pooled[1]:8.4f} {up:9d} {dn:9d} {pv:10.3f} {mean_r:13.4f}")
    if best is None or abs(mean_r - 0.5) > abs(best[1] - 0.5):
        best = (f, mean_r, pv, len(per_run))

if best:
    f, mr, pv, nr = best
    print(f"\nstrongest cheap feature: {f} mean per-run {mr:.4f}, sign p={pv:.3f}, {nr} runs")
    print(f"pre-registered bar: effect >= 0.606 AND p < 0.05")
    ok = (mr >= 0.606 or mr <= 0.394) and pv < 0.05
    print(f"cheap-feature floor: {'CLEARS the bar' if ok else 'does NOT clear the bar'}")
    print("\nIf the floor is flat, note what that means here: it does not prove a learned")
    print("model must fail, but on this corpus no learned model has yet exceeded the cheap")
    print("floor by the margin this bar demands.")

with open(OUT, "w") as fh:
    for p in pairs:
        q = dict(p)
        q["intask_split"] = "train"      # split assigned later, by held-out runs
        fh.write(json.dumps(q) + "\n")
print(f"\nwrote {len(pairs)} pairs -> {OUT}")
