"""Re-check LOTO with a cross-task-COMPARABLE target. Raw oriented score isn't comparable across 26
heterogeneous tasks (accuracy vs AUC vs RMSE), which dooms a pooled cross-task regression by construction.
FOREAGENT ships beat_ratio (leaderboard percentile in [0,1]) = the right normalized target. Uses the
CACHED features -> CPU, seconds. intra is rank-invariant so it won't change; LOTO is the question.
"""
import os
import json

import numpy as np

from phase1.h1_ablation import intra, loto

ROOT = "/research/d7/spc/yzyang4/foreagent_slice"
d = np.load(os.path.join(ROOT, "feats_l21.npz"), allow_pickle=True)
X, y_raw, tasks, C = d["X"], d["y"], d["tasks"].astype(str), d["C"]
rows = json.load(open(os.path.join(ROOT, "slice.json")))
assert len(rows) == len(X), (len(rows), len(X))
beat = np.array([(r["beat_ratio"] if r["beat_ratio"] is not None else np.nan) for r in rows], float)

# alignment sanity: raw intra must reproduce the GPU-job's 0.408
print(f"alignment check -- raw intra should be ~0.408: {intra(X, y_raw, tasks):+.3f}", flush=True)
print(f"beat_ratio available for {int((~np.isnan(beat)).sum())}/{len(beat)} rows", flush=True)

m = ~np.isnan(beat)
Xb, bt, tb, Cb = X[m], beat[m], tasks[m], C[m]

print("\n=== target = RAW oriented score (not cross-task comparable) ===", flush=True)
print(f"  intra={intra(X, y_raw, tasks):+.3f}   loto={loto(X, y_raw, tasks):+.3f}", flush=True)

print("\n=== target = beat_ratio (leaderboard percentile, cross-task comparable) ===", flush=True)
print(f"  intra={intra(Xb, bt, tb):+.3f}   loto={loto(Xb, bt, tb):+.3f}", flush=True)
print(f"  + length-residualized:   intra={intra(Xb, bt, tb, Cb):+.3f}   loto={loto(Xb, bt, tb, Cb):+.3f}", flush=True)
print(f"  length-only floor:       intra={intra(Cb, bt, tb):+.3f}   loto={loto(Cb, bt, tb):+.3f}", flush=True)

print("\n=== VERDICT ===", flush=True)
lb = loto(Xb, bt, tb)
lbr = loto(Xb, bt, tb, Cb)
if lb > 0.08 and lbr > 0.04:
    print(f"  GREEN: with a comparable target, LOTO transfers ({lb:+.3f}, {lbr:+.3f} after length) -> the earlier"
          " negative LOTO was a raw-score-scale artifact; H1 replicates at scale INCLUDING cross-task.", flush=True)
elif lb <= 0.02:
    print(f"  cross-task genuinely weak even normalized (loto={lb:+.3f}): grade-encoding is domain-specific; within-task"
          " H1 is strong (0.41) but does NOT transfer across heterogeneous domains -- a real (interesting) finding.", flush=True)
else:
    print(f"  partial cross-task (loto={lb:+.3f}): weak-positive transfer once normalized.", flush=True)
print("\n=== done rc=0 ===", flush=True)
