#!/usr/bin/env bash
# Proper T1 analysis per (task, arm): n runs, n working, selected-solution D_val (median + values),
# selection REGRET (= how much worse the search-picked node is than the truly-best node in its tree,
# by D_val), and the proxy->truth gap of the selected node. Regret is the cleanest test of whether
# the eval protocol selects well.
source ~/env_setup.sh
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
"$PY" - <<'PYEOF'
import json, glob, os
import numpy as np
base = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
TASKS = [("spaceship-titanic", "spaceship", False, ["full", "naive", "consistency", "mean"]),
         ("nomad2018-predict-transparent-conductors", "nomad", True, ["full", "naive", "consistency"])]
def dval(n):
    v = (n.get("metric_info") or {}).get("dval_score")
    return v if isinstance(v, (int, float)) else None
def med(x):
    return f"{np.median(x):.4f}" if x else "—"
for task, short, lower, arms in TASKS:
    print(f"\n######## {short}  (lower_is_better={lower}) ########")
    print(f"{'arm':12s}{'nrun':5s}{'nwk':4s}{'sel_dval':10s}{'regret':9s}{'gap':9s} sel_dval values")
    for arm in arms:
        iss = f"t1_{arm}_{task}"
        jfs = sorted(glob.glob(os.path.join(base, f"user_yzyang4_issue_{iss}", "*", "checkpoint", "journal.jsonl")))
        sds, regs, gaps, nwk = [], [], [], 0
        for jf in jfs:
            nodes = [json.loads(l) for l in open(jf) if l.strip()]
            w = [n for n in nodes if n.get("is_buggy") is False and isinstance(n.get("metric"), (int, float))]
            wv = [n for n in w if dval(n) is not None]
            if not wv:
                continue
            nwk += 1
            sel = min(w, key=lambda n: n["metric"]) if lower else max(w, key=lambda n: n["metric"])
            sd = dval(sel)
            if sd is None:
                continue
            orc = min(wv, key=lambda n: dval(n)) if lower else max(wv, key=lambda n: dval(n))
            od = dval(orc)
            reg = (sd - od) if lower else (od - sd)   # >=0: regret vs best-by-truth in same tree
            gap = sel["metric"] - sd                   # selected proxy fitness minus its truth
            sds.append(sd); regs.append(reg); gaps.append(gap)
        print(f"{arm:12s}{len(jfs):<5d}{nwk:<4d}{med(sds):10s}{med(regs):9s}{med(gaps):9s} {[round(v,3) for v in sds]}")
PYEOF
echo "T1_ANALYZE_DONE"
