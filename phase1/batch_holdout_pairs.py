"""The batch-qua-batch experiment: one training, two matched test sets.

Question: does holding out a whole COLLECTION BATCH hurt more than holding out whole TREES from
the training batches? If yes, the "collapse" is pseudo-replication at the run level -- an RM
that recognises lineages -- and not about generators or versions at all.

Design keeps everything else fixed by using only the senior's date batches 0727/0728/0729 for
training (same deep-tree protocol, same conda env, same account, temp 0.6/0.5 era, ds-flash v1)
and 0730 as the held-out batch (still v1 per the senior's annotation that v2 starts 0731).
So the batch axis is literally "which day it was collected".

  train  pairs among 80% of trees in 0727-0729
  testA  pairs among the other 20% of trees (TREEHOLD::task)  -- same batches, unseen trees
  testB  pairs within 0730                  (BATCHHOLD::task) -- unseen batch entirely

Both endpoints of a pair must be in the same group; nothing straddles. testA vs testB is the
isolated batch effect, measured inside one run of one model on one eval pass.

Usage: python phase1/batch_holdout_pairs.py OUT --train-files f1 f2 f3 --hold-file f4
"""
import argparse, collections, itertools, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--train-files", nargs="+", required=True)
ap.add_argument("--hold-files", nargs="+", required=True,
                help="whole batches held out; each contributes BATCHHOLD pairs for its tasks")
ap.add_argument("--tasks", default="spooky-author-identification,petfinder-pawpularity-score")
ap.add_argument("--cap-train", type=int, default=40000)
ap.add_argument("--cap-test", type=int, default=2500, help="per (group, task)")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
TASKS = set(a.tasks.split(","))
ORI = json.load(open("phase1/task_orientation.json"))
rng = random.Random(a.seed)


def load(files):
    cs = {}
    for f in files:
        for l in open(f):
            d = json.loads(l)
            if d["task"]["name"] in TASKS:
                cs[d["id"]] = d
    return cs


tr_cards = load(a.train_files)
ho_cards = load(a.hold_files)
overlap = set(tr_cards) & set(ho_cards)
assert not overlap, f"{len(overlap)} cards appear in both train and holdout files"

root = {}
def tree_root(cs, cid, g=0):
    if cid in root:
        return root[cid]
    p = cs.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cs or g > 200) else tree_root(cs, p, g + 1)
    root[cid] = r
    return r


def pairs_of(cs, ids, task, cap, split, tag):
    lower = ORI[task]
    out = []
    prs = list(itertools.combinations([i for i in ids if cs[i]["task"]["name"] == task], 2))
    rng.shuffle(prs)
    for x, y in prs:
        vx, vy = cs[x]["label"]["graded"], cs[y]["label"]["graded"]
        if vx == vy:
            continue
        hi, lo = (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)
        out.append({"task": tag, "better": hi, "worse": lo,
                    "gap_raw": round(abs(vx - vy), 6),
                    "intask_split": split, "loto_fold": task,
                    "clears_tau": None, "src": "batch_holdout"})
        if len(out) >= cap:
            break
    return out


recs = []
for t in sorted(TASKS):
    tids = [i for i in tr_cards if tr_cards[i]["task"]["name"] == t]
    roots = sorted({tree_root(tr_cards, i) for i in tids})
    rng.shuffle(roots)
    hold_trees = set(roots[int(0.8 * len(roots)):])
    tr_ids = [i for i in tids if tree_root(tr_cards, i) not in hold_trees]
    th_ids = [i for i in tids if tree_root(tr_cards, i) in hold_trees]
    recs += pairs_of(tr_cards, tr_ids, t, a.cap_train, "train", t)
    recs += pairs_of(tr_cards, th_ids, t, a.cap_test, "test", "TREEHOLD::" + t)
    recs += pairs_of(ho_cards, list(ho_cards), t, a.cap_test, "test", "BATCHHOLD::" + t)
    print(f"  {t[:40]:40s} train_cards={len(tr_ids):4d} treehold_cards={len(th_ids):4d} "
          f"batchhold_cards={sum(1 for i in ho_cards if ho_cards[i]['task']['name'] == t):4d}")

with open(a.out, "w") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")
c = collections.Counter((r["intask_split"], r["task"].split("::")[0]) for r in recs)
for k in sorted(c):
    print(f"  {k[0]:5s} {k[1][:14]:14s}: {c[k]}")
print(f"[batch_holdout] {len(recs)} records -> {a.out}")
