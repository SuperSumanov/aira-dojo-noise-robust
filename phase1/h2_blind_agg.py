"""H2 clean grounding-isolation: run BLIND with the SAME aggressive training (epochs 8, lr 2e-4) as the
already-run GROUNDED-aggressive (-0.144), on the same 80/20 split (seed 0). Now the student actually
trains for BOTH, so the only difference is grounding on/off -> a clean answer to the advisor's question.
  grounded-aggressive was -0.144 ; base zeroshot -0.179 ; scalar +0.335.
If blind-agg << grounded-agg -> grounding HELPS once trained. If blind-agg ~= grounded-agg -> grounding
does not help even when the student trains (the whole reasoning-generation critic is just uncompetitive)."""
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
    tte = np.array([c.task.name for c in te])
    print(f"train {len(tr)} test {len(te)} (80/20 seed 0)", flush=True)

    from phase1.critics.qwen_train import ReasoningTrainer
    trn = ReasoningTrainer(MODEL, teacher_path=TEACHER, grounded=False, epochs=8, lr=2e-4).fit(tr)
    pb = np.asarray(trn.predict(te), float)
    per = {t: spear(pb[tte == t], yte[tte == t]) for t in np.unique(tte) if (tte == t).sum() >= 4}
    ov = spear(pb, yte)
    print(f"\nBLIND-aggressive (ep8, lr2e-4): overall Spearman {ov:+.3f} | "
          + " ".join(f"{t[:8]}={v:+.2f}" for t, v in per.items()), flush=True)
    print("reference: GROUNDED-aggressive -0.144 | base zeroshot -0.179 | scalar +0.335", flush=True)
    d = -0.144 - ov
    print(f"\ngrounded-agg minus blind-agg = {-0.144 - ov:+.3f}", flush=True)
    print("VERDICT:", "GROUNDING HELPS once the student trains (grounded-agg > blind-agg) — but still << scalar"
          if d > 0.03 else
          "GROUNDING DOES NOT HELP even when trained (grounded-agg ~= blind-agg) — reasoning-generation critic is just uncompetitive",
          flush=True)


if __name__ == "__main__":
    main()
