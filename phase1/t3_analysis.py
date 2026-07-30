"""T3 controlled comparison: vanilla UCT vs value-RM-guided selection.
Pairs runs by (task, seed) across control/guided tags; best externally-graded score per run.
Usage: python phase1/t3_analysis.py [--pairs t3cA:t3gA t3cB:t3gB]"""
import argparse, collections, glob, json

ap = argparse.ArgumentParser()
ap.add_argument("--pairs", nargs="+", default=["t3cA:t3gA", "t3cB:t3gB"])
ap.add_argument("--out", default="phase1/t3_results.csv")
a = ap.parse_args()
ORI = json.load(open("phase1/task_orientation.json"))

def harvest(tag):
    out = {}
    for j in glob.glob(f"/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_mcts_data_{tag}/*/checkpoint/journal.jsonl"):
        seed = j.split("_seed_")[1].split("_")[0]
        task = None; scores = []; nodes = bug = 0
        for l in open(j):
            try: d = json.loads(l)
            except Exception: continue
            d = d.get("data", d)
            if not isinstance(d, dict): continue
            mi = d.get("metric_info") or {}
            if mi.get("competition_id"): task = mi["competition_id"]
            if "code" in d: nodes += 1
            if d.get("is_buggy"): bug += 1
            if mi.get("score") is not None: scores.append(mi["score"])
        if task and scores:
            lower = ORI.get(task, False)
            out[(task, seed)] = dict(best=(min if lower else max)(scores),
                                     nodes=nodes, graded=len(scores), buggy=bug)
    return out

import csv
wins = collections.Counter(); rows = []
for pr in a.pairs:
    c, g = pr.split(":")
    hc, hg = harvest(c), harvest(g)
    for key in sorted(set(hc) & set(hg)):
        task, seed = key
        lower = ORI.get(task, False)
        cb, gb = hc[key]["best"], hg[key]["best"]
        w = "guided" if ((gb < cb) if lower else (gb > cb)) else ("control" if gb != cb else "tie")
        wins[w] += 1
        rows.append(dict(pair=pr, task=task, seed=seed, control_best=cb, guided_best=gb, winner=w))
        print(f"{pr} {task[:28]:28s} s{seed} ctrl={cb:.4f} guided={gb:.4f} -> {w}")
print("wins:", dict(wins))
with open(a.out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader()
    for r in rows: w.writerow(r)
print(f"wrote {a.out}")
