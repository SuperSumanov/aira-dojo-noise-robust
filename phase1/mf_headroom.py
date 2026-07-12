"""④ Stage 0 — multi-fidelity HEADROOM probe (offline, no GPU, no DeepSeek).

Before building multi-fidelity + BAI, check it has headroom on our tasks. Uses only the FREE self-report
(val_at_low) + external true grade (y) from existing cards. Budget model: from a pool of candidates, a
budget of B full-eval-equivalents.
  single-fidelity : full-eval B RANDOM candidates -> best true among them (quality unknown a priori).
  mf(self-report) : the free self-report screens the whole pool; full-eval the top-B by self-report -> best true.
  oracle          : pool max true grade (perfect-screening ceiling).
headroom = mf(self-report) - single ; ceiling = oracle - single.

Done on BOTH real search-tree pools (grouped by run, correlated = the honest model) and random pools
(to expose the random-pool inflation that fooled ③a). GREEN (build multi-fidelity): on REAL pools,
mf(self-report) meaningfully beats single. RED: mf ~= single on real pools => low headroom, reconsider.
No Qwen/torch import -> pure-CPU, runs in seconds on the login node.
"""
import glob
import json

import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled, tasks_of

RUNS = "/research/d7/spc/yzyang4/aira-dojo-runs"
BUDGETS = [3, 5, 10]
DRAWS = 1000            # random pools
REPS = 200             # random subsets within a pool (single-fidelity estimate)


def node2run():
    """prefixed node id ('<comp>__<id>') -> run_key, so it matches build_cards' card.id."""
    m = {}
    for j in glob.glob(RUNS + "/**/journal.jsonl", recursive=True):
        try:
            rows = [json.loads(l) for l in open(j) if l.strip()]
        except Exception:
            continue
        comp = None
        for d in rows:
            mi = d.get("metric_info")
            if isinstance(mi, dict) and mi.get("competition_id"):
                comp = mi["competition_id"]; break
        if not comp:
            continue
        for d in rows:
            if d.get("id"):
                m[f"{comp}__{d['id']}"] = j
    return m


def eval_pool(ix, y, v, B, rng, reps=REPS):
    """(single, mf_selfreport, oracle) true grade for budget B on candidate pool `ix`."""
    if len(ix) <= B:
        return None
    oracle = float(y[ix].max())
    topB = ix[np.argsort(-v[ix])[:B]]                 # free self-report screen -> promote top-B
    mf = float(y[topB].max())
    sing = float(np.mean([y[ix[rng.choice(len(ix), B, replace=False)]].max() for _ in range(reps)]))
    return sing, mf, oracle


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    n2r = node2run()
    rng = np.random.default_rng(0)
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t and c.y is not None]
        if len(tc) < 8:
            continue
        y = np.array([c.y for c in tc], float)
        vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in tc])
        hib = tc[0].task.higher_is_better
        v = vraw if hib else -vraw
        n = len(tc)

        runs = {}
        for i, c in enumerate(tc):
            r = n2r.get(c.id)
            if r is not None:
                runs.setdefault(r, []).append(i)
        runs = {r: np.array(ix) for r, ix in runs.items() if len(ix) >= min(BUDGETS) + 2}
        Preal = int(np.median([len(ix) for ix in runs.values()])) if runs else min(2 * min(BUDGETS), n)

        print(f"\n### {t}: {n} cards | {len(runs)} real runs (pool>= {min(BUDGETS)+2}, median size {Preal}) | grade spread {y.min():.2f}-{y.max():.2f}", flush=True)
        print(f"{'B':>3} |  REAL: single  mf-sr  oracle   head |  RAND(P={Preal}): single  mf-sr   head", flush=True)
        for B in BUDGETS:
            # real pools
            acc = [eval_pool(ix, y, v, B, rng) for ix in runs.values()]
            acc = [a for a in acc if a]
            if acc:
                rs = np.mean([a[0] for a in acc]); rm = np.mean([a[1] for a in acc]); ro = np.mean([a[2] for a in acc])
            # random pools of size Preal
            sr = []; mr = []
            for _ in range(DRAWS):
                pl = rng.choice(n, min(Preal, n), replace=False)
                r = eval_pool(pl, y, v, B, rng, reps=1)
                if r:
                    sr.append(r[0]); mr.append(r[1])
            singR, mfR = (np.mean(sr), np.mean(mr)) if sr else (float("nan"), float("nan"))
            rl = f"{rs:>7.3f} {rm:>6.3f} {ro:>7.3f} {rm-rs:>+6.3f}" if acc else "   (no real pools)   "
            print(f"{B:>3} |  {rl} |  {singR:>7.3f} {mfR:>6.3f} {mfR-singR:>+6.3f}", flush=True)


if __name__ == "__main__":
    main()
