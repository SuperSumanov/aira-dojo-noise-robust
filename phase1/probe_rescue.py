"""Change of angle: does the probe RESCUE the self-report where the self-report is WRONG?

feasibility (budget_probe) showed the probe can't beat the self-report at best-of-K selection —
because the self-report is already very good on these tasks. But H1's whole value is being
INDEPENDENT of the self-report, which only pays off WHERE THE SELF-REPORT FAILS.

Test on candidate PAIRS. A pair (i,j) is "self-report-wrong" if the oriented self-report ranks them
opposite to the true grade (says i>=j but grade i<j). On those pairs the self-report is 0% correct by
construction; a coin flip is 50%. If the probe scores >50% on exactly those pairs, it carries grade
signal precisely where the self-report misleads — the reward-hacking / val-overfit detection use-case
that best-of-K could never reveal (there the self-report was never wrong).

Probe predictions use 5-fold CV within each task (no leakage). We also report, as context, the probe's
accuracy on the pairs where the self-report is RIGHT (should stay high) and the overall self-report
disagreement rate (how much room there even is).
"""
import numpy as np

from phase1.cards import load_cards
from phase1.critics.base import Ridge
from phase1.critics.qwen_backend import extract_features
from phase1.dataset import labeled, tasks_of

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"


def _cv_probe(X, y, seed=0, folds=5):
    n = len(y); p = np.zeros(n)
    idx = np.random.default_rng(seed).permutation(n)
    for f in np.array_split(idx, folds):
        tr = np.setdiff1d(idx, f, assume_unique=False)
        mu = X[tr].mean(0); sd = X[tr].std(0); sd[sd < 1e-8] = 1.0
        r = Ridge(2.0).fit((X[tr] - mu) / sd, y[tr])
        p[f] = r.predict((X[f] - mu) / sd)
    return p


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    print(f"{len(cards)} labeled cards; extracting frozen probe features ...", flush=True)
    feats = extract_features(cards, path=MODEL)
    fmap = {c.id: feats[i] for i, c in enumerate(cards)}

    print("\n=== probe RESCUE rate on self-report-WRONG pairs (random=0.50; >0.50 => probe helps where self-report fails) ===", flush=True)
    print(f"{'task':30s} {'n':>4} {'wrong-pairs':>11} {'%pairs':>7} {'probe@wrong':>11} {'probe@right':>11}", flush=True)
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t and c.y is not None]
        if len(tc) < 10:
            continue
        y = np.array([c.y for c in tc], float)
        vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in tc])
        hib = tc[0].task.higher_is_better
        v = vraw if hib else -vraw
        X = np.vstack([fmap[c.id] for c in tc])
        p = _cv_probe(X, y)
        n_wrong = n_wrong_probe_ok = n_right = n_right_probe_ok = 0
        n_pairs = 0
        for i in range(len(tc)):
            for j in range(i + 1, len(tc)):
                if y[i] == y[j]:
                    continue
                n_pairs += 1
                true_sign = np.sign(y[i] - y[j])
                sr_ok = np.sign(v[i] - v[j]) == true_sign     # self-report ranks this pair correctly
                probe_ok = np.sign(p[i] - p[j]) == true_sign
                if sr_ok:
                    n_right += 1; n_right_probe_ok += probe_ok
                else:
                    n_wrong += 1; n_wrong_probe_ok += probe_ok
        rescue = n_wrong_probe_ok / max(1, n_wrong)
        keep = n_right_probe_ok / max(1, n_right)
        pct = 100.0 * n_wrong / max(1, n_pairs)
        print(f"{t:30s} {len(tc):>4} {n_wrong:>11} {pct:>6.1f}% {rescue:>11.2f} {keep:>11.2f}", flush=True)


if __name__ == "__main__":
    main()
