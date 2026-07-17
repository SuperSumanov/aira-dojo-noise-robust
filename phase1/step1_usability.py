"""Step 1 -- does MORE data make the probe USABLE, or just a better-but-still-useless probe?

Gates the expensive data-collection: A2(corrected) says the probe keeps improving with N, but the project
thesis is 'decodable != usable'. So the real question: as N grows, does the probe (a) start to BEAT the
free self-report for RANKING grade, and (b) become a BETTER reward-hacking DETECTOR? If usability rises
with N -> collecting data is justified. If usability is flat while accuracy rises -> better-but-useless.

All offline, cached ablated features, 40 resamples + SE (A2 taught us: too few resamples flips the verdict).
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _auroc, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
RES = 40


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

    # ---- baseline: how good is the FREE self-report at ranking grade (fixed, N-independent)? ----
    print("=== the bar to beat: free self-report's ranking of grade (Spearman v,y) ===", flush=True)
    sr = {}
    for t in np.unique(tasks):
        m = (tasks == t) & ~np.isnan(v)
        sr[t] = _spear(v[m], y[m])
        print(f"  {t[:26]:26s} self-report Spearman = {sr[t]:+.3f}", flush=True)

    grids = {"spaceship-titanic": [25, 50, 100, 150],
             "nomad2018-predict-transparent-conductors": [12, 18, 24],
             "tabular-playground-series-may-2022": [12, 16, 20]}

    # ---- (A) selection: probe ranking vs N -- does it cross the self-report line? ----
    print("\n=== (A) SELECTION: probe grade-ranking (Spearman) vs N  [beat self-report?] ===", flush=True)
    for t, grid in grids.items():
        idx = np.where(tasks == t)[0]; ntest = max(6, int(len(idx) * 0.3))
        row = []
        for N in grid:
            vals = []
            for o in range(RES):
                rng = np.random.default_rng(o); perm = rng.permutation(idx)
                test, pool = perm[:ntest], perm[ntest:]
                if N > len(pool):
                    continue
                tr = rng.choice(pool, N, replace=False)
                vals.append(_spear(_dual_ridge(XA[tr], y[tr], XA[test]), y[test]))
            row.append((N, np.mean(vals), np.std(vals) / np.sqrt(len(vals))))
        s = "  ".join(f"N{N}={m:+.2f}±{e:.2f}" for N, m, e in row)
        beat = "PROBE>self-report" if row[-1][1] > sr[t] else "still BELOW self-report"
        print(f"  {t[:20]:20s} sr={sr[t]:+.2f} | {s}  -> {beat}", flush=True)

    # ---- (B) detection: reward-hack detector AUROC vs N (spaceship: enough test) ----
    print("\n=== (B) DETECTION: reward-hack detector AUROC vs N  (self-report detector = anti-informative ~0.42) ===", flush=True)
    for t in ["spaceship-titanic"]:
        idx0 = np.where(tasks == t)[0]
        idx = idx0[~np.isnan(v[idx0])]                    # drop cards with missing self-report
        ntest = int(len(idx) * 0.35)
        print(f"  ({t[:12]}: {len(idx)}/{len(idx0)} cards have a self-report)", flush=True)
        for N in [25, 50, 100, 150]:
            aucs, sraucs = [], []
            for o in range(RES):
                rng = np.random.default_rng(o); perm = rng.permutation(idx)
                test, pool = perm[:ntest], perm[ntest:]
                if N > len(pool):
                    continue
                tr = rng.choice(pool, N, replace=False)
                pred = _dual_ridge(XA[tr], y[tr], XA[test])
                vt, yt = v[test], y[test]
                happy = vt >= np.median(vt)
                if happy.sum() < 8:
                    continue
                lab = yt[happy] < np.median(yt)
                if lab.sum() < 2 or lab.sum() == len(lab):
                    continue
                aucs.append(_auroc(-_z(pred[happy]), lab))
                sraucs.append(_auroc(-_z(vt[happy]), lab))
            if aucs:
                print(f"  {t[:12]:12s} N={N:>4}  probe-AUROC {np.mean(aucs):.3f}±{np.std(aucs)/np.sqrt(len(aucs)):.3f}"
                      f"   (self-report-AUROC {np.mean(sraucs):.3f})", flush=True)

    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
