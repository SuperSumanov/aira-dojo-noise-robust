"""H2 grounded-reasoning test (advisor idea) — does a GROUNDED teacher (SEES the true grade, writes a
COHERENT post-hoc rationale) beat the current BLIND teacher? 3 arms on ONE 80/20 split (seed 0):
  scalar  |  reasoning-blind (current)  |  reasoning-grounded (advisor)
Report overall + per-task TEST Spearman. Test predictions are leakage-free (the student never sees a
test grade); the decisive question is whether training on coherent grounded rationales yields a better
score-predictor than blind rationales — or whether the train/test information MISMATCH (arXiv:2602.04942)
makes grounded <= blind (the student can't reproduce answer-conditioned rationales from inputs alone).
Leakage controls on the distilled rationale: teacher told not to restate the score + all digits stripped.
Honest ceiling: even if grounded wins on RANK, rank != regret still holds (no search/selection gain).
"""
import gc
import os

import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.critics.scalar import ScalarCritic
from phase1.critics.reasoning import ReasoningCritic


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return 0.0 if ra.std() < 1e-9 or rb.std() < 1e-9 else float(np.corrcoef(ra, rb)[0, 1])


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available — resubmit on another node")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    idx = np.random.default_rng(0).permutation(len(cards))
    cut = int(0.8 * len(cards))
    tr = [cards[i] for i in idx[:cut]]; te = [cards[i] for i in idx[cut:]]
    yte = np.array([c.y for c in te], float)
    tte = np.array([c.task.name for c in te])
    print(f"train {len(tr)} test {len(te)}  (80/20, seed 0)", flush=True)

    # ONE arm per job (ARM env) — separate processes avoid the cross-arm CUDA OOM (each gets a clean 24GB GPU).
    ARM = os.environ.get("ARM", "grounded")
    mk = {
        "scalar": lambda: ScalarCritic(backend="qwen", max_code=1200),
        "blind": lambda: ReasoningCritic(backend="qwen", grounded=False),
        "grounded": lambda: ReasoningCritic(backend="qwen", grounded=True),
    }[ARM]
    print(f"\n===== fitting ARM={ARM} =====", flush=True)
    cr = mk().fit(tr)
    p = np.asarray(cr.predict(te), float)
    per = {t: spear(p[tte == t], yte[tte == t]) for t in np.unique(tte) if (tte == t).sum() >= 4}
    print(f"H2_RESULT ARM={ARM}: overall {spear(p, yte):+.3f} | "
          + " ".join(f"{t[:8]}={v:+.2f}" for t, v in per.items()), flush=True)


if __name__ == "__main__":
    main()
