#!/usr/bin/env bash
# Offline lambda sweep on the consistency-arm spaceship trees (k=3 raw proxies logged per node).
# Re-select the FINAL node by argmax(mean - lambda*std) for several lambda, report its D_val.
# lambda=0 == pure mean-of-3 (the "averaging only, no variance penalty" ablation).
# Caveat: trajectory was generated at lambda=1; this only varies the final pick, not the search path.
source ~/env_setup.sh
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
"$PY" - <<'PYEOF'
import json, glob, os
import numpy as np
base = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
jfs = sorted(glob.glob(os.path.join(base, "user_yzyang4_issue_t1_consistency_spaceship-titanic", "*", "checkpoint", "journal.jsonl")))
lams = [0.0, 0.5, 1.0, 2.0, 3.0]
per = {l: [] for l in lams}
for jf in jfs:
    nodes = [json.loads(l) for l in open(jf) if l.strip()]
    cand = []
    for n in nodes:
        if n.get("is_buggy") is not False:
            continue
        mi = n.get("metric_info") or {}
        di = mi.get("dsearch_info") or {}
        raw = di.get("raw"); dv = mi.get("dval_score")
        if isinstance(raw, list) and raw and isinstance(dv, (int, float)):
            cand.append((float(np.mean(raw)), float(np.std(raw)), float(dv)))
    if not cand:
        continue
    for l in lams:
        best = max(cand, key=lambda c: c[0] - l * c[1])   # spaceship maximizes
        per[l].append(best[2])
print(f"consistency-arm spaceship trees: {len(jfs)} journals")
print("(reference: naive median dval=0.784, full median dval=0.803)")
for l in lams:
    v = per[l]
    if v:
        print(f"lambda={l}: median={np.median(v):.4f} mean={np.mean(v):.4f} n={len(v)} vals={[round(x,3) for x in v]}")
PYEOF
echo "T1_LAMBDA_DONE"
