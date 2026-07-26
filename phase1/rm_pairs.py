"""RM pilot data builder v0: same-task preference pairs from graded cards.
- direction from y (per-task min-max normalized, higher=better)
- clears_tau flag: raw |gap| > 2*p90_tau (tau-measured tasks; else None)
- wild-node exclusion list (extreme same-env variance)
- deterministic sampling cap per task; in-task split (80/20 by card) + LOTO fold = task name
Usage: python phase1/rm_pairs.py out.jsonl cards1.jsonl [cards2.jsonl ...] [--cap 20000] [--seed 7]
"""
import csv, json, sys, random, collections, itertools, argparse

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("cards", nargs="+")
ap.add_argument("--cap", type=int, default=20000); ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
WILD = {"nomad2018-predict-transparent-conductors__8c54deef"}  # prefix-matched

taus = collections.defaultdict(list)
for r in csv.DictReader(open("phase1/regrade_tau_nodes.csv")):
    if r["tau"]: taus[r["competition"]].append(float(r["tau"]))
floor = {t: 2 * max(sorted(v)[int(0.9*(len(v)-1))], 1e-9) for t, v in taus.items()}

cards = collections.defaultdict(list)
for i, path in enumerate(a.cards):
    src = "senior" if "senior" in path else "ours"
    for l in open(path):
        d = json.loads(l)
        t = (d.get("task") or {}).get("name"); lab = d.get("label") or {}
        yv = lab.get("y_norm")
        if not t or lab.get("graded") is None or yv is None: continue
        cid = d.get("id") or ""
        if any(cid.startswith(w) for w in WILD): continue
        cards[t].append({"id": cid, "y": yv, "graded": lab["graded"], "src": src})

rng = random.Random(a.seed)
n_out = 0
with open(a.out, "w") as f:
    for t, cs in sorted(cards.items()):
        # in-task split by card (80/20)
        ids = [c["id"] for c in cs]; rng.shuffle(ids)
        holdout = set(ids[int(0.8*len(ids)):])
        pairs = [(x, y_) for x, y_ in itertools.combinations(cs, 2) if x["y"] != y_["y"]]
        rng.shuffle(pairs)
        kept = pairs[:a.cap]
        for x, y_ in kept:
            better, worse = (x, y_) if x["y"] > y_["y"] else (y_, x)
            gap = abs(x["graded"] - y_["graded"])
            ct = (gap > floor[t]) if t in floor else None
            rec = {"task": t, "better": better["id"], "worse": worse["id"],
                   "gap_raw": round(gap, 6), "clears_tau": ct,
                   "src": f'{better["src"]}|{worse["src"]}',
                   "intask_split": "test" if (better["id"] in holdout or worse["id"] in holdout) else "train",
                   "loto_fold": t}
            f.write(json.dumps(rec) + "\n"); n_out += 1
        print(f"{t[:40]:40s} cards={len(cs):4d} pairs_kept={len(kept):6d} tau={'y' if t in floor else '-'}")
print(f"[rm_pairs] total pairs: {n_out} -> {a.out}")
