"""T1 harness — scaling curves: predictor performance vs dataset size N, for
  VALUE  (per-task intra Spearman, frozen feats + dual ridge)
  HACK   (reward-hack detector AUROC, step1_usability construction)
  BUGGY  (execution-failure AUROC from code alone, all-cards cache + journal ground truth)
Outputs one CSV row per (predictor,task,N,resample) + a summary table with SE.
Verification anchors printed at the end (must match known numbers at full N).
CPU-only given the two id-keyed feature caches exist (built by t1_extract.sbatch).
"""
import csv
import json
import sys

import numpy as np

sys.path.insert(0, "/research/d7/spc/yzyang4/aira-dojo")
from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _auroc, _dual_ridge
from phase1 import feat_cache

CARDS_LAB = "phase1/cards_t1_labeled.jsonl"
CARDS_ALL = "phase1/cards_t1_all.jsonl"
CACHE_LAB = "phase1/_cache_t1_lab.npz"
CACHE_ALL = "phase1/_cache_t1_pre.npz"
BUGGY = "phase1/t1_buggy_labels.jsonl"
OUT = "phase1/t1_curves.csv"
NS = [100, 200, 300, 450, 600, 800, 1000, 1500, 2000, 3000]
RES = 30

rows = []


def emit(pred, task, N, r, metric, val):
    rows.append({"predictor": pred, "task": task, "N": N, "resample": r, "metric": metric, "value": float(val)})


# ================= VALUE + HACK (labeled cards) =================
cards = labeled(load_cards(CARDS_LAB))
X, mask = feat_cache.load_aligned(cards, CACHE_LAB)
cards = [c for c, m in zip(cards, mask) if m]
y = np.array([c.y for c in cards], float)
tasks = np.array([c.task.name for c in cards])
vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else np.nan) for c in cards])
v = np.full(len(cards), np.nan)
for t in np.unique(tasks):
    m = tasks == t
    h = next(c for c in cards if c.task.name == t).task.higher_is_better
    v[m] = vraw[m] if h else -vraw[m]
print(f"[value/hack] labeled cards with feats: {len(cards)} | tasks: {dict((t, int((tasks==t).sum())) for t in np.unique(tasks))}")

for t in np.unique(tasks):
    idx_t = np.where(tasks == t)[0]
    if len(idx_t) < 40:
        continue
    ntest = max(12, int(len(idx_t) * 0.35))
    # VALUE: train on N sampled from pool, eval Spearman on fixed-size held-out
    for N in [n for n in NS if n <= len(idx_t) - ntest] + [len(idx_t) - ntest]:
        for r in range(RES):
            rng = np.random.default_rng(r)
            perm = rng.permutation(idx_t)
            test, pool = perm[:ntest], perm[ntest:]
            if N > len(pool):
                continue
            tr = rng.choice(pool, N, replace=False)
            emit("value", t, N, r, "spearman", _spear(_dual_ridge(X[tr], y[tr], X[test]), y[test]))
    # HACK: step1 construction (happy half by self-report; label = truly bad)
    idx_v = idx_t[~np.isnan(v[idx_t])]
    if len(idx_v) < 60:
        continue
    ntest_h = max(15, int(len(idx_v) * 0.35))
    for N in [n for n in NS if n <= len(idx_v) - ntest_h] + [len(idx_v) - ntest_h]:
        for r in range(RES):
            rng = np.random.default_rng(1000 + r)
            perm = rng.permutation(idx_v)
            test, pool = perm[:ntest_h], perm[ntest_h:]
            if N > len(pool):
                continue
            tr = rng.choice(pool, N, replace=False)
            pred = _dual_ridge(X[tr], y[tr], X[test])
            vt, yt = v[test], y[test]
            happy = vt >= np.median(vt)
            if happy.sum() < 8:
                continue
            lab = yt[happy] < np.median(yt)
            if lab.sum() < 2 or lab.sum() == len(lab):
                continue
            emit("hack", t, N, r, "auroc", _auroc(-_z(pred[happy]), lab))

# ================= BUGGY (all cards) =================
alls = load_cards(CARDS_ALL)
Xa, mask_a = feat_cache.load_aligned(alls, CACHE_ALL)
alls = [c for c, m in zip(alls, mask_a) if m]
blab = {json.loads(l)["id"]: json.loads(l)["is_buggy"] for l in open(BUGGY) if l.strip()}
keep = [i for i, c in enumerate(alls) if c.id in blab]
Xa = Xa[keep]
alls = [alls[i] for i in keep]
b = np.array([1.0 if blab[c.id] else 0.0 for c in alls])
tasks_a = np.array([c.task.name for c in alls])
print(f"[buggy] cards with feats+label: {len(alls)} | buggy rate: {b.mean():.2f}")
idx = np.arange(len(alls))
ntest_b = max(60, int(len(idx) * 0.25))
for N in [n for n in NS if n <= len(idx) - ntest_b] + [len(idx) - ntest_b]:
    for r in range(RES):
        rng = np.random.default_rng(2000 + r)
        perm = rng.permutation(idx)
        test, pool = perm[:ntest_b], perm[ntest_b:]
        if N > len(pool):
            continue
        tr = rng.choice(pool, N, replace=False)
        if b[tr].sum() < 3 or b[tr].sum() > len(tr) - 3:
            continue
        pred = _dual_ridge(Xa[tr], b[tr], Xa[test])
        emit("buggy", "ALL", N, r, "auroc", _auroc(pred, b[test] > 0.5))

# ================= write + summarize =================
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["predictor", "task", "N", "resample", "metric", "value"])
    w.writeheader()
    w.writerows(rows)
print(f"\n[t1_scaling] {len(rows)} rows -> {OUT}\n")
print(f"{'predictor':9s} {'task':28s} {'N':>5s}  mean±SE")
agg = {}
for r in rows:
    agg.setdefault((r["predictor"], r["task"], r["N"]), []).append(r["value"])
for (p, t, N), vals in sorted(agg.items()):
    va = np.array(vals)
    print(f"{p:9s} {t[:28]:28s} {N:>5d}  {va.mean():+.3f}±{va.std()/np.sqrt(len(va)):.3f}")
print("\nVERIFY anchors: value@full-N per task should match known intra numbers "
      "(spaceship ~+0.24, tps_may ~+0.4-0.5 at old N); hack@N=100 spaceship ~0.55-0.60; "
      "buggy AUROC expected >0.65 (else features not informative).")
print("=== t1_scaling done ===")
