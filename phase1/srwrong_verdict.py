"""Step-1 verdict of the pre-registration, exactly as written before the run.

PASS requires BOTH: run-clustered 95% CI lower bound > 0.5, AND the point estimate stays
> 0.5 after dropping spooky (four earlier directions were carried by that one task alone).

Usage: python phase1/srwrong_verdict.py [hits.jsonl]
"""
import collections, json, math, random, sys

H = sys.argv[1] if len(sys.argv) > 1 else "phase1/hits_l1_uncapped.jsonl"
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d


def sr(cid):
    try:
        v = float(cards[cid]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


rows = []
for l in open(H):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    sb, sw = sr(b), sr(w)
    if sb is None or sw is None or sb == sw:
        continue
    lower = ORI.get(h["task"], False)
    s_ok = int((sb < sw) if lower else (sb > sw))
    rows.append({"rm": h["hit"], "sr": s_ok, "run": RUN.get(b), "task": h["task"]})

print(f"scored pairs with both self-reports: {len(rows)} "
      f"over {len({r['run'] for r in rows})} runs")
print(f"self-report accuracy: {sum(r['sr'] for r in rows)/len(rows):.4f}")
print(f"RM accuracy:          {sum(r['rm'] for r in rows)/len(rows):.4f}")


def boot(sub, nb=4000, seed=7):
    by = collections.defaultdict(list)
    for r in sub:
        by[r["run"]].append(r["rm"])
    runs = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(nb):
        vals = [v for x in (rng.choice(runs) for _ in runs) for v in by[x]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(.025 * nb)], out[int(.975 * nb)], len(runs)


wrong = [r for r in rows if r["sr"] == 0]
k, n = sum(r["rm"] for r in wrong), len(wrong)
lo, hi, nr = boot(wrong)
print(f"\n--- self-report-WRONG subset ---")
print(f"n={n} pairs over {nr} runs; RM {k}/{n} = {k/n:.4f}")
print(f"run-clustered 95% CI [{lo:.4f}, {hi:.4f}]")
cond1 = lo > 0.5
nos = [r for r in wrong if r["task"] != "spooky-author-identification"]
p2 = sum(r["rm"] for r in nos) / len(nos) if nos else float("nan")
lo2, hi2, nr2 = boot(nos) if nos else (0, 0, 0)
print(f"excluding spooky: n={len(nos)} over {nr2} runs, RM {p2:.4f} CI [{lo2:.4f}, {hi2:.4f}]")
cond2 = p2 > 0.5
print(f"\nper task:")
byt = collections.defaultdict(lambda: [0, 0])
for r in wrong:
    byt[r["task"]][0] += r["rm"]
    byt[r["task"]][1] += 1
for t, (a, b) in sorted(byt.items(), key=lambda kv: -kv[1][1]):
    print(f"  {t[:44]:44s} {a:4d}/{b:<4d} = {a/max(b,1):.3f}")
print(f"\nprereg condition 1 (CI lower > 0.5): {'PASS' if cond1 else 'FAIL'} ({lo:.4f})")
print(f"prereg condition 2 (holds without spooky): {'PASS' if cond2 else 'FAIL'} ({p2:.4f})")
print(f"STEP-1 VERDICT: {'PASS -- proceed to sr-cond training' if (cond1 and cond2) else 'FAIL -- line terminates, write as a negative result'}")
