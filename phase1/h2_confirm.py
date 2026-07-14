"""Confirm the H2 identical-result cause: is the reasoning student UNDERFIT at 231 cards (both blind &
grounded collapse to the base model -> identical)? On the same 80/20 split (seed 0) compare:
  (1) base ZEROSHOT (no training, greedy score on the reasoning prompt)
  (2) GROUNDED with AGGRESSIVE training (epochs 8, lr 2e-4) vs the default (epochs 3, lr 1e-4) that collapsed.
If grounded-aggressive DIVERGES from zeroshot (low agreement) -> it actually trained; the earlier
collapse was UNDERFIT (and grounding may then matter). If grounded-aggressive ~= zeroshot -> the collapse
is a deeper predict-side issue, not just training amount. Also report its Spearman vs scalar (+0.335)."""
import gc

import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
TEACHER = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-14B-Instruct"


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return 0.0 if ra.std() < 1e-9 or rb.std() < 1e-9 else float(np.corrcoef(ra, rb)[0, 1])


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    idx = np.random.default_rng(0).permutation(len(cards))
    cut = int(0.8 * len(cards))
    tr = [cards[i] for i in idx[:cut]]; te = [cards[i] for i in idx[cut:]]
    yte = np.array([c.y for c in te], float)
    print(f"train {len(tr)} test {len(te)} (80/20 seed 0)", flush=True)

    # (1) base zeroshot, no training
    from phase1.critics.qwen_backend import generate_scores, _MODELS
    zs = np.asarray(generate_scores(te, path=MODEL, for_reasoning=True, max_code=1200), float)
    print(f"\nZEROSHOT base (no training): overall Spearman {spear(zs, yte):+.3f}", flush=True)
    _MODELS.clear(); gc.collect(); torch.cuda.empty_cache()

    # (2) grounded, AGGRESSIVE training
    from phase1.critics.qwen_train import ReasoningTrainer
    trn = ReasoningTrainer(MODEL, teacher_path=TEACHER, grounded=True, epochs=8, lr=2e-4).fit(tr)
    pg = np.asarray(trn.predict(te), float)
    print(f"GROUNDED-aggressive (ep8, lr2e-4): overall Spearman {spear(pg, yte):+.3f}", flush=True)

    agree = float(np.corrcoef(pg, zs)[0, 1]) if pg.std() > 1e-9 and zs.std() > 1e-9 else 1.0
    print(f"\nagreement(grounded-agg vs base zeroshot): pearson {agree:+.3f}  mean|Δ| {np.mean(np.abs(pg - zs)):.3f}", flush=True)
    print(f"reference: scalar was +0.335, blind==grounded(default) was -0.162 on this split", flush=True)
    print("VERDICT:", "grounded-agg DIVERGED from base -> it TRAINED; earlier blind==grounded collapse was UNDERFIT"
          if agree < 0.95 else
          "grounded-agg ~= base zeroshot -> predict-side collapse (LoRA not affecting the score), not just underfit",
          flush=True)


if __name__ == "__main__":
    main()
