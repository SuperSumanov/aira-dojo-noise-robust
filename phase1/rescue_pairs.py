"""Few-shot rescue pairs: LOTO training plus K target-task pairs, evaluated on the target.

The transfer table came back heterogeneous -- petfinder keeps 46% of its in-task margin, chaii
23%, nomad transfers INVERTED (0.4605, 3.5 sigma below chance). The constructive question, and
the price-list the paper needs: how many labeled target pairs does it take to fix each case?

Construction (leakage rules identical to everything else):
  train = every record of every OTHER task (both splits, boost kept)
        + K unique target-task pairs sampled from the target's TRAIN-split records only
          (tree-level split, so no sampled pair shares a tree with the eval set; boost copies
          deduped before sampling so K counts distinct pairs)
  eval  = the target task's TEST-split records, deduped
K=0 reproduces the plain LOTO number by construction, so the curve anchors to a measured point.

Usage: python phase1/rescue_pairs.py OUT PAIRS TARGET_TASK K [--seed 7]
"""
import argparse, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("pairs"); ap.add_argument("target"); ap.add_argument("k", type=int)
ap.add_argument("--base", type=int, default=4000,
                help="records sampled from the other-task pool. Without this cap the trainer's "
                     "sizes=N draw dilutes the injected target records to nothing: 3k injected "
                     "into 138k others at sizes=4000 leaves ~87 target records, a placebo dose.")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
rng = random.Random(a.seed)

recs = [json.loads(l) for l in open(a.pairs)]
others = [r for r in recs if r["task"] != a.target]
rng.shuffle(others)
others = others[:a.base]
tgt_train = [r for r in recs if r["task"] == a.target and r["intask_split"] == "train"]
tgt_test = [r for r in recs if r["task"] == a.target and r["intask_split"] == "test"]

# dedupe boost copies, then sample K distinct pairs and keep ALL budget records of each
by_pair = {}
for r in tgt_train:
    by_pair.setdefault((r["better"], r["worse"]), []).append(r)
uniq = {}
for key, rs in by_pair.items():
    seen_b = set()
    uniq[key] = [r for r in rs if not (r["budget"] in seen_b or seen_b.add(r["budget"]))]
keys = sorted(uniq)
rng.shuffle(keys)
picked = keys[:a.k]
inject = [r for key in picked for r in uniq[key]]

seen_t = set()
test = []
for r in tgt_test:
    key = (r["better"], r["worse"], r.get("budget"))
    if key in seen_t: continue
    seen_t.add(key)
    test.append(r)

with open(a.out, "w") as f:
    for r in others:
        rr = dict(r); rr["intask_split"] = "train"
        f.write(json.dumps(rr) + "\n")
    for r in inject:
        rr = dict(r); rr["intask_split"] = "train"
        f.write(json.dumps(rr) + "\n")
    for r in test:
        rr = dict(r); rr["intask_split"] = "test"
        f.write(json.dumps(rr) + "\n")
print(f"[rescue] target={a.target} K={len(picked)} distinct pairs "
      f"({len(inject)} records) + {len(others)} other-task records; eval={len(test)} records")
assert not ({(r['better'], r['worse']) for r in inject} &
            {(r['better'], r['worse']) for r in test}), "sampled pair leaked into eval"
tr_nodes = {x for r in inject for x in (r["better"], r["worse"])}
te_nodes = {x for r in test for x in (r["better"], r["worse"])}
assert not (tr_nodes & te_nodes), "node-level leak between injected pairs and eval"
print("[rescue] leakage checks: pair-level OK, node-level OK")
