#!/usr/bin/env bash
# Read-only T1 matrix progress: queue, submitted/30, and per (task,arm) the search-selected solution's
# D_val truth per seed. Selected = argmax(node.metric=D_search fitness), or argmin for lower-is-better.
source ~/env_setup.sh
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_matrix_submitted.txt
echo "=== queue ($(squeue -u yzyang4 -h 2>/dev/null | wc -l)/4) ==="; squeue -u yzyang4
echo "submitted: $(wc -l < "$STATE" 2>/dev/null || echo 0)/30"
echo "=== daemon tail ==="; tail -n 3 /research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log 2>/dev/null
"$PY" - <<'PYEOF'
import json, glob, os
import numpy as np
base = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
TASKS = [("spaceship-titanic", "spaceship", False), ("nomad2018-predict-transparent-conductors", "nomad", True)]
ARMS = ["full", "naive", "consistency"]
print(f"\n{'task':10s}{'arm':12s}{'seeds':6s}selected-solution D_val truth (per seed)")
for task, short, lower in TASKS:
    for arm in ARMS:
        iss = f"t1_{arm}_{task}"
        jfs = sorted(glob.glob(os.path.join(base, f"user_yzyang4_issue_{iss}", "*", "checkpoint", "journal.jsonl")))
        sels = []
        for jf in jfs:
            nodes = [json.loads(l) for l in open(jf) if l.strip()]
            nb = [n for n in nodes if n.get("is_buggy") is False and isinstance(n.get("metric"), (int, float))]
            if not nb:
                continue
            best = min(nb, key=lambda n: n["metric"]) if lower else max(nb, key=lambda n: n["metric"])
            dv = (best.get("metric_info") or {}).get("dval_score")
            if isinstance(dv, (int, float)):
                sels.append(round(dv, 4))
        med = f"median={np.median(sels):.4f}" if sels else ""
        print(f"{short:10s}{arm:12s}{len(jfs):<6d}{med}  {sels}")
PYEOF
echo "=== clean-exit / health check (recent t1_hce .out) ==="
for f in $(ls -t /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_*.out 2>/dev/null | head -10); do
  rc=$(grep -oE "_DONE rc=[0-9]+" "$f" | tail -1)
  ff=$(grep -c "Final fitness" "$f" 2>/dev/null)
  ve=$(grep -c "This should not be reached" "$f" 2>/dev/null)
  to=$(grep -c "DUE TO TIME LIMIT" "$f" 2>/dev/null)
  echo "$(basename "$f"): ${rc:-<running>} | Final_fitness=$ff ValueError=$ve TIMEOUT=$to"
done
echo "T1_PROGRESS_DONE"
