"""POWERED illusion-atlas on FOREAGENT agent_runs edges (loads edges.json from agentruns_pull.py).

Tests the pivot main line with power + cross-agent split:
 - decoupling of dVal(self-report change) vs dTrue(true-grade change)
 - per operator (A1 factor ADDED): mean dVal / mean dTrue (within-task z) + bootstrap 95% CI -> classify
   GENUINE (true grade rises) / ILLUSION (self-report rises, true grade doesn't) / net-neg
 - LENGTH-RESIDUALIZED (guard the complexity confound)
 - CROSS-AGENT consistency: does each operator classify the same way in AIDE vs ForeAgent?
GREEN => operators cleanly + cross-agent-consistently split -> main line stands (build + intervention).
"""
import os
import json
import collections

import numpy as np

from phase1.a1_mechanism import feats

ROOT = "/research/d7/spc/yzyang4/foreagent_agentruns"
NAMES = list(feats("").keys())
RES = 2000


def zt(x, tasks):
    out = np.zeros_like(x, float)
    for t in np.unique(tasks):
        m = tasks == t; s = x[m].std()
        out[m] = (x[m] - x[m].mean()) / (s if s > 1e-9 else 1.0)
    return out


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() < 1e-9 or rb.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def mean_ci(x, seed=0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3:
        return (np.nan, np.nan, np.nan, len(x))
    rng = np.random.default_rng(seed)
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(RES)]
    return (float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(x))


def resid_on(y, x):
    A = np.c_[np.ones(len(x)), x]
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    return y - A @ b


def main():
    E = json.load(open(os.path.join(ROOT, "edges.json")))
    print(f"loaded {len(E)} edges", flush=True)
    if len(E) < 40:
        print("too few edges; abort", flush=True); return
    agent = np.array([e["agent"] for e in E]); task = np.array([e["task"] for e in E])
    dT = np.array([e["dTrue"] for e in E], float); dV = np.array([e["dVal"] for e in E], float)
    dlen = np.array([e["df"]["code_len"] for e in E], float)
    zT, zV = zt(dT, task), zt(dV, task)
    zTr, zVr = zt(resid_on(zt(dT, task), dlen), task), zt(resid_on(zt(dV, task), dlen), task)
    print(f"agents={dict(collections.Counter(agent))}  tasks={len(set(task))}", flush=True)
    print(f"decoupling corr(dVal,dTrue | task-z) = {spear(zV, zT):+.3f}   (length-resid {spear(zVr, zTr):+.3f})", flush=True)

    def atlas(zVv, zTv, title):
        print(f"\n=== {title} ===", flush=True)
        print(f"  {'operator(+f)':13s} {'n':>4} {'meanDVal[95CI]':>20} {'meanDTrue[95CI]':>20} {'class':9s}| {'AIDE dT':>8} {'FA dT':>8} xagent", flush=True)
        rows = []
        for k in ["hp_search", "ensemble", "feat_eng", "cv", "leak_guard", "reg", "nn", "xgb", "lgbm", "catboost", "sk_gbm", "rf"]:
            add = np.array([e["df"][k] > 0 for e in E])
            if add.sum() < 8:
                continue
            mv, vlo, vhi, _ = mean_ci(zVv[add], 1)
            mt, tlo, thi, _ = mean_ci(zTv[add], 2)
            cls = "ILLUSION" if (vlo > 0 and thi <= 0.05) else ("genuine" if tlo > 0 else ("net-neg" if thi < 0 else "flat"))
            aT = zTv[add & (agent == "AIDE")]; fT = zTv[add & (agent == "ForeAgent")]
            amt = aT.mean() if len(aT) >= 5 else np.nan
            fmt = fT.mean() if len(fT) >= 5 else np.nan
            xa = ("CONSIST" if (not np.isnan(amt) and not np.isnan(fmt) and np.sign(amt) == np.sign(fmt))
                  else ("split" if (not np.isnan(amt) and not np.isnan(fmt)) else "1-agent"))
            print(f"  {k:13s} {int(add.sum()):>4} {mv:>+6.2f}[{vlo:+.2f},{vhi:+.2f}] {mt:>+6.2f}[{tlo:+.2f},{thi:+.2f}] {cls:9s}| {amt:>+8.3f} {fmt:>+8.3f} {xa}", flush=True)
            rows.append((k, cls, xa))
        return rows

    atlas(zV, zT, "POWERED operator atlas (raw, within-task z)")
    rows_r = atlas(zVr, zTr, "POWERED operator atlas (LENGTH-RESIDUALIZED)")

    print("\n=== coarse stage (draft/improve/debug) mean dVal/dTrue ===", flush=True)
    for s in sorted(set(e["stage"] for e in E)):
        m = np.array([e["stage"] == s for e in E])
        if m.sum() < 8:
            continue
        print(f"  {s:10s} n={int(m.sum()):>4}  meanDVal={zV[m].mean():+.3f}  meanDTrue={zT[m].mean():+.3f}", flush=True)

    ill = [k for k, c, x in rows_r if c == "ILLUSION"]
    gen = [k for k, c, x in rows_r if c == "genuine"]
    consist = [k for k, c, x in rows_r if x == "CONSIST"]
    print("\n=== VERDICT (length-residualized, powered) ===", flush=True)
    print(f"  illusion ops = {ill}", flush=True)
    print(f"  genuine ops  = {gen}", flush=True)
    print(f"  cross-agent-consistent ops = {consist}", flush=True)
    green = len(ill) >= 1 and len(gen) >= 1 and len(set(ill + gen) & set(consist)) >= 2
    print("  " + ("GREEN: operators cleanly + cross-agent-consistently split into genuine vs illusion "
                  "-> main line stands; build the atlas + design the intervention."
                  if green else
                  "NOT CLEAN: the genuine/illusion split is weak or agent-specific -> reassess the framing."), flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
