"""A2 -- learning curve: is the frozen probe DATA-limited or NOISE-ceilinged?

For each task, hold out a fixed test set, train the (self-report-ablated) probe on N sampled cards, measure
Spearman on the held-out test, sweep N, average over resamples. If Spearman is still climbing at the max
available N -> more data would help (justifies collecting more). If it plateaus well before max N -> adding
data won't help (noise ceiling; don't burn GPUs collecting cards). Zero-GPU, cached ablated features.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
OUTER = 10          # test resamples
TEST_FRAC = 0.30


def curve(X, y, idx, grid, seed0=0):
    res = {N: [] for N in grid}
    ntest = max(6, int(len(idx) * TEST_FRAC))
    for o in range(OUTER):
        rng = np.random.default_rng(seed0 + o)
        perm = rng.permutation(idx)
        test, pool = perm[:ntest], perm[ntest:]
        for N in grid:
            if N > len(pool):
                continue
            tr = rng.choice(pool, N, replace=False)
            pred = _dual_ridge(X[tr], y[tr], X[test])
            res[N].append(_spear(pred, y[test]))
    return {N: (float(np.mean(v)), float(np.std(v))) for N, v in res.items() if v}


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    XA = np.load(CACHE)["XA"]
    print(f"features {XA.shape}, ablated/code-only; test_frac={TEST_FRAC}, {OUTER} resamples\n", flush=True)

    grids = {
        "spaceship-titanic": [25, 50, 75, 100, 125, 150],
        "nomad2018-predict-transparent-conductors": [12, 18, 24],
        "tabular-playground-series-may-2022": [12, 16, 20],
    }
    for t, grid in grids.items():
        idx = np.where(tasks == t)[0]
        if len(idx) < 12:
            continue
        c = curve(XA, y, idx, grid)
        pts = sorted(c.items())
        print(f"=== {t}  (n={len(idx)}) ===", flush=True)
        for N, (m, s) in pts:
            bar = "#" * int(max(0, m) * 40)
            print(f"  N={N:>4}  Spearman {m:+.3f} ± {s:.3f}  {bar}", flush=True)
        if len(pts) >= 2:
            (N1, (m1, _)), (N2, (m2, _)) = pts[-2], pts[-1]
            slope = (m2 - m1) / max(1, (N2 - N1))
            tail = m2 - pts[0][1][0]
            still = "STILL RISING -> data-limited" if (m2 - m1) > 0.02 else "FLAT -> near noise ceiling"
            print(f"  last step {N1}->{N2}: Δ={m2-m1:+.3f} (slope {slope:+.4f}/card); total {pts[0][0]}->{N2}: Δ={tail:+.3f}  => {still}\n", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
