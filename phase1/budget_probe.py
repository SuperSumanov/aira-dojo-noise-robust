"""Feasibility probe: does the probe's RANK skill translate into EVALUATION-BUDGET SAVINGS?

The load-bearing unknown (per NAS literature, White et al. 2021): a predictor with good rank
correlation does NOT automatically speed up search. We have probe spearman +0.407 (intra) — but does
that let a budget-limited search recover a good solution with FEWER expensive evaluations?

Offline simulation on real graded cards, NO online search / NO DeepSeek: under a budget of K expensive
evaluations, compare the best TRUE grade recovered by selecting the K candidates that each strategy
ranks highest:
  - critic  : rank by probe prediction (frozen Qwen features + ridge)   <- our method
  - proxy   : rank by self-reported val_at_low (the multi-fidelity / cheap-proxy analog, ~Hyperband)
  - random  : pick K at random (averaged)                                <- floor
  - oracle  : best grade over ALL candidates                             <- ceiling (regret=0)
regret(K) = oracle - selected_best(K); lower is better. If critic regret < proxy < random at small K,
the rank skill DOES translate into budget savings (rank->regret holds). If critic ~ random, it doesn't.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.critics.base import Ridge
from phase1.critics.qwen_backend import extract_features
from phase1.dataset import labeled

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
KS = [3, 5, 10, 20]
SPLIT_SEEDS = [0, 1, 2, 3, 4]     # intra train/test splits
RANDOM_DRAWS = 500                 # for the random baseline expectation


def _oriented_proxy(cards):
    hib = cards[0].task.higher_is_better if cards else True
    raw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
    return raw if hib else -raw


def _sim(train, test, feats_map, seed):
    """Fit probe on train, then simulate budget-K selection on test. Returns {K: {strategy: regret}}."""
    tr = [c for c in train if c.y is not None]
    Xtr = np.vstack([feats_map[c.id] for c in tr]); ytr = np.array([c.y for c in tr], float)
    mu = Xtr.mean(0); sd = Xtr.std(0); sd[sd < 1e-8] = 1.0
    ridge = Ridge(2.0).fit((Xtr - mu) / sd, ytr)
    Xte = np.vstack([feats_map[c.id] for c in test])
    probe_pred = ridge.predict((Xte - mu) / sd)
    yte = np.array([c.y for c in test], float)
    proxy = _oriented_proxy(test)
    rng = np.random.default_rng(seed)
    oracle = float(yte.max())
    crit_order = np.argsort(-probe_pred)
    prox_order = np.argsort(-proxy)
    out = {}
    for K in KS:
        k = min(K, len(yte))
        crit = float(yte[crit_order[:k]].max())
        prox = float(yte[prox_order[:k]].max())
        rnd = float(np.mean([yte[rng.choice(len(yte), k, replace=False)].max() for _ in range(RANDOM_DRAWS)]))
        out[K] = {"oracle": oracle, "critic_regret": oracle - crit,
                  "proxy_regret": oracle - prox, "random_regret": oracle - rnd}
    return out


def _report(label, per_seed):
    print(f"\n=== {label}: regret(K) = oracle - best-true-grade-recovered (lower=better) ===", flush=True)
    print(f"{'K':>3} | {'critic(probe)':>14} {'proxy(selfrep)':>14} {'random':>10}", flush=True)
    for K in KS:
        c = np.mean([s[K]["critic_regret"] for s in per_seed])
        p = np.mean([s[K]["proxy_regret"] for s in per_seed])
        r = np.mean([s[K]["random_regret"] for s in per_seed])
        cs = np.std([s[K]["critic_regret"] for s in per_seed])
        print(f"{K:>3} | {c:>10.3f}±{cs:.2f} {p:>14.3f} {r:>10.3f}", flush=True)


def _grade_dist(cards, label):
    y = np.array([c.y for c in cards], float)
    frac_top = float(np.mean(y >= y.max() - 0.05))   # top-heaviness: fraction within 0.05 of the max
    print(f"[grade dist] {label:28s} n={len(y):3d} min={y.min():.3f} max={y.max():.3f} "
          f"mean={y.mean():.3f} std={y.std():.3f} frac_within_0.05_of_max={frac_top:.2f}", flush=True)


def main():
    from phase1.dataset import tasks_of
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    print(f"{len(cards)} labeled cards; extracting frozen probe features ...", flush=True)
    feats = extract_features(cards, path=MODEL)
    fmap = {c.id: feats[i] for i, c in enumerate(cards)}

    print("\n--- grade distributions (top-heavy => random baseline already near-optimal => less room for critic) ---", flush=True)
    for t in tasks_of(cards):
        _grade_dist([c for c in cards if c.task.name == t], t)

    # INTRA: same-task 60/40 split, multiple seeds — for EVERY task
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t]
        if len(tc) < 12:
            print(f"\n(skip INTRA {t}: only {len(tc)} cards)", flush=True); continue
        intra = []
        for s in SPLIT_SEEDS:
            rng = np.random.default_rng(s)
            idx = rng.permutation(len(tc)); ntr = int(len(tc) * 0.6)
            tr = [tc[i] for i in idx[:ntr]]; te = [tc[i] for i in idx[ntr:]]
            intra.append(_sim(tr, te, fmap, seed=100 + s))
        _report(f"INTRA {t}", intra)

    # LOTO: train on the other tasks, select over the held-out task — for EVERY task
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t]
        others = [c for c in cards if c.task.name != t]
        if len(tc) < 6 or not others:
            continue
        loto = [_sim(others, tc, fmap, seed=200 + s) for s in range(3)]
        _report(f"LOTO {t}", loto)


if __name__ == "__main__":
    main()
