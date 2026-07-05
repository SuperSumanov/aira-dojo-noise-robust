"""Verify the real-Qwen backends end-to-end on the existing spaceship cards (single-task train/test
split, since we only have >=1 task labeled so far). Runs one_epoch (CPU baseline) + zeroshot + probe
(frozen 7B, no fine-tuning) and prints ranking/calibration metrics. Needs a GPU.

    python -m phase1.verify_qwen phase1/cards_real.jsonl spaceship-titanic
"""
import sys

import numpy as np

from phase1.cards import load_cards
from phase1.critics import build
from phase1.eval import metrics as M


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_real.jsonl"
    task = sys.argv[2] if len(sys.argv) > 2 else "spaceship-titanic"
    cards = [c for c in load_cards(path) if c.task.name == task and c.y is not None]
    print(f"{len(cards)} '{task}' cards")
    if len(cards) < 10:
        print("too few cards"); return
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(cards))
    ntr = int(len(cards) * 0.6)
    tr = [cards[i] for i in idx[:ntr]]
    te = [cards[i] for i in idx[ntr:]]
    yte = np.array([c.y for c in te])
    print(f"train={len(tr)} test={len(te)} | y_test range [{yte.min():.3f},{yte.max():.3f}]")
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else ["one_epoch", "zeroshot", "probe", "scalar"]
    for name in names:
        try:
            cr = build(name, backend="qwen")
            cr.fit(tr)
            pred = np.asarray(cr.predict([c.hidden() for c in te]), float)
            print(f"{name:10s} spearman={M.spearman(yte, pred):+.3f} kendall={M.kendall_tau(yte, pred):+.3f} "
                  f"regret@1={M.top_k_regret(yte, pred, 1):.3f} ece={M.ece(yte, pred):.3f}")
        except Exception as e:
            import traceback
            print(f"{name:10s} FAILED: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
