"""Apply the same yardstick to axis A before spending a GPU hour on it.

Every direction so far died the same death: a pair-level effect that evaporates once the
CI is clustered by run, leaving one task carrying the signal. Axis A must be held to that
standard BEFORE training, not after. Two questions:

  1. How many independent runs does the repair test set actually contain? If the held-out
     side is a handful of runs, no result from it will ever be quotable.
  2. What do cheap features already achieve on that test set, with run-clustered CIs? A
     learned model has to clear this floor; if the floor itself cannot be measured above
     0.5, the experiment cannot produce a quotable positive either.

Usage: python phase1/repair_power.py
"""
import collections, json, math, random, statistics

RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

pairs = [json.loads(l) for l in open("phase1/repair_pairs_v1.jsonl")]
test = [p for p in pairs if p["intask_split"] == "test"]
train = [p for p in pairs if p["intask_split"] == "train"]
tr_runs = {RUN[p[k]] for p in train for k in ("better", "worse")}
te_runs = {RUN[p[k]] for p in test for k in ("better", "worse")}
print(f"pairs: train {len(train)}, test {len(test)}")
print(f"runs:  train {len(tr_runs)}, test {len(te_runs)}, overlap {len(tr_runs & te_runs)}")
te_nodes = {p[k] for p in test for k in ("better", "worse")}
print(f"distinct test endpoints (failed programs): {len(te_nodes)}")
byt = collections.Counter(p["task"] for p in test)
print(f"test pairs by task: {dict(byt)}")
runs_by_task = collections.defaultdict(set)
for p in test:
    runs_by_task[p["task"]].add(RUN[p["better"]])
print(f"test RUNS by task: { {t[:22]: len(v) for t, v in runs_by_task.items()} }")

# effective n is closer to the number of distinct endpoints than to the pair count:
# 883 pairs are all-vs-all combinations of a few dozen programs.
print(f"\n*** effective sample size is ~{len(te_nodes)} programs across "
      f"{len(te_runs)} runs, NOT {len(test)} pairs ***")


def feat(cid):
    d = cards[cid]
    tail = (d["obs"].get("stdout_tail") or "").lower()
    return {
        "code_len": float(len(d.get("code") or "")),
        "runtime": float(d["obs"].get("runtime_s") or 0),
        "tail_len": float(len(tail)),
        "n_sibs": float(d["lineage"].get("n_siblings") or 0),
        "depth": float(d["lineage"].get("depth") or 0),
        "has_tb": float("traceback" in tail),
    }


FN = list(feat(next(iter(te_nodes))).keys())
print(f"\n{'cheap feature':12s} {'acc':>7} {'run-clustered 95% CI':>26} {'n_pairs':>8}")
print("-" * 58)
for f in FN:
    rows = []
    for p in test:
        a, b = feat(p["better"])[f], feat(p["worse"])[f]
        if a == b:
            continue
        rows.append({"ok": 1.0 if a > b else 0.0, "run": RUN[p["better"]]})
    if len(rows) < 30:
        print(f"{f:12s} {'--':>7}  (only {len(rows)} usable pairs)")
        continue
    acc = sum(r["ok"] for r in rows) / len(rows)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["run"]].append(r["ok"])
    runs = list(by)
    rng = random.Random(7)
    draws = []
    for _ in range(4000):
        vals = [v for x in (rng.choice(runs) for _ in runs) for v in by[x]]
        draws.append(sum(vals) / len(vals))
    draws.sort()
    lo, hi = draws[100], draws[3900]
    flag = "  <- clears 0.5" if (lo > 0.5 or hi < 0.5) else ""
    print(f"{f:12s} {acc:7.4f}  [{lo:.4f}, {hi:.4f}] ({len(runs):2d} runs) {len(rows):8d}{flag}")

print("\nread: if no cheap feature can be resolved away from 0.5 with this many runs,")
print("the test set cannot support a quotable learned result either -- the limit is the")
print("number of independent runs, and no model changes that.")
