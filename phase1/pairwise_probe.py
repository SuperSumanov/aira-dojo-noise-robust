"""Pairwise (Bradley-Terry / RankNet) vs scalar-ridge readout on the SAME frozen features.

Tests the senior's hypothesis: is a *ranking* objective (LLM-friendly, like an RLHF reward model that
learns pairwise preferences, never absolute scalars) better than scalar L2 regression for reading the
grade out of a frozen code-LLM? Both readouts live on the frozen ablated (code-only) layer-21 features
(cached) -- the LLM is never touched, honouring the no-fine-tune constraint. Offline, CPU, seconds.

Metrics on the same CV splits: per-task Spearman (intra), cross-task Spearman (LOTO), and the B1
detection AUROC (catch reward-hacked solutions among the self-report-happy). If pairwise clearly beats
ridge -- especially on detection -- the 'find a better loss' pivot has legs.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _auroc, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
PCA_K = 64
LAM_RIDGE = 5.0
LAM_PW = 1.0


def _pca_fit(Xtr, k):
    mu = Xtr.mean(0)
    _, _, Vt = np.linalg.svd(Xtr - mu, full_matrices=False)
    return mu, Vt[:k]


def _prep(Xtr, Xte, k):
    mu, comps = _pca_fit(Xtr, k)
    Xtr = (Xtr - mu) @ comps.T
    Xte = (Xte - mu) @ comps.T
    zmu = Xtr.mean(0); zsd = Xtr.std(0); zsd[zsd < 1e-8] = 1.0
    return (Xtr - zmu) / zsd, (Xte - zmu) / zsd


def ridge_w(X, y, lam):
    d = X.shape[1]
    return np.linalg.solve(X.T @ X + lam * np.eye(d), X.T @ y)


def pairwise_w(X, y, lam=LAM_PW, k_pairs=6000, iters=500, lr=0.5, seed=0):
    """Bradley-Terry: learn w s.t. sigmoid(w.(x_i - x_j)) predicts P(y_i > y_j)."""
    rng = np.random.default_rng(seed); n = len(y)
    a = rng.integers(0, n, k_pairs * 3); b = rng.integers(0, n, k_pairs * 3)
    m = y[a] != y[b]; a, b = a[m][:k_pairs], b[m][:k_pairs]
    D = X[a] - X[b]; t = (y[a] > y[b]).astype(float)
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(D @ w)))
        w -= lr * (D.T @ (p - t) / len(t) + lam * w)
    return w


def _fit_score(Xtr, ytr, Xte, method):
    if method == "ridge_full":
        return _dual_ridge(Xtr, ytr, Xte)
    Xr, Xer = _prep(Xtr, Xte, PCA_K)
    w = ridge_w(Xr, ytr, LAM_RIDGE) if method == "ridge_pca" else pairwise_w(Xr, ytr)
    return Xer @ w


def oof_intra(X, y, tasks, method, seed=0, folds=5):
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        order = np.random.default_rng(seed).permutation(idx)
        for f in np.array_split(order, folds):
            tr = np.setdiff1d(idx, f)
            pred[f] = _fit_score(X[tr], y[tr], X[f], method)
    return pred


def oof_loto(X, y, tasks, method):
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        te = np.where(tasks == t)[0]; tr = np.where(tasks != t)[0]
        pred[te] = _fit_score(X[tr], y[tr], X[te], method)
    return pred


def per_task_spear(pred, y, tasks):
    vals = [_spear(pred[tasks == t], y[tasks == t]) for t in np.unique(tasks)
            if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
    return float(np.mean(vals)) if vals else float("nan")


def detect_auroc(pred, y, v, tasks):
    """B1: among self-report-happy (v>=task median), catch secretly-bad (y<task median); detector = -pred."""
    lab, scr = [], []
    for t in np.unique(tasks):
        m = np.where(tasks == t)[0]
        if len(m) < 10 or np.isnan(pred[m]).any():
            continue
        happy = m[v[m] >= np.median(v[m])]
        if len(happy) < 6:
            continue
        lab.append(y[happy] < np.median(y[m]))
        scr.append(-_z(pred[happy]))
    if not lab:
        return float("nan")
    return _auroc(np.concatenate(scr), np.concatenate(lab))


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
    v = np.zeros(len(cards))
    for t in np.unique(tasks):
        mm = tasks == t
        h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[mm] = vraw[mm] if h else -vraw[mm]

    d = np.load(CACHE)
    XA = d["XA"]
    assert XA.shape[0] == len(cards), f"cache/card mismatch {XA.shape[0]} vs {len(cards)}"
    print(f"features {XA.shape} (ablated/code-only layer-21), PCA_K={PCA_K}", flush=True)

    methods = [("ridge_full (dual, 7169-dim)", "ridge_full"),
               (f"ridge   (PCA-{PCA_K}, L2 regression)", "ridge_pca"),
               (f"pairwise (PCA-{PCA_K}, Bradley-Terry)", "pairwise")]
    print(f"\n  {'readout':38s} {'intra':>7} {'LOTO':>7} {'detect-AUROC':>13}", flush=True)
    res = {}
    for name, key in methods:
        pi = oof_intra(XA, y, tasks, key)
        pl = oof_loto(XA, y, tasks, key)
        det = detect_auroc(pi, y, v, tasks)
        res[key] = (per_task_spear(pi, y, tasks), per_task_spear(pl, y, tasks), det)
        print(f"  {name:38s} {res[key][0]:>7.3f} {res[key][1]:>7.3f} {res[key][2]:>13.3f}", flush=True)

    rp, pp = res["ridge_pca"], res["pairwise"]
    print("\n=== pairwise - ridge (same PCA features, only the loss differs) ===", flush=True)
    print(f"  intra  {pp[0]-rp[0]:+.3f}   LOTO {pp[1]-rp[1]:+.3f}   detect {pp[2]-rp[2]:+.3f}", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
