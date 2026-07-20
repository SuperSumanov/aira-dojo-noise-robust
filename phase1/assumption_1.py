"""Assumption-1 harness: does a probe trained on N-1 MLE tasks FAST-FIT a new task with FEW labels?
(advisor's assumption 1 = cross-MLE-task generalization + rapid fit to a new task).

Prototype on CACHED frozen features (zero GPU). Built-in verification: the k=0 column is pure LOTO and
MUST match our previously-established LOTO (~0.07 spaceship / 0.18 nomad / 0.47 tps from d4_precheck) --
if it doesn't, the harness is wired wrong. Then the few-shot curve (k>0) shows whether adding k labels
from the held-out task rapidly lifts the probe (= fast-fit).

Re-point CACHE/cards at the bigger set as the collection campaign accumulates data.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear, _dual_ridge
from phase1 import feat_cache

CACHE = "phase1/_cache_b1_feats.npz"
KS = [0, 5, 10, 20, 40]
RES = 40


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    X, mask = feat_cache.load_aligned(cards, CACHE)
    cards = [c for c, m in zip(cards, mask) if m]
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    assert len(cards) == len(X), f"cards/features misaligned: {len(cards)} vs {len(X)}"
    uniq = list(np.unique(tasks))
    print(f"N={len(cards)}  tasks={ {t: int((tasks==t).sum()) for t in uniq} }", flush=True)
    print(f"\n{'held-out task':32s} " + "  ".join(f"k={k:<3d}" for k in KS) + "   (Spearman on held-out task)", flush=True)

    for T in uniq:
        te_all = np.where(tasks == T)[0]
        tr_other = np.where(tasks != T)[0]
        if len(te_all) < 25:
            print(f"  {T[:32]:32s} (only {len(te_all)} nodes, skip)", flush=True)
            continue
        row = []
        for k in KS:
            vals = []
            for r in range(RES):
                rng = np.random.default_rng(r)
                perm = rng.permutation(te_all)
                adapt, test = perm[:k], perm[k:]
                if len(test) < 8:
                    continue
                tr = np.concatenate([tr_other, adapt]) if k > 0 else tr_other
                pred = _dual_ridge(X[tr], y[tr], X[test])
                vals.append(_spear(pred, y[test]))
            row.append(float(np.mean(vals)) if vals else float("nan"))
        print(f"  {T[:32]:32s} " + "  ".join(f"{v:+.3f}" for v in row), flush=True)

    print("\n=== VERIFY: k=0 column == pure LOTO. Expected ~ spaceship +0.07 / nomad +0.18 / tps +0.47", flush=True)
    print("    (from d4_precheck). If k=0 matches, harness is correctly wired.", flush=True)
    print("=== fast-fit read: does Spearman rise steeply from k=0 to k=5/10/20? ===", flush=True)
    print("=== done ===", flush=True)


if __name__ == "__main__":
    main()
