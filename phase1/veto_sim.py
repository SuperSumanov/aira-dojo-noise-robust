"""③a — offline VETO simulation: does the probe RESCUE the deployment decision?

Bridges two earlier results:
  - budget_probe: the probe can't REPLACE the self-report as a selector (rank≠regret).
  - probe_rescue: the probe is right on ~59% of the PAIRS where the self-report is WRONG (spaceship).
The deployment question in between: when you must SHIP ONE node, does a light-touch probe VETO on the
self-report's pick (override only when the probe strongly distrusts a high-self-report node) yield a
higher TRUE grade than shipping the self-report's pick outright?

Sim: draw many random candidate pools of size K (the search's final shortlist). Per pool:
  - baseline: ship argmax(self_report)
  - veto:     ship self_report-best UNLESS its probe score is in the bottom half of the pool,
              then ship the best-probe node among the top-m self_report candidates.
  - blend (context): ship argmax( z(self_report) + lam*z(probe) ); lam=0 == baseline.
Report mean TRUE grade shipped and regret = oracle - shipped, per task, over K and seeds.
Probe = 5-fold CV within task (no leakage), identical to probe_rescue.

GREEN (=> ③b online worth building): on spaceship, veto regret <= baseline regret (veto doesn't hurt,
ideally helps) — i.e. the reward-hacking veto pays off at deployment. Weak-probe tasks (tps) may show
veto hurting; that's the expected, honest boundary.

NOTE (limitation, same as budget_probe): random pools are a simplification of a real search shortlist
(which is correlated via improve-lineage). ③b removes this by running the veto in live search.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.critics.base import Ridge
from phase1.critics.qwen_backend import extract_features
from phase1.dataset import labeled, tasks_of

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
KS = [3, 5, 10, 20]
SEEDS = [0, 1, 2, 3, 4]
DRAWS = 500                       # random candidate pools per (K, seed)
TOPM = 3                          # veto fallback pool = top-m by self-report
LAMS = [0.0, 0.25, 0.5, 1.0, 2.0]  # blend context sweep (0.0 == baseline)


def _cv_probe(X, y, seed=0, folds=5):
    n = len(y); p = np.zeros(n)
    idx = np.random.default_rng(seed).permutation(n)
    for f in np.array_split(idx, folds):
        tr = np.setdiff1d(idx, f, assume_unique=False)
        mu = X[tr].mean(0); sd = X[tr].std(0); sd[sd < 1e-8] = 1.0
        r = Ridge(2.0).fit((X[tr] - mu) / sd, y[tr])
        p[f] = r.predict((X[f] - mu) / sd)
    return p


def _z(a):
    a = np.asarray(a, float); s = a.std()
    return (a - a.mean()) / (s if s > 1e-8 else 1.0)


def _veto_pick(pool, v, p, topm):
    order = pool[np.argsort(-v[pool])]           # candidates by self-report desc
    sr_best = order[0]
    if p[sr_best] > np.median(p[pool]):          # probe does NOT object -> keep self-report best
        return sr_best
    cand = order[:min(topm, len(order))]         # veto -> best-probe among top-m self-report
    return cand[int(np.argmax(p[cand]))]


def main():
    import torch
    if not torch.cuda.is_available():                     # fail fast: node CUDA init failed -> resubmit
        raise SystemExit("CUDA not available (node GPU init failed) — resubmit on another node")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    print(f"{len(cards)} labeled cards; extracting frozen probe features ...", flush=True)
    feats = extract_features(cards, path=MODEL)
    fmap = {c.id: feats[i] for i, c in enumerate(cards)}

    print("\n=== VETO deployment sim: TRUE grade shipped (higher=better) & regret=oracle-shipped (lower=better) ===", flush=True)
    print(f"{'task':26s} {'K':>3} {'base_grd':>9} {'veto_grd':>9} {'base_reg':>9} {'veto_reg':>9} {'Δreg(+=veto better)':>20}", flush=True)
    blend_rows = []
    for t in tasks_of(cards):
        tc = [c for c in cards if c.task.name == t and c.y is not None]
        if len(tc) < 12:
            continue
        y = np.array([c.y for c in tc], float)
        vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in tc])
        hib = tc[0].task.higher_is_better
        v = vraw if hib else -vraw
        X = np.vstack([fmap[c.id] for c in tc])
        p = _cv_probe(X, y)
        vz, pz = _z(v), _z(p)
        n = len(tc)
        best_lam = {}
        for K in KS:
            if K > n:
                continue
            bg = vg = brg = vrg = 0.0; cnt = 0
            lam_reg = {l: 0.0 for l in LAMS}
            for s in SEEDS:
                rng = np.random.default_rng(1000 + s)
                for _ in range(DRAWS):
                    pool = rng.choice(n, size=K, replace=False)
                    oracle = y[pool].max()
                    b = pool[int(np.argmax(v[pool]))]
                    vv = _veto_pick(pool, v, p, TOPM)
                    bg += y[b]; vg += y[vv]; brg += oracle - y[b]; vrg += oracle - y[vv]; cnt += 1
                    for l in LAMS:
                        blend = pool[int(np.argmax(vz[pool] + l * pz[pool]))]
                        lam_reg[l] += oracle - y[blend]
            bg /= cnt; vg /= cnt; brg /= cnt; vrg /= cnt
            for l in LAMS:
                lam_reg[l] /= cnt
            bl = min(lam_reg, key=lam_reg.get)
            best_lam[K] = (bl, lam_reg[0.0], lam_reg[bl])
            print(f"{t:26s} {K:>3} {bg:>9.3f} {vg:>9.3f} {brg:>9.3f} {vrg:>9.3f} {brg - vrg:>+20.3f}", flush=True)
        blend_rows.append((t, best_lam))

    print("\n=== blend context: best lam per (task,K) — lam*=0 means no probe weight helps (baseline wins) ===", flush=True)
    print(f"{'task':26s} {'K':>3} {'lam*':>5} {'reg@lam0':>9} {'reg@lam*':>9}", flush=True)
    for t, bl in blend_rows:
        for K, (l, r0, rl) in bl.items():
            print(f"{t:26s} {K:>3} {l:>5.2f} {r0:>9.3f} {rl:>9.3f}", flush=True)


if __name__ == "__main__":
    main()
