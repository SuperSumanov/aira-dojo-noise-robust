"""D4 offline pre-check: is probe-vs-self-report DISAGREEMENT an EXPLORATION target, or just noise/hacking?

Gate for the (expensive, GPU, live-search) disagreement-exploration experiment. Runs FULLY OFFLINE on the
289 cached cards. LOTO probe (train on other tasks, predict the held-out task -- the regime a live search on
a NEW task faces). Bootstrap CIs + within-task label-permutation null (A2 lesson: too few resamples / no null
flips the verdict).

The D4 idea survives only if HIGH disagreement marks UNDER-ESTIMATED GOOD nodes (hidden gems the search
signal v misses) -- NOT (b) probe blind-spots (pure error) or (c) reward-hacked nodes (v inflated, y low).
Even though step1 already showed the probe is a WORSE overall ranker than self-report, that does NOT answer
this: exploration only needs the probe to carry ORTHOGONAL, correctly-directed grade-signal.

  T0 sanity   : reproduce self-report Spearman(v,y) ~ .48/.52/.61 and LOTO probe Spearman(p,y) ~ .2-.3.
                (if these don't reproduce, the plumbing is wrong -- stop and fix before trusting anything.)
  T1 GATE     : within-task PARTIAL Spearman corr(p, y | v) vs within-task-permutation null.
                Does the probe carry TRUE-grade signal BEYOND self-report? <= null / CI incl 0 -> RED.
  T2 direction: d = z(p)-z(v) within task. Are probe-optimistic (d>0) nodes genuine hidden gems (higher
                grade-residual-on-v) while self-report-optimistic (d<0) nodes are the over-valued/hacked ones?
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
RES = 300


def _rank(x):
    """Average ranks (proper Spearman ranks; ties averaged)."""
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    ranks[order] = np.arange(1, len(x) + 1, dtype=float)
    ux, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    sr = np.zeros(len(ux))
    np.add.at(sr, inv, ranks)
    return (sr / cnt)[inv]


def _resid_on(r, rz):
    """residual of r after linear fit on rz (with intercept)."""
    A = np.c_[np.ones_like(rz), rz]
    beta, *_ = np.linalg.lstsq(A, r, rcond=None)
    return r - A @ beta


def partial_spearman(p, v, y):
    """Spearman partial corr of p and y controlling for v."""
    rp, rv, ry = _rank(p), _rank(v), _rank(y)
    ep, ey = _resid_on(rp, rv), _resid_on(ry, rv)
    if ep.std() < 1e-9 or ey.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ep, ey)[0, 1])


def zt(x):
    x = np.asarray(x, float)
    s = x.std()
    return (x - x.mean()) / (s if s > 1e-9 else 1.0)


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    XA = np.load(CACHE)["XA"]
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else np.nan) for c in cards])
    v = np.full(len(cards), np.nan)
    for t in np.unique(tasks):
        m = tasks == t
        h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[m] = vraw[m] if h else -vraw[m]

    # ---- LOTO probe: train on all OTHER tasks, predict held-out task (the live-on-new-task regime) ----
    p = np.full(len(cards), np.nan)
    for t in np.unique(tasks):
        te = np.where(tasks == t)[0]
        tr = np.where(tasks != t)[0]
        p[te] = _dual_ridge(XA[tr], y[tr], XA[te])

    uniq = list(np.unique(tasks))

    # ================= T0 sanity =================
    print("=== T0 SANITY (must reproduce: self-report ~.48/.52/.61, LOTO probe ~.2-.3) ===", flush=True)
    for t in uniq:
        mv = (tasks == t) & ~np.isnan(v)
        mp = tasks == t
        print(f"  {t[:26]:26s}  n={mp.sum():3d}  self-report Spearman(v,y)={_spear(v[mv], y[mv]):+.3f}"
              f"   LOTO probe Spearman(p,y)={_spear(p[mp], y[mp]):+.3f}", flush=True)

    # ================= T1 GATE : partial corr(p, y | v) vs permutation null =================
    print("\n=== T1 GATE: within-task PARTIAL Spearman corr(p, y | v)  [probe grade-signal BEYOND self-report?] ===", flush=True)
    print("    (bootstrap 95% CI ; within-task label-permutation null 95th pct ; SIGNAL needs pc>null95 AND CI_lo>0)", flush=True)
    t1_pass = {}
    for t in uniq:
        idx = np.where((tasks == t) & ~np.isnan(v) & ~np.isnan(p))[0]
        pc = partial_spearman(p[idx], v[idx], y[idx])
        boots = []
        for b in range(RES):
            rng = np.random.default_rng(b)
            bi = rng.choice(idx, len(idx), replace=True)
            boots.append(partial_spearman(p[bi], v[bi], y[bi]))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        nulls = []
        for b in range(RES):
            rng = np.random.default_rng(10_000 + b)
            yp = y[idx].copy(); rng.shuffle(yp)
            nulls.append(partial_spearman(p[idx], v[idx], yp))
        null95 = np.percentile(nulls, 95)
        passed = (pc > null95) and (lo > 0)
        t1_pass[t] = passed
        print(f"  {t[:26]:26s}  n={len(idx):3d}  partial corr={pc:+.3f}  CI[{lo:+.3f},{hi:+.3f}]"
              f"  null95={null95:+.3f}  -> {'SIGNAL' if passed else 'noise'}", flush=True)

    # ================= T2 direction : is the disagreement pointed the EXPLORE way? =================
    print("\n=== T2 DIRECTION: probe-optimistic (d>0) = hidden gems? self-report-optimistic (d<0) = over-valued? ===", flush=True)
    D, YR, TASK = [], [], []
    for t in uniq:
        idx = np.where((tasks == t) & ~np.isnan(v) & ~np.isnan(p))[0]
        d = zt(p[idx]) - zt(v[idx])                      # disagreement, +=probe-optimistic
        yr = zt(_resid_on(_rank(y[idx]), _rank(v[idx]))) # grade-residual after removing self-report, z within task
        D.append(d); YR.append(yr); TASK.append(np.array([t] * len(idx)))
    D = np.concatenate(D); YR = np.concatenate(YR); TASK = np.concatenate(TASK)
    corr_dy = float(np.corrcoef(D, YR)[0, 1])
    # tertiles of disagreement, pooled
    lo_t, hi_t = np.percentile(D, [33.33, 66.67])
    bot = D <= lo_t     # self-report-optimistic (v >> p)
    top = D >= hi_t     # probe-optimistic (p >> v)
    print(f"  pooled corr(disagreement d, grade-residual-on-v) = {corr_dy:+.3f}   (n={len(D)})", flush=True)
    print(f"  mean grade-residual  |  probe-optimistic top-third d = {YR[top].mean():+.3f}"
          f"   vs   self-report-optimistic bottom-third d = {YR[bot].mean():+.3f}", flush=True)
    coherent = (YR[top].mean() > 0 > YR[bot].mean()) and (corr_dy > 0)
    print(f"  direction coherent (top>0>bottom & corr>0)? -> {coherent}", flush=True)

    # ================= VERDICT =================
    print("\n=== VERDICT ===", flush=True)
    powered = "spaceship-titanic"
    powered_t = next((t for t in uniq if t.startswith(powered)), uniq[0])
    n_signal = sum(t1_pass.values())
    if t1_pass.get(powered_t) and coherent:
        v_str = "GREEN"
        why = ("probe carries orthogonal grade-signal beyond self-report on the powered task, pointed the "
               "EXPLORE way (probe-optimistic=under-valued gems). Worth pricing a minimal live pilot.")
    elif not t1_pass.get(powered_t) and n_signal == 0:
        v_str = "RED"
        why = ("no probe grade-signal beyond self-report anywhere (partial corr within permutation null). "
               "Disagreement is empty -> live disagreement-exploration is dead on arrival. Do NOT ask for GPUs.")
    else:
        v_str = "AMBER"
        why = (f"signal on {n_signal}/{len(uniq)} tasks and/or direction incoherent (coherent={coherent}). "
               "Weak/mixed -> not worth GPUs yet; revisit framing.")
    print(f"  {v_str}: {why}", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
