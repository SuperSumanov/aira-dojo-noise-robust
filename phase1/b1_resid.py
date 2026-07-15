"""B1 make-or-break: does the FROZEN REPRESENTATION add reward-hacking-detection signal BEYOND code-length?

code-length was a surprisingly strong baseline in b1_detector (AUROC 0.55 pooled, 0.64 on nomad). So the
honest question is: is the probe just reading 'longer code = more overfit', or does the representation carry
grade signal orthogonal to length? We answer it the same way H1 answered 'are you just reading code length':
residualize the code-only features against log-code-length WITHIN each CV fold (leak-free), refit the probe,
and re-run the detector. Then put a bootstrap 95% CI on every AUROC and on the paired gaps.

  probe LEN-RESID beats random (CI>0.5)      -> representation adds signal beyond length: B1 survives.
  probe LEN-RESID collapses to ~code-length  -> B1 was mostly a length heuristic: demote to footnote.

Feature extraction (one GPU forward pass) is cached to _cache_b1_feats.npz so re-analysis is CPU-only.
"""
import os
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.h1_ablation import extract_multilayer, mask_selfreport
from phase1.b1_detector import _z, _spear, _auroc, _prec_at_k, _dual_ridge

LAYER = 21
MIN_N = 10
NBOOT = 2000
CACHE = "phase1/_cache_b1_feats.npz"


def cv_oof_resid(X, y, tasks, loglen, residualize, seed=0, folds=5):
    """Per-task 5-fold OOF probe. If residualize: project code-length out of the features on TRAIN, apply
    the same projection to the held-out fold, then fit the dual-ridge probe (leak-free length control)."""
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        order = np.random.default_rng(seed).permutation(idx)
        for f in np.array_split(order, folds):
            tr = np.setdiff1d(idx, f)
            Xtr, Xte = X[tr].astype(float), X[f].astype(float)
            if residualize:
                ctr = np.column_stack([np.ones(len(tr)), loglen[tr]])
                cte = np.column_stack([np.ones(len(f)), loglen[f]])
                beta = np.linalg.lstsq(ctr, Xtr, rcond=None)[0]
                Xtr = Xtr - ctr @ beta
                Xte = Xte - cte @ beta
            pred[f] = _dual_ridge(Xtr, y[tr], Xte)
    return pred


def _auroc_ci(score, label, seed=0, B=NBOOT):
    rng = np.random.default_rng(seed)
    n = len(label); idx = np.arange(n); bs = []
    for _ in range(B):
        s = rng.choice(idx, n, replace=True)
        a = _auroc(score[s], label[s])
        if not np.isnan(a):
            bs.append(a)
    bs = np.array(bs)
    return _auroc(score, label), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _gap_ci(s1, s2, label, seed=0, B=NBOOT):
    """Paired bootstrap of AUROC(s1)-AUROC(s2): same resampled indices for both detectors."""
    rng = np.random.default_rng(seed)
    n = len(label); idx = np.arange(n); d = []
    for _ in range(B):
        s = rng.choice(idx, n, replace=True)
        a1 = _auroc(s1[s], label[s]); a2 = _auroc(s2[s], label[s])
        if not (np.isnan(a1) or np.isnan(a2)):
            d.append(a1 - a2)
    d = np.array(d)
    return _auroc(s1, label) - _auroc(s2, label), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def _block(tag, mask, y, v, yhat_n, yhat_r, loglen, tasks):
    m = np.where(mask)[0]
    if len(m) == 0:
        return
    # per-task z of primitives restricted to this block's tasks
    zv = np.zeros(len(y)); zyn = np.zeros(len(y)); zyr = np.zeros(len(y)); zL = np.zeros(len(y))
    med_y = np.zeros(len(y)); med_v = np.zeros(len(y))
    for t in np.unique(tasks):
        mm = tasks == t
        zv[mm] = _z(v[mm]); zyn[mm] = _z(yhat_n[mm]); zyr[mm] = _z(yhat_r[mm]); zL[mm] = _z(loglen[mm])
        med_y[mm] = np.median(y[mm]); med_v[mm] = np.median(v[mm])
    happy = (v >= med_v) & mask
    H = np.where(happy)[0]
    label = (y[H] < med_y[H])
    k = int(label.sum())
    if k < 5:
        print(f"\n=== {tag}: only {k} positives, skip ===", flush=True)
        return
    base = float(label.mean())
    lsign = 1.0 if _spear(zL[H], label.astype(float)) >= 0 else -1.0
    dets = [
        ("probe normal (-yhat)", -zyn[H]),
        ("probe LEN-RESID (-yhat)", -zyr[H]),
        ("disagreement resid z(v)-z(yr)", (zv - zyr)[H]),
        (f"code-length ({'+' if lsign > 0 else '-'}len)", lsign * zL[H]),
        ("self-report (-v)", -zv[H]),
    ]
    print(f"\n=== {tag} ===  happy N={len(H)}  positives={k}  base={base:.2f}", flush=True)
    print(f"  {'detector':30s} {'AUROC':>6}  95% CI", flush=True)
    for name, sc in dets:
        a, lo, hi = _auroc_ci(sc, label)
        print(f"  {name:30s} {a:>6.3f}  [{lo:.3f}, {hi:.3f}]", flush=True)
    print(f"  {'random':30s} {0.500:>6.3f}", flush=True)
    print(f"  probe skill Spearman(yhat_resid, y)|happy = {_spear(zyr[H], y[H]):+.3f}", flush=True)

    cl = lsign * zL[H]
    g1, l1, h1 = _gap_ci(-zyr[H], cl, label)            # resid-probe vs code-length
    a_r, lo_r, hi_r = _auroc_ci(-zyr[H], label)
    g3, l3, h3 = _gap_ci(-zyn[H], -zyr[H], label)       # how much length contributed (normal - resid)
    print(f"  GAP resid-probe - code-length : {g1:+.3f} [{l1:+.3f}, {h1:+.3f}]  -> "
          f"{'BEATS code-length' if l1 > 0 else 'ties code-length'}", flush=True)
    print(f"  resid-probe AUROC vs random   : {a_r:.3f} [{lo_r:.3f}, {hi_r:.3f}]  -> "
          f"{'SURVIVES (CI>0.5)' if lo_r > 0.5 else 'dies (CI touches 0.5)'}", flush=True)
    print(f"  GAP normal-probe - resid-probe: {g3:+.3f} [{l3:+.3f}, {h3:+.3f}]  (length's contribution)", flush=True)
    # complementary? equal-weight fuse of the two orthogonal weak detectors
    comb = _z(-zyr[H]) + _z(cl)
    a_c, lo_c, hi_c = _auroc_ci(comb, label)
    ap = _auroc(-zyr[H], label); acl = _auroc(cl, label)
    best_sc = (-zyr[H]) if ap >= acl else cl
    gcb, lcb, hcb = _gap_ci(comb, best_sc, label)
    print(f"  FUSE resid-probe + code-length: {a_c:.3f} [{lo_c:.3f}, {hi_c:.3f}]  vs best-single {max(ap, acl):.3f}"
          f"  gap {gcb:+.3f} [{lcb:+.3f}, {hcb:+.3f}]  -> {'complementary' if lcb > 0 else 'no clear add'}", flush=True)


def main():
    import torch
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
    v = np.zeros(len(cards))
    for t in np.unique(tasks):
        m = tasks == t
        h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[m] = vraw[m] if h else -vraw[m]
    loglen = np.array([np.log(max(len(c.code or ""), 1)) for c in cards], float)

    if os.path.exists(CACHE):
        d = np.load(CACHE)
        if d["XA"].shape[0] == len(cards):
            XA = d["XA"]; print(f"loaded cached features {XA.shape}", flush=True)
        else:
            XA = None
    else:
        XA = None
    if XA is None:
        if not torch.cuda.is_available():
            raise SystemExit("CUDA not available and no feature cache")
        print("extracting layer-21 self-report-ablated features (code-only) ...", flush=True)
        fA, eA = extract_multilayer([mask_selfreport(c) for c in cards], [LAYER], 4000)
        XA = np.hstack([fA[LAYER], eA]).astype(np.float32)
        np.savez(CACHE, XA=XA)
        print(f"cached features {XA.shape} -> {CACHE}", flush=True)

    yhat_n = cv_oof_resid(XA, y, tasks, loglen, residualize=False)
    yhat_r = cv_oof_resid(XA, y, tasks, loglen, residualize=True)

    big = np.array([t for t in np.unique(tasks) if (tasks == t).sum() >= MIN_N])
    _block(f"POOLED (tasks n>={MIN_N}: {', '.join(big)})", np.isin(tasks, big), y, v, yhat_n, yhat_r, loglen, tasks)
    for t in big:
        _block(f"per-task {t}", tasks == t, y, v, yhat_n, yhat_r, loglen, tasks)

    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
