"""③a′ — VETO on REAL search trees: does the ③a win survive real (correlated) candidate pools?

③a used RANDOM candidate pools — its one caveat. Here each candidate pool is the ACTUAL set of graded
nodes from ONE real spaceship search run (journal), i.e. correlated via improve-lineage exactly as a
deployment shortlist would be. Probe = LEAVE-ONE-RUN-OUT ridge (train on all OTHER runs' spaceship
nodes, predict this run's) — no within-run leakage, stricter than ③a's within-task 5-fold.

Per run: baseline ships argmax(self_report); veto ships self-report-best UNLESS the probe puts it in
the pool's bottom half, then best-probe among top-m self_report. Report mean TRUE grade shipped and
regret vs the run's own oracle, baseline vs veto, over runs (+ per-run win/loss tally).

GREEN => the ③a win is not a random-pool artifact => ③b online worth building.
RED    => ③a was a random-pool artifact; skip the expensive ③b (offline falsification saves it again).
"""
import glob
import json

import numpy as np

from phase1.cards import load_cards
from phase1.critics.base import Ridge
from phase1.critics.qwen_backend import extract_features
from phase1.dataset import labeled

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
RUNS = "/research/d7/spc/yzyang4/aira-dojo-runs"
TASK = "spaceship-titanic"
TOPM = 3
MIN_POOL = 3          # a run needs >=3 graded nodes to be a deployment "choice"


def node2run_map():
    """node_id -> run_key (journal path) for journals whose graded nodes are TASK."""
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
                comp = mi["competition_id"]
                break
        if comp != TASK:
            continue
        for d in rows:
            if d.get("id"):
                m[f"{TASK}__{d['id']}"] = j          # match build_cards id = "<task>__<node id>"
    return m


def _z(a):
    a = np.asarray(a, float); s = a.std()
    return (a - a.mean()) / (s if s > 1e-8 else 1.0)


def _veto_pick(idx, v, p, topm):
    order = idx[np.argsort(-v[idx])]                 # by self-report desc
    sr = order[0]
    if p[sr] > np.median(p[idx]):                    # probe does NOT object -> keep self-report best
        return sr
    cand = order[:min(topm, len(order))]             # veto -> best-probe among top-m self-report
    return cand[int(np.argmax(p[cand]))]


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available (node GPU init failed) — resubmit on another node")

    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    sp = [c for c in cards if c.task.name == TASK and c.y is not None]
    print(f"{len(sp)} labeled {TASK} cards", flush=True)

    n2r = node2run_map()
    runs = {}
    for i, c in enumerate(sp):
        r = n2r.get(c.id)
        if r is not None:
            runs.setdefault(r, []).append(i)
    matched = sum(len(ix) for ix in runs.values())
    print(f"matched {matched}/{len(sp)} cards to {len(runs)} real runs (id join card<->journal)", flush=True)
    runs = {r: ix for r, ix in runs.items() if len(ix) >= MIN_POOL}
    print(f"{len(runs)} runs with >= {MIN_POOL} graded nodes (usable deployment pools)", flush=True)
    if not runs:
        raise SystemExit("no usable runs — id join likely failed; inspect card.id vs journal node id")

    print("extracting frozen probe features ...", flush=True)
    X = np.asarray(extract_features(sp, path=MODEL), float)
    y = np.array([c.y for c in sp], float)
    vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in sp])
    hib = sp[0].task.higher_is_better
    v = vraw if hib else -vraw

    # leave-one-run-out probe: predict each run's nodes from a ridge trained on all OTHER runs' nodes
    p = np.full(len(sp), np.nan)
    for r, ix in runs.items():
        tr = np.array([i for i in range(len(sp)) if n2r.get(sp[i].id) != r])
        mu = X[tr].mean(0); sd = X[tr].std(0); sd[sd < 1e-8] = 1.0
        rg = Ridge(2.0).fit((X[tr] - mu) / sd, y[tr])
        p[np.array(ix)] = rg.predict((X[np.array(ix)] - mu) / sd)

    base_reg = veto_reg = base_g = veto_g = 0.0
    wins = losses = ties = 0
    pools = []
    for r, ix in runs.items():
        ix = np.array(ix)
        pools.append(len(ix))
        oracle = y[ix].max()
        b = ix[int(np.argmax(v[ix]))]
        vv = _veto_pick(ix, v, p, TOPM)
        br, vr = oracle - y[b], oracle - y[vv]
        base_reg += br; veto_reg += vr; base_g += y[b]; veto_g += y[vv]
        if vr < br - 1e-9:
            wins += 1
        elif vr > br + 1e-9:
            losses += 1
        else:
            ties += 1
    n = len(runs)
    print("\n=== VETO on REAL spaceship search trees (leave-one-run-out probe) ===", flush=True)
    print(f"runs={n}  pool size: min={min(pools)} median={int(np.median(pools))} max={max(pools)}", flush=True)
    print(f"baseline (ship self-report best): mean true grade {base_g / n:.3f}  mean regret {base_reg / n:.3f}", flush=True)
    print(f"veto     (probe overrides)      : mean true grade {veto_g / n:.3f}  mean regret {veto_reg / n:.3f}", flush=True)
    print(f"Δregret (base - veto, + = veto better): {(base_reg - veto_reg) / n:+.3f}", flush=True)
    print(f"per-run tally: veto WINS {wins}, LOSES {losses}, TIES {ties}  (of {n})", flush=True)

    # --- rigor: does ANY probe blend weight beat baseline on real trees? (within-pool z, LORO probe) ---
    LAMS = [0.0, 0.25, 0.5, 1.0, 2.0]
    LAM_SIG = 1.0                                          # pre-registered (not post-hoc best) for significance
    lam_reg = {l: 0.0 for l in LAMS}
    per_base, per_blend = [], []                           # per-run regrets: lam=0 (baseline) vs lam=1
    for r, ix in runs.items():
        ix = np.array(ix)
        oracle = y[ix].max()
        vzi, pzi = _z(v[ix]), _z(p[ix])
        pr = {}
        for l in LAMS:
            pick = ix[int(np.argmax(vzi + l * pzi))]
            pr[l] = oracle - y[pick]
            lam_reg[l] += pr[l]
        per_base.append(pr[0.0]); per_blend.append(pr[LAM_SIG])
    print("\n=== blend rigor on real trees: mean regret by lam (lam=0 == baseline; lower=better) ===", flush=True)
    for l in LAMS:
        print(f"  lam={l:>4}: mean regret {lam_reg[l] / n:.4f}", flush=True)
    bl = min(lam_reg, key=lam_reg.get)
    print(f"best lam={bl} (regret {lam_reg[bl] / n:.4f}) vs baseline lam=0 (regret {lam_reg[0.0] / n:.4f})", flush=True)

    # --- decisive: bootstrap over the runs. delta = base_reg - blend_reg(lam=1); + => blend better ---
    delta = np.array(per_base) - np.array(per_blend)
    rng = np.random.default_rng(0)
    B, nr = 10000, len(delta)
    boots = delta[rng.integers(0, nr, size=(B, nr))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"\n=== bootstrap significance (lam={LAM_SIG} vs baseline; delta=base_reg-blend_reg, + = blend better) ===", flush=True)
    print(f"per-run delta: {(delta > 0).sum()} pos / {(delta < 0).sum()} neg / {(delta == 0).sum()} zero  (of {nr})", flush=True)
    print(f"observed mean delta = {delta.mean():+.4f}   95% CI = [{lo:+.4f}, {hi:+.4f}]   P(mean>0) = {(boots > 0).mean():.3f}", flush=True)
    print("VERDICT:", "CI excludes 0 — SMALL BUT REAL deployment benefit (soft blend)"
          if lo > 0 else "CI includes 0 — NOT significant; ③ negative airtight (noise)", flush=True)


if __name__ == "__main__":
    main()
