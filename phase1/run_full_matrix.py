"""Full LOTO matrix on the REAL cards with the REAL Qwen backends -> reasoning-vs-others verdict.

Efficiency: the frozen backbones (zeroshot generation, probe features) don't depend on training, so
they are computed ONCE over all cards and reused across every (fold, N, seed). Only scalar/reasoning
(QLoRA) are retrained per split. Writes a per-run CSV + sample-efficiency plots.

Usage:
  python -m phase1.run_full_matrix phase1/cards_real.jsonl phase1/_full_out \
      [--budgets 25,50,all] [--seeds 0,1] [--only-fold spaceship-titanic] [--critics ...]
"""
import argparse
import os

import numpy as np

from phase1.cards import load_cards
from phase1.critics import build
from phase1.critics.base import Ridge
from phase1.dataset import labeled, loto_folds, subsample
from phase1.eval import metrics as M
from phase1.eval.runner import Row, write_csv

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"


def _predict(name, tr, test, zs_cache, probe_cache):
    hidden = [c.hidden() for c in test]
    if name in ("one_epoch", "asha"):
        cr = build(name); cr.fit(tr)
        return np.asarray(cr.predict(hidden), float)
    if name == "zeroshot":
        return np.array([zs_cache[c.id] for c in test])
    if name == "probe":
        tr_l = [c for c in tr if c.y is not None]
        if not tr_l:
            return np.zeros(len(test))
        X = np.vstack([probe_cache[c.id] for c in tr_l]); y = np.array([c.y for c in tr_l], float)
        mu = X.mean(0); sd = X.std(0); sd[sd < 1e-8] = 1.0
        r = Ridge(2.0).fit((X - mu) / sd, y)
        Xt = np.vstack([probe_cache[c.id] for c in test])
        return r.predict((Xt - mu) / sd)
    if name in ("scalar", "reasoning"):
        import gc
        import torch
        cr = build(name, backend="qwen"); cr.fit(tr)
        out = np.asarray(cr.predict(hidden), float)
        if getattr(cr, "_trainer", None) is not None:      # free this split's trained model
            cr._trainer.model = None; cr._trainer.tok = None
        del cr; gc.collect(); torch.cuda.empty_cache()
        return out
    return None


def _intra_folds(cards, test_frac=0.4, seed=42):
    """Each task -> one fold with a FIXED internal train/test split (same-task setting). test is held
    fixed across N/seed so budgets are comparable; the training subsample varies by budget+seed."""
    from phase1.dataset import tasks_of
    rng = np.random.default_rng(seed)
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t]
        idx = rng.permutation(len(tc))
        ntr = int(len(tc) * (1 - test_frac))
        train = [tc[i] for i in idx[:ntr]]
        test = [tc[i] for i in idx[ntr:]]
        if train and test:
            yield t, train, test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cards"); ap.add_argument("out")
    ap.add_argument("--budgets", default="25,50,all")
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--only-fold", default=None, help="run just this held-out task (smoke)")
    ap.add_argument("--critics", default="one_epoch,asha,zeroshot,probe,scalar,reasoning")
    ap.add_argument("--mode", default="loto", choices=["loto", "intra"],
                    help="loto=leave-one-task-out (cross-task); intra=same-task train/test split")
    a = ap.parse_args()

    cards = labeled(load_cards(a.cards))
    budgets = [b if b == "all" else int(b) for b in a.budgets.split(",")]
    seeds = tuple(int(s) for s in a.seeds.split(","))
    names = a.critics.split(",")
    os.makedirs(a.out, exist_ok=True)
    print(f"{len(cards)} labeled cards; folds={[t for t,_,_ in loto_folds(cards)]}", flush=True)

    # ---- precompute frozen backbone outputs once (reused across all folds/N/seeds) ----
    zs_cache = probe_cache = None
    from phase1.critics.qwen_backend import extract_features, generate_scores
    if "zeroshot" in names:
        print("[precompute] zeroshot frozen scores over all cards ...", flush=True)
        raw = generate_scores(cards, path=MODEL, for_reasoning=False)
        zs_cache = {c.id: (0.5 if s is None else s) for c, s in zip(cards, raw)}
    if "probe" in names:
        print("[precompute] probe frozen features over all cards ...", flush=True)
        feats = extract_features(cards, path=MODEL)
        probe_cache = {c.id: feats[i] for i, c in enumerate(cards)}

    # free the frozen backbone before per-split QLoRA training (avoid 2x7B in VRAM -> OOM)
    if any(n in names for n in ("scalar", "reasoning")):
        import gc
        import torch
        from phase1.critics.qwen_backend import _MODELS
        _MODELS.clear(); gc.collect(); torch.cuda.empty_cache()
        print("[precompute] freed frozen backbone before training", flush=True)

    rows = []
    csv = os.path.join(a.out, "runs_real.csv")
    folds = list(_intra_folds(cards)) if a.mode == "intra" else list(loto_folds(cards))
    if a.only_fold:
        folds = [f for f in folds if f[0] == a.only_fold]
    print(f"mode={a.mode}; {len(folds)} folds", flush=True)
    for test_task, train_all, test in folds:
        yte = np.array([c.y for c in test], float)
        for N in budgets:
            for seed in seeds:
                tr = subsample(train_all, N, seed)
                blabel = "all" if N == "all" else str(N)
                for name in names:
                    pred = _predict(name, tr, test, zs_cache, probe_cache)
                    if pred is None:
                        continue
                    m = M.compute_all(yte, pred)
                    rows.append(Row(predictor=name, budget=blabel, seed=seed, task=test_task,
                                    n_train=len(tr), n_test=len(test), metrics=m, commit="real"))
                    print(f"[{test_task} N={blabel} s{seed}] {name}: spearman={m['spearman']:+.3f} "
                          f"ece={m['ece']:.3f}", flush=True)
        write_csv(rows, csv)   # incremental flush after each fold (survive a wall-clock kill)
        print(f"[checkpoint] fold {test_task} done -> {len(rows)} runs saved", flush=True)
    print(f"\n{len(rows)} runs -> {csv}", flush=True)
    try:
        from phase1.eval.plots import plot_all
        for msg in plot_all(rows, a.out):
            print(msg)
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()
