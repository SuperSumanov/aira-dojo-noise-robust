"""Rank with frozen embeddings, and answer: what did fine-tuning actually buy?

Fits a linear ranker on differences of frozen mean-pooled embeddings, using the same
antisymmetric design as the rest of the suite (each pair contributes +d and -d) so the
learned function cannot exploit position. Evaluated on the same run-clean held-out side
with run-clustered CIs, so the number drops straight into the suite table.

Reads the embedding dump from embed_extract.py; no GPU.

Usage: python phase1/embed_rank.py EMB.json [--dump phase1/embed_scores.json]
"""
import argparse, collections, json, math, random, time

import numpy as np
from sklearn.linear_model import LogisticRegression

ap = argparse.ArgumentParser()
ap.add_argument("emb")
ap.add_argument("--pairs", default="phase1/value_pairs_runsplit.jsonl")
ap.add_argument("--train-cap", type=int, default=24000)
ap.add_argument("--test-cap", type=int, default=6000)
ap.add_argument("--dump", default="")
a = ap.parse_args()

RUN = json.load(open("phase1/card_run_map.json"))
E = {k: np.array(v, dtype=np.float32) for k, v in json.load(open(a.emb)).items()}
print(f"embeddings: {len(E)} nodes, dim {len(next(iter(E.values())))}")

train, test = [], []
for l in open(a.pairs):
    p = json.loads(l)
    if p["better"] not in E or p["worse"] not in E:
        continue
    (train if p["intask_split"] == "train" else test).append(p)
rng = random.Random(7)
rng.shuffle(train)
rng.shuffle(test)
train, test = train[:a.train_cap], test[:a.test_cap]
print(f"train {len(train)}, test {len(test)} over "
      f"{len({RUN[p['better']] for p in test})} held-out runs")

t0 = time.time()
D = np.vstack([E[p["better"]] - E[p["worse"]] for p in train])
X = np.vstack([D, -D])
y = np.array([1] * len(train) + [0] * len(train))
# embeddings are already on a common scale; C is small because the dim is large relative
# to the pair count and an unregularised fit memorises the training runs.
clf = LogisticRegression(max_iter=3000, C=0.05).fit(X, y)
init_s = time.time() - t0
print(f"fit in {init_s:.0f}s")

per_run = collections.defaultdict(list)
t0 = time.time()
for p in test:
    d = (E[p["better"]] - E[p["worse"]]).reshape(1, -1)
    per_run[RUN[p["better"]]].append(float(clf.decision_function(d)[0] > 0))
q_ms = (time.time() - t0) / max(len(test), 1) * 1000

vals = [v for vs in per_run.values() for v in vs]
acc = sum(vals) / len(vals)
runs = list(per_run)
r = random.Random(7)
draws = []
for _ in range(3000):
    s = [v for x in (r.choice(runs) for _ in runs) for v in per_run[x]]
    draws.append(sum(s) / len(s))
draws.sort()
print(f"\nfrozen-embedding linear ranker: acc={acc:.4f} "
      f"95% CI [{draws[75]:.4f}, {draws[2925]:.4f}] over {len(runs)} runs")
print(f"init {init_s:.0f}s, query {q_ms:.2f}ms")
print("\ncompare: fine-tuned 1.5B = 0.6493, char n-gram tfidf = 0.6657, "
      "self-report = 0.7780 (query 561s)")
print("if frozen ~ fine-tuned, the fine-tuning bought nothing and the ceiling is the")
print("representation rather than the head.")

if a.dump:
    w = clf.coef_[0]
    json.dump({c: float(np.dot(w, v)) for c, v in E.items()}, open(a.dump, "w"))
    print(f"dumped {len(E)} node scores -> {a.dump}")
