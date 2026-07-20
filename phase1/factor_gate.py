"""Factor gate: do the A1 interpretable factors (esp. leak_guard) carry grade-signal BEYOND self-report?

The user's idea: use interpretable factors (from A1's checklist -- SAE couldn't isolate a cleaner latent one)
as a PLANNING target: steer generation toward the factor. That only helps if the factor carries TRUE-grade
signal the FREE self-report MISSES (else the agent already gets rewarded for it). Same cheap-offline gate
logic as the D4 pre-check, now per-factor.

Prime suspect: leak_guard -- low prevalence (~0.20 = headroom to steer) AND plausibly where self-report is
fooled (leakage inflates validation but not test). If it carries beyond-self-report grade signal it is a
clean, interpretable planning lever even though the full black-box probe carried none (D4 was RED).

  T0 : prevalence of each practice (headroom = not saturated, not absent) + raw factor->grade (A1 sanity).
  T1 : per-factor within-task PARTIAL Spearman(factor, grade | self-report) on the powered task (spaceship,
       n~202) + all tasks; bootstrap CI + within-task label-permutation null. SIGNAL = pc>null95 & CI_lo>0.
  T2 : deep-dive leak_guard -- also control for ALL other factors; raw grade & self-report split (leak=1 vs 0).
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear
from phase1.a1_mechanism import feats

RES = 300


def _rank(x):
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    ranks[order] = np.arange(1, len(x) + 1, dtype=float)
    ux, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    sr = np.zeros(len(ux))
    np.add.at(sr, inv, ranks)
    return (sr / cnt)[inv]


def _resid_on(r, Z):
    """residual of r after linear fit on Z (Z: 1d or 2d), with intercept."""
    Z = np.atleast_2d(Z)
    if Z.shape[0] != len(r):
        Z = Z.T
    A = np.c_[np.ones(len(r)), Z]
    beta, *_ = np.linalg.lstsq(A, r, rcond=None)
    return r - A @ beta


def partial_spearman(f, v, y, extra=None):
    """Spearman partial corr of f and y controlling for v (+ optional extra columns)."""
    rf, ry = _rank(f), _rank(y)
    Z = _rank(v) if extra is None else np.column_stack([_rank(v)] + [_rank(e) for e in extra.T])
    ef, ey = _resid_on(rf, Z), _resid_on(ry, Z)
    if ef.std() < 1e-9 or ey.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ef, ey)[0, 1])


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else np.nan) for c in cards])
    v = np.full(len(cards), np.nan)
    for t in np.unique(tasks):
        m = tasks == t
        h = next(c for c in cards if c.task.name == t).task.higher_is_better
        v[m] = vraw[m] if h else -vraw[m]

    names = list(feats(cards[0].code).keys())
    F = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    uniq = list(np.unique(tasks))
    powered = next((t for t in uniq if t.startswith("spaceship")), uniq[0])

    # ---------------- T0 prevalence ----------------
    print("=== T0 prevalence (headroom = not saturated ~1.0, not absent ~0.0) ===", flush=True)
    bink = [k for k in names if set(np.unique(F[:, names.index(k)])) <= {0.0, 1.0}]
    for k in bink:
        print(f"  {k:11s} prevalence={F[:, names.index(k)].mean():.2f}", flush=True)

    def col(k):
        return F[:, names.index(k)]

    def one_factor(fvals, idx):
        pc = partial_spearman(fvals[idx], v[idx], y[idx])
        boots = []
        for b in range(RES):
            rng = np.random.default_rng(b)
            bi = rng.choice(idx, len(idx), replace=True)
            boots.append(partial_spearman(fvals[bi], v[bi], y[bi]))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        nulls = []
        for b in range(RES):
            rng = np.random.default_rng(9000 + b)
            yp = y[idx].copy(); rng.shuffle(yp)
            nulls.append(partial_spearman(fvals[idx], v[idx], yp))
        null95 = np.percentile(nulls, 95)
        return pc, lo, hi, null95

    # ---------------- T1 per-factor partial corr on powered task ----------------
    pidx = np.where((tasks == powered) & ~np.isnan(v))[0]
    print(f"\n=== T1 partial Spearman(factor, grade | self-report) on powered task {powered[:20]} (n={len(pidx)}) ===", flush=True)
    print("    SIGNAL = pc>null95 AND CI excludes 0.  (+)=raises grade beyond self-report, (-)=lowers", flush=True)
    rows = []
    for k in names:
        fv = col(k)
        if fv[pidx].std() < 1e-9:
            continue
        pc, lo, hi, null95 = one_factor(fv, pidx)
        sig = (abs(pc) > null95) and (lo * hi > 0)
        rows.append((k, pc, lo, hi, null95, sig, fv.mean()))
    for k, pc, lo, hi, null95, sig, prev in sorted(rows, key=lambda r: -abs(r[1])):
        flag = "  <== SIGNAL" if sig else ""
        print(f"  {k:11s} prev={prev:.2f}  partial={pc:+.3f}  CI[{lo:+.3f},{hi:+.3f}]  null95={null95:.3f}{flag}", flush=True)

    # ---------------- T1b leak_guard across all tasks ----------------
    print("\n=== T1b leak_guard partial Spearman(leak, grade | self-report) per task ===", flush=True)
    lg_pass = {}
    for t in uniq:
        idx = np.where((tasks == t) & ~np.isnan(v))[0]
        fv = col("leak_guard")
        if fv[idx].std() < 1e-9:
            print(f"  {t[:24]:24s} n={len(idx):3d}  (no variance)", flush=True); continue
        pc, lo, hi, null95 = one_factor(fv, idx)
        passed = (pc > null95) and (lo > 0)
        lg_pass[t] = passed
        print(f"  {t[:24]:24s} n={len(idx):3d}  partial={pc:+.3f}  CI[{lo:+.3f},{hi:+.3f}]  null95={null95:.3f}"
              f"  -> {'SIGNAL' if passed else 'noise'}", flush=True)

    # ---------------- T2 leak_guard deep-dive on powered task ----------------
    print(f"\n=== T2 leak_guard deep-dive on {powered[:20]} ===", flush=True)
    lg = col("leak_guard")[pidx]
    yy, vv = y[pidx], v[pidx]
    if lg.std() > 1e-9:
        print(f"  leak=1: n={int(lg.sum())}  mean grade={yy[lg == 1].mean():.4f}  mean self-report={vv[lg == 1].mean():.4f}", flush=True)
        print(f"  leak=0: n={int((1 - lg).sum())}  mean grade={yy[lg == 0].mean():.4f}  mean self-report={vv[lg == 0].mean():.4f}", flush=True)
        # control for ALL other factors too
        others = np.column_stack([col(k)[pidx] for k in names if k != "leak_guard" and col(k)[pidx].std() > 1e-9])
        pc_full = partial_spearman(lg, vv, yy, extra=others)
        print(f"  partial(leak, grade | self-report + all other factors) = {pc_full:+.3f}", flush=True)

    # ---------------- VERDICT ----------------
    print("\n=== VERDICT ===", flush=True)
    # a clean planning lever = a factor with headroom (0.1<prev<0.7) that raises grade beyond self-report on powered task
    levers = [(k, pc, prev) for k, pc, lo, hi, null95, sig, prev in rows if sig and pc > 0 and 0.1 < prev < 0.7]
    if lg_pass.get(powered):
        print("  GREEN: leak_guard carries positive grade-signal BEYOND self-report on the powered task"
              " -> a clean, interpretable planning lever (steer generation to add it). This is the D1-planning target.", flush=True)
    elif levers:
        ks = ", ".join(f"{k}({pc:+.2f},prev {prev:.2f})" for k, pc, prev in levers)
        print(f"  AMBER/GREEN: leak_guard not clear on powered task, but other headroom levers carry beyond-self-report"
              f" signal: {ks}. Interpretable planning target(s) exist -- worth a focused look.", flush=True)
    else:
        print("  RED: no headroom factor (incl. leak_guard) carries grade-signal beyond self-report on the powered"
              " task -> the factors are redundant with the free signal for OPTIMIZATION. Planning-via-factors is"
              " likely a no-op. (The factor MAP is still a valid EXPLANATION contribution.)", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
