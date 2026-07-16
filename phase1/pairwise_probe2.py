"""Pairwise (Bradley-Terry) vs scalar-ridge -- THOROUGH version, so nobody can say it was under-tried.
Pairwise logistic is solved to the exact MLE by Newton/IRLS (not truncated gradient descent), swept over
PCA dims {64,128,256} and L2 strength, with up to 12k within-fold pairs. Ridge likewise swept. Same frozen
ablated layer-21 features, same CV splits. Reports intra / LOTO Spearman + B1 detection AUROC.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _auroc, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
DIMS = [64, 128, 256]
LAM_R = [2.0, 10.0, 40.0]
LAM_P = [0.5, 2.0, 8.0]
MAX_PAIRS = 12000
NEWTON_ITERS = 25


def _pca(Xtr, k):
    mu = Xtr.mean(0)
    _, _, Vt = np.linalg.svd(Xtr - mu, full_matrices=False)
    return mu, Vt[:k]


def _prep(Xtr, Xte, k):
    mu, comps = _pca(Xtr, k)
    Xtr = (Xtr - mu) @ comps.T; Xte = (Xte - mu) @ comps.T
    zmu = Xtr.mean(0); zsd = Xtr.std(0); zsd[zsd < 1e-8] = 1.0
    return (Xtr - zmu) / zsd, (Xte - zmu) / zsd


def ridge_w(X, y, lam):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def pairwise_newton(X, y, lam, seed=0):
    rng = np.random.default_rng(seed); n = len(y); d = X.shape[1]
    a, b = np.triu_indices(n, 1)
    m = y[a] != y[b]; a, b = a[m], b[m]
    if len(a) > MAX_PAIRS:
        sel = rng.choice(len(a), MAX_PAIRS, replace=False); a, b = a[sel], b[sel]
    D = X[a] - X[b]; t = (y[a] > y[b]).astype(float); w = np.zeros(d)
    for _ in range(NEWTON_ITERS):
        p = 1.0 / (1.0 + np.exp(-(D @ w)))
        g = D.T @ (p - t) / len(t) + lam * w
        W = p * (1 - p)
        H = (D * W[:, None]).T @ D / len(t) + lam * np.eye(d)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            step = g
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return w


def oof(X, y, tasks, fit_fn, mode, seed=0, folds=5):
    pred = np.full(len(y), np.nan)
    if mode == "intra":
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < folds + 2:
                continue
            order = np.random.default_rng(seed).permutation(idx)
            for f in np.array_split(order, folds):
                tr = np.setdiff1d(idx, f)
                pred[f] = fit_fn(X[tr], y[tr], X[f])
    else:
        for t in np.unique(tasks):
            te = np.where(tasks == t)[0]; tr = np.where(tasks != t)[0]
            pred[te] = fit_fn(X[tr], y[tr], X[te])
    return pred


def spear(pred, y, tasks):
    vals = [_spear(pred[tasks == t], y[tasks == t]) for t in np.unique(tasks)
            if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
    return float(np.mean(vals)) if vals else float("nan")


def detect(pred, y, v, tasks):
    lab, scr = [], []
    for t in np.unique(tasks):
        m = np.where(tasks == t)[0]
        if len(m) < 10 or np.isnan(pred[m]).any():
            continue
        happy = m[v[m] >= np.median(v[m])]
        if len(happy) < 6:
            continue
        lab.append(y[happy] < np.median(y[m])); scr.append(-_z(pred[happy]))
    return _auroc(np.concatenate(scr), np.concatenate(lab)) if lab else float("nan")


def evaluate(X, y, v, tasks, method, dim, lam):
    def fit(Xtr, ytr, Xte):
        Xr, Xer = _prep(Xtr, Xte, dim)
        w = ridge_w(Xr, ytr, lam) if method == "ridge" else pairwise_newton(Xr, ytr, lam)
        return Xer @ w
    pi = oof(X, y, tasks, fit, "intra"); pl = oof(X, y, tasks, fit, "loto")
    return spear(pi, y, tasks), spear(pl, y, tasks), detect(pi, y, v, tasks)


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
    v = np.zeros(len(cards))
    for t in np.unique(tasks):
        mm = tasks == t; h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[mm] = vraw[mm] if h else -vraw[mm]
    XA = np.load(CACHE)["XA"]
    print(f"features {XA.shape}; MAX_PAIRS={MAX_PAIRS}, Newton<= {NEWTON_ITERS} iters\n", flush=True)

    # reference: full-dim dual ridge
    pif = oof(XA, y, tasks, lambda a, b, c: _dual_ridge(a, b, c), "intra")
    plf = oof(XA, y, tasks, lambda a, b, c: _dual_ridge(a, b, c), "loto")
    print(f"  {'ridge_full (dual 7169-dim)':34s} intra {spear(pif,y,tasks):+.3f}  LOTO {spear(plf,y,tasks):+.3f}  detect {detect(pif,y,v,tasks):.3f}\n", flush=True)

    best = {}
    for method, lams in [("ridge", LAM_R), ("pairwise", LAM_P)]:
        for dim in DIMS:
            rows = [(lam,) + evaluate(XA, y, v, tasks, method, dim, lam) for lam in lams]
            # select lambda by best intra (honest model selection); report all metrics at it
            lam, si, sl, det = max(rows, key=lambda r: r[1])
            print(f"  {method:8s} PCA-{dim:<4d} (lam*={lam:<4g})  intra {si:+.3f}  LOTO {sl:+.3f}  detect {det:.3f}", flush=True)
            best.setdefault(method, []).append((si, sl, det, dim, lam))
        print("", flush=True)

    br = max(best["ridge"], key=lambda r: r[0]); bp = max(best["pairwise"], key=lambda r: r[0])
    print("=== BEST-of-sweep, pairwise vs ridge (each given its best dim/lam by intra) ===", flush=True)
    print(f"  ridge    best: intra {br[0]:+.3f} LOTO {br[1]:+.3f} detect {br[2]:.3f}  (PCA-{br[3]}, lam {br[4]})", flush=True)
    print(f"  pairwise best: intra {bp[0]:+.3f} LOTO {bp[1]:+.3f} detect {bp[2]:.3f}  (PCA-{bp[3]}, lam {bp[4]})", flush=True)
    print(f"  Δ(pairwise-ridge): intra {bp[0]-br[0]:+.3f}  LOTO {bp[1]-br[1]:+.3f}  detect {bp[2]-br[2]:+.3f}", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
