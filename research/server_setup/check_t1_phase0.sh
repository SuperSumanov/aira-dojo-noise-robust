#!/usr/bin/env bash
# Validate the T1 HCE harness from the Phase 0 runs (3 arms x spaceship x seed 1).
source ~/env_setup.sh 2>/dev/null
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
echo "=== queue ==="; squeue -u yzyang4
echo "=== newest 3 t1_hce .out: did HCE eval fire? ==="
for f in $(ls -t /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_*.out 2>/dev/null | head -3); do
  echo "--- $f ---"
  echo "HCE_eval_fires=$(grep -c 'VALIDATION_FITNESS=' "$f" 2>/dev/null)"
  grep 'VALIDATION_FITNESS=' "$f" 2>/dev/null | tail -2
  tail -n 3 "$f"
done
"$PY" - <<'PYEOF'
import json, glob, os
base = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
for arm in ["full", "naive", "consistency"]:
    jfs = glob.glob(os.path.join(base, f"user_yzyang4_issue_t1_p0_{arm}*", "*", "checkpoint", "journal.jsonl"))
    print(f"\n===== ARM {arm} =====  journals={len(jfs)}")
    for jf in jfs:
        nodes = [json.loads(l) for l in open(jf) if l.strip()]
        nb = [n for n in nodes if n.get("is_buggy") is False]
        print(f"  nodes={len(nodes)} non-buggy={len(nb)}")
        for n in nb:
            mi = n.get("metric_info") or {}
            di = mi.get("dsearch_info") or {}
            chk = ""
            if arm == "consistency" and di.get("mean") is not None and di.get("std") is not None:
                exp = di["mean"] - di.get("lambda", 1.0) * di["std"]   # spaceship maximizes -> mean - lam*std
                chk = f" [check mean-lam*std={exp:.5f} vs metric={n.get('metric')}]"
            print(f"   step={n['step']} metric(Dsearch_fit)={n.get('metric')} arm={mi.get('arm')} "
                  f"raw={di.get('raw')} mean={di.get('mean')} std={di.get('std')} "
                  f"dval={mi.get('dval_score')} n_search={mi.get('n_search')} n_val={mi.get('n_val')}{chk}")
PYEOF
echo "T1_P0_CHECK_DONE"
