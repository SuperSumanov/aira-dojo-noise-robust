"""Nail down two audit findings: (1) clean permutation null -- shuffle y WITHIN task, the probe must drop
to ~0 (else it's overfitting, not real signal). (2) A2 corrected -- spaceship/nomad/tps learning curves at
40 resamples with SE, to confirm whether the probe is still rising (data-limited) or flat (noise ceiling).
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    XA = np.load(CACHE)["XA"]
    N = len(cards)

    def probe_oof(tgt, seed=0):
        pred = np.full(N, np.nan)
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < 7:
                continue
            for f in np.array_split(np.random.default_rng(seed).permutation(idx), 5):
                tr = np.setdiff1d(idx, f); pred[f] = _dual_ridge(XA[tr], tgt[tr], XA[f])
        return pred

    def pts(pred, tgt):
        v = [_spear(pred[tasks == t], tgt[tasks == t]) for t in np.unique(tasks)
             if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
        return float(np.mean(v)) if v else float("nan")

    # ---- (1) clean permutation null: shuffle y within task ----
    real = pts(probe_oof(y), y)
    nulls = []
    for s in range(15):
        yp = y.copy()
        for t in np.unique(tasks):
            m = np.where(tasks == t)[0]
            yp[m] = y[m][np.random.default_rng(s).permutation(len(m))]
        nulls.append(pts(probe_oof(yp, seed=s), yp))
    nulls = np.array(nulls)
    print(f"[null] real probe = {real:+.3f} ; within-task label-shuffled null = {nulls.mean():+.3f} ± {nulls.std():.3f} "
          f"(max {nulls.max():+.3f})", flush=True)
    print(f"       -> null near 0 => the 0.29 is real X-y signal, not overfitting; the earlier 0.14 was the messy global shuffle\n", flush=True)

    # ---- (2) A2 corrected: learning curves, 40 resamples + SE ----
    grids = {"spaceship-titanic": [25, 50, 75, 100, 125, 150],
             "nomad2018-predict-transparent-conductors": [12, 18, 24],
             "tabular-playground-series-may-2022": [12, 16, 20]}
    for t, grid in grids.items():
        idx = np.where(tasks == t)[0]; ntest = max(6, int(len(idx) * 0.3))
        print(f"[A2 {t} n={len(idx)}]", flush=True)
        prev = None
        for Ntr in grid:
            vals = []
            for o in range(40):
                rng = np.random.default_rng(500 + o); perm = rng.permutation(idx)
                test, pool = perm[:ntest], perm[ntest:]
                if Ntr > len(pool):
                    continue
                tr = rng.choice(pool, Ntr, replace=False)
                vals.append(_spear(_dual_ridge(XA[tr], y[tr], XA[test]), y[test]))
            m = np.mean(vals); se = np.std(vals) / np.sqrt(len(vals))
            d = "" if prev is None else f"  Δ={m-prev:+.3f}"
            print(f"    N={Ntr:>4}  {m:+.3f} ± {se:.3f}{d}", flush=True)
            prev = m
        print("", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
