"""Manifest for the decision-cost dose-response experiment.

The execution cliff is currently binary: free signals sit at chance, one full cheap
execution buys ~20 top-1 points. This experiment turns the cliff into a curve -- selection
accuracy as a function of SECONDS OF EXECUTION PER CANDIDATE -- by re-running every child
of a sample of real sibling sets under wall-clock caps. The full-fidelity endpoint is free:
the corpus already holds each child's completed-run val_at_low and graded.

Sampling: sibling sets from the b0 TEST universe (no training happens here; this is pure
measurement, and staying inside the frozen evaluation universe keeps every number
comparable with the regret frontier). Stratified: half the sets from the hard population
(top-2 true gap < 1e-2), half easy; within each stratum spread over tasks round-robin.

Writes: phase1/fidelity_manifest.jsonl (full)  and  phase1/fidelity_smoke.jsonl (10 children
across >=5 tasks, for the parse-rate smoke that gates the full run).
"""
import collections, json, math, random

ORI = json.load(open("phase1/task_orientation.json"))
G, OWN, TASK, CODE = {}, {}, {}, {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    TASK[d["id"]] = d["task"]["name"]
    CODE[d["id"]] = d.get("code") or ""
    try:
        v = float(d["label"].get("graded"))
        G[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        G[d["id"]] = None
    try:
        w = float(d["obs"].get("val_at_low"))
        OWN[d["id"]] = w if math.isfinite(w) else None
    except (TypeError, ValueError):
        OWN[d["id"]] = None

sets_ = collections.defaultdict(set)
for l in open("phase1/decision_clean_b0.jsonl"):
    p = json.loads(l)
    sets_[p["parent"]].update((p["better"], p["worse"]))
sets_ = {par: sorted(c for c in ch if G.get(c) is not None and CODE[c].strip())
         for par, ch in sets_.items()}
MISSING_TASKS = {'dog-breed-identification', 'aptos2019-blindness-detection', 'histopathologic-cancer-detection'}   # no local data; excluded from the rerun universe
sets_ = {par: ch for par, ch in sets_.items()
         if len(ch) >= 2 and TASK[ch[0]] not in MISSING_TASKS}


def top2gap(ch):
    t = TASK[ch[0]]
    vs = sorted((G[c] for c in ch), reverse=not ORI.get(t, False))
    return abs(vs[0] - vs[1])


hard = [p for p in sets_ if top2gap(sets_[p]) < 1e-2]
easy = [p for p in sets_ if top2gap(sets_[p]) >= 1e-2]
print(f"universe: {len(sets_)} sets ({len(hard)} hard, {len(easy)} easy)")

rng = random.Random(7)


def strat_sets(pool, n):
    byt = collections.defaultdict(list)
    for p in pool:
        byt[TASK[sets_[p][0]]].append(p)
    for t in byt:
        rng.shuffle(byt[t])
    out = []
    while len(out) < n and any(byt.values()):
        for t in sorted(byt):
            if byt[t] and len(out) < n:
                out.append(byt[t].pop())
    return out


pick = strat_sets(hard, 50) + strat_sets(easy, 50)
rows = []
for par in pick:
    for c in sets_[par]:
        rows.append({"card_id": c, "competition": TASK[c], "code": CODE[c],
                     "graded": G[c], "val_at_low": OWN.get(c), "parent": par,
                     "set_size": len(sets_[par]),
                     "stratum": "hard" if par in hard else "easy"})
with open("phase1/fidelity_manifest.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
byt = collections.Counter(r["competition"] for r in rows)
print(f"full manifest: {len(pick)} sets, {len(rows)} children, "
      f"{len(byt)} tasks: {dict(byt.most_common())}")

# smoke: 10 children, >=5 tasks, mixed strata, preferring short original runtimes is WRONG
# (it would bias the parse-rate estimate optimistic); take a plain task-spread sample.
byt2 = collections.defaultdict(list)
for r in rows:
    byt2[r["competition"]].append(r)
for t in byt2:
    rng.shuffle(byt2[t])
smoke, i = [], 0
while len(smoke) < 10 and any(byt2.values()):
    for t in sorted(byt2):
        if byt2[t] and len(smoke) < 10:
            smoke.append(byt2[t].pop())
with open("phase1/fidelity_smoke.jsonl", "w") as f:
    for r in smoke:
        f.write(json.dumps(r) + "\n")
print(f"smoke manifest: {len(smoke)} children over "
      f"{len(set(r['competition'] for r in smoke))} tasks")
