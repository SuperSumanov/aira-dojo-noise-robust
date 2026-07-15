"""A1 + B1 on the frozen mid-layer (21) representation, reusing H1's extractor. No finetuning, offline.

A1 — how LOW-DIM is the grade signal? (cf 'Confidence Manifold' 2602.08159: correctness lives in 3-8 dims)
   Grade Spearman (per-task 5-fold CV) as a function of #dims: a single contrastive (good-minus-bad)
   direction, then PCA-k for k in {1,2,3,5,8,16,32,full}. Does a low-dim subspace capture most of it?

B1 — reward-hacking / validation-overfit DETECTOR (rescue made per-candidate + deployable).
   Probe yhat = code-only estimate of the true grade from SELF-REPORT-ABLATED features (so it cannot
   just echo the self-report). "Reward-hacked" candidates = self-report ABOVE its task median but true
   grade BELOW (inflated / optimistic CV). Metric: what fraction of these the probe correctly FLAGS
   (yhat below the task median) — the self-report itself flags 0% of them (it says they are good).
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.h1_ablation import extract_multilayer, mask_selfreport

LAYER = 21
LAM = 2.0


def _z(a):
    a = np.asarray(a, float); s = a.std()
    return (a - a.mean()) / (s if s > 1e-8 else 1.0)


def _spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return 0.0 if ra.std() < 1e-9 or rb.std() < 1e-9 else float(np.corrcoef(ra, rb)[0, 1])


def _dual_ridge(Xtr, ytr, Xte):
    mu = Xtr.mean(0); sd = Xtr.std(0); sd[sd < 1e-8] = 1.0
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    a = np.linalg.solve(Xtr @ Xtr.T + LAM * np.eye(len(ytr)), ytr)
    return (Xte @ Xtr.T) @ a


def _pca(Xtr, k):
    mu = Xtr.mean(0)
    _, _, Vt = np.linalg.svd(Xtr - mu, full_matrices=False)
    return mu, Vt[:k]


def cv_oof(X, y, tasks, ncomp=None, contrastive=False, seed=0, folds=5):
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        order = np.random.default_rng(seed).permutation(idx)
        for f in np.array_split(order, folds):
            tr = np.setdiff1d(idx, f)
            if contrastive:
                med = np.median(y[tr]); hi = tr[y[tr] >= med]; lo = tr[y[tr] < med]
                d = X[hi].mean(0) - X[lo].mean(0); d = d / (np.linalg.norm(d) + 1e-8)
                pred[f] = X[f] @ d
            elif ncomp is not None:
                mu, comps = _pca(X[tr], ncomp)
                pred[f] = _dual_ridge((X[tr] - mu) @ comps.T, y[tr], (X[f] - mu) @ comps.T)
            else:
                pred[f] = _dual_ridge(X[tr], y[tr], X[f])
    return pred


def per_task_spear(pred, y, tasks):
    vals = [_spear(pred[tasks == t], y[tasks == t]) for t in np.unique(tasks)
            if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
    return float(np.mean(vals)) if vals else float("nan")


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
    v = np.zeros(len(cards))
    for t in np.unique(tasks):
        m = tasks == t
        h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[m] = vraw[m] if h else -vraw[m]

    print("extracting layer-21 features: normal + self-report-ablated ...", flush=True)
    fN, eN = extract_multilayer(cards, [LAYER], 4000); XN = np.hstack([fN[LAYER], eN])
    fA, eA = extract_multilayer([mask_selfreport(c) for c in cards], [LAYER], 4000); XA = np.hstack([fA[LAYER], eA])

    print("\n=== A1: grade Spearman vs #dims (target 3-8 per Confidence Manifold 2602.08159) ===", flush=True)
    print(f"  contrastive-1D (good-minus-bad direction): {per_task_spear(cv_oof(XN, y, tasks, contrastive=True), y, tasks):+.3f}", flush=True)
    for k in [1, 2, 3, 5, 8, 16, 32, None]:
        print(f"  PCA-{str(k):>4}: {per_task_spear(cv_oof(XN, y, tasks, ncomp=k), y, tasks):+.3f}", flush=True)

    print("\n=== B1: reward-hack / validation-overfit detector (self-report-ablated, code-only probe) ===", flush=True)
    yhat = cv_oof(XA, y, tasks, ncomp=None)
    print(f"  (probe skill: Spearman(yhat, true) per-task {per_task_spear(yhat, y, tasks):+.3f})", flush=True)
    flags = []
    for t in np.unique(tasks):
        m = np.where(tasks == t)[0]
        if len(m) < 10:
            continue
        ymed = np.median(y[m]); vmed = np.median(v[m]); yhmed = np.median(yhat[m])
        hack = m[(v[m] > vmed) & (y[m] < ymed)]           # self-report high but truly low = inflated
        if len(hack) == 0:
            continue
        flagged = np.mean(yhat[hack] < yhmed)             # probe puts them below median = correctly flags
        flags.append((t, len(hack), flagged))
        print(f"  {t:28s} n_hack={len(hack):>3}  probe flags {flagged:.2f}  (self-report flags 0.00, random 0.50)", flush=True)
    if flags:
        print(f"  MEAN probe flag-rate on inflated solutions: {np.mean([f[2] for f in flags]):.2f}", flush=True)


if __name__ == "__main__":
    main()
