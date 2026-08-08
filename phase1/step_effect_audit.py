"""Is "later failures are more repairable" real, or another weighting artifact?

Within-run pairing gave step a per-run mean of 0.683 (sign p<0.001) while the POOLED number
is only 0.573. That gap is the same shape as the lookahead-label confound we already got
burned by: per-run means weight a run holding one pair the same as a run holding hundreds,
and a one-pair run scores exactly 0 or 1.

Five checks, any of which can kill it:
  1. pairs-per-run distribution, and the per-run mean restricted to runs with >=3 pairs
  2. does it survive inside the dominant task (birds is 1603/2299 pairs) alone
  3. per-task direction -- one task carrying it has killed four earlier directions
  4. CENSORING: a run cut off by the wall clock leaves late repairs unfinished. If late
     failures look MORE repairable, censoring works against us, but the mirror artifact is
     that a *successful* repair extends the run and generates more late nodes. Test by
     dropping each run's final steps.
  5. is step just a proxy for the operator that produced the failed node (Draft failures
     early, Improve failures late, with different intrinsic repairability)?

Usage: python phase1/step_effect_audit.py
"""
import collections, json, math, statistics
from math import comb

RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
pairs = [json.loads(l) for l in open("phase1/repair_pairs_withinrun.jsonl")]


def st(cid):
    return float(cards[cid]["lineage"].get("step") or 0)


def sign_test(per_run):
    fr = [k / n for k, n in per_run.values() if n]
    up = sum(1 for v in fr if v > 0.5)
    dn = sum(1 for v in fr if v < 0.5)
    m = up + dn
    pv = (min(1.0, sum(comb(m, i) for i in range(0, min(up, dn) + 1)) / 2 ** m * 2)
          if m else 1.0)
    return (statistics.mean(fr) if fr else float("nan")), up, dn, pv, len(fr)


def evaluate(sub, label):
    per_run, pooled = {}, [0, 0]
    for p in sub:
        a, b = st(p["better"]), st(p["worse"])
        if a == b:
            continue
        ok = 1 if a > b else 0
        per_run.setdefault(p["run"], [0, 0])
        per_run[p["run"]][0] += ok
        per_run[p["run"]][1] += 1
        pooled[0] += ok
        pooled[1] += 1
    if pooled[1] == 0:
        print(f"{label:38s} (no usable pairs)")
        return
    m, up, dn, pv, nr = sign_test(per_run)
    print(f"{label:38s} pooled={pooled[0]/pooled[1]:.4f} per-run={m:.4f} "
          f"({up}+/{dn}-) p={pv:.4f} runs={nr} pairs={pooled[1]}")


print("1) pairs per run")
cnt = collections.Counter(p["run"] for p in pairs)
dist = collections.Counter(min(v, 10) for v in cnt.values())
print(f"   distribution (capped at 10): {dict(sorted(dist.items()))}")
print(f"   runs with exactly 1 pair: {sum(1 for v in cnt.values() if v == 1)}")
print()
evaluate(pairs, "ALL")
evaluate([p for p in pairs if cnt[p["run"]] >= 3], ">=3 pairs/run")
evaluate([p for p in pairs if cnt[p["run"]] >= 6], ">=6 pairs/run")

print("\n2)+3) per task")
for t in sorted({p["task"] for p in pairs}):
    sub = [p for p in pairs if p["task"] == t]
    if len(sub) >= 20:
        evaluate(sub, "   " + t[:34])

print("\n4) censoring: drop each run's last steps")
maxstep = {}
for p in pairs:
    for k in ("better", "worse"):
        maxstep[p["run"]] = max(maxstep.get(p["run"], 0), st(p[k]))
for frac in (0.9, 0.75, 0.5):
    sub = [p for p in pairs
           if st(p["better"]) <= frac * maxstep[p["run"]]
           and st(p["worse"]) <= frac * maxstep[p["run"]]]
    evaluate(sub, f"   first {int(frac*100)}% of each run")

print("\n5) is step a proxy for the failed node's own operator?")
ops = collections.Counter(cards[p["better"]]["lineage"].get("op") for p in pairs)
ops_w = collections.Counter(cards[p["worse"]]["lineage"].get("op") for p in pairs)
print(f"   op of repairable endpoint:   {dict(ops)}")
print(f"   op of unrepairable endpoint: {dict(ops_w)}")
same = [p for p in pairs
        if cards[p["better"]]["lineage"].get("op") == cards[p["worse"]]["lineage"].get("op")]
evaluate(same, "   same-operator pairs only")

print("\n6) direct check: is the OUTCOME itself trending with step?")
out = []
for p in pairs:
    out.append((st(p["better"]), 1))
    out.append((st(p["worse"]), 0))
seen = {}
for s, y in out:
    seen.setdefault(round(s / 5) * 5, [0, 0])
    seen[round(s / 5) * 5][0] += y
    seen[round(s / 5) * 5][1] += 1
print("   step-bucket -> repair success rate (endpoint level, deduped by pair membership)")
for b in sorted(seen)[:12]:
    a, n = seen[b]
    print(f"     step~{b:4.0f}  {a:5d}/{n:<5d} = {a/n:.3f}")
