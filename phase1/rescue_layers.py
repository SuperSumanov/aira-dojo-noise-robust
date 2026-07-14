"""Rescue @ multiple layers — does the mid-layer probe (H1-ablation winner, layer 14/21) also improve
the self-report-FAILURE rescue rate vs the current last-layer (28) probe? Reuses h1_ablation's one-pass
multi-layer extractor + probe_rescue's wrong-pair metric. Layer 28 should reproduce the paper's 0.59
(spaceship). 5-fold CV dual ridge (no leak). No finetuning."""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled, tasks_of
from phase1.h1_ablation import extract_multilayer

RLAYERS = [14, 21, 28]
MAXCODE = 4000


def _cv_probe(X, y, seed=0, folds=5):
    n = len(y); p = np.zeros(n)
    idx = np.random.default_rng(seed).permutation(n)
    for f in np.array_split(idx, folds):
        tr = np.setdiff1d(idx, f)
        mu = X[tr].mean(0); sd = X[tr].std(0); sd[sd < 1e-8] = 1.0
        Xtr = (X[tr] - mu) / sd; Xte = (X[f] - mu) / sd
        a = np.linalg.solve(Xtr @ Xtr.T + 2.0 * np.eye(len(tr)), y[tr])
        p[f] = (Xte @ Xtr.T) @ a
    return p


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available — resubmit on another node")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    feats, ent = extract_multilayer(cards, RLAYERS, MAXCODE)     # normal prompts (self-report present)
    print("\n=== probe RESCUE @ self-report-WRONG pairs, by layer (random=0.50; 28=paper baseline) ===", flush=True)
    hdr = " ".join(f"L{L}@wrong L{L}@right" for L in RLAYERS)
    print(f"{'task':28s} {'n':>4} {'wrongP':>7}  {hdr}", flush=True)
    for t in tasks_of(cards):
        idx = np.array([i for i, c in enumerate(cards) if c.task.name == t and c.y is not None])
        if len(idx) < 10:
            continue
        tc = [cards[i] for i in idx]
        y = np.array([c.y for c in tc], float)
        vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in tc])
        hib = tc[0].task.higher_is_better
        v = vraw if hib else -vraw
        cells = []
        nwron = 0
        for L in RLAYERS:
            X = np.hstack([feats[L][idx], ent[idx]])
            p = _cv_probe(X, y)
            nw = nwok = nr = nrok = 0
            for i in range(len(tc)):
                for j in range(i + 1, len(tc)):
                    if y[i] == y[j]:
                        continue
                    ts = np.sign(y[i] - y[j])
                    if np.sign(v[i] - v[j]) == ts:
                        nr += 1; nrok += (np.sign(p[i] - p[j]) == ts)
                    else:
                        nw += 1; nwok += (np.sign(p[i] - p[j]) == ts)
            nwron = nw
            cells.append(f"{nwok / max(1, nw):>7.2f} {nrok / max(1, nr):>7.2f}")
        print(f"{t:28s} {len(tc):>4} {nwron:>7}  {'  '.join(cells)}", flush=True)


if __name__ == "__main__":
    main()
