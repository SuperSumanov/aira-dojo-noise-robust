#!/usr/bin/env bash
# Summarize an aira-dojo run's journal.jsonl: per-node step/buggy/metric/operators, + best metric.
# Usage: bash extract_aira_journal.sh <run_dir-or-checkpoint-journal.jsonl>
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
ARG="${1:-}"
# Accept either a run dir or a direct journal.jsonl path
if [ -d "$ARG" ]; then
  J="$(ls -t "$ARG"/checkpoint/journal.jsonl "$ARG"/*/checkpoint/journal.jsonl 2>/dev/null | head -1)"
else
  J="$ARG"
fi
echo "JOURNAL=$J"
"$PY" - "$J" <<'PYEOF'
import json, sys
path = sys.argv[1]
nodes = []
try:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                nodes.append(json.loads(line))
except Exception as e:
    print("read failed:", e); sys.exit(0)
print("total nodes:", len(nodes))
good = [n for n in nodes if n.get("is_buggy") is False]
print("non-buggy nodes:", len(good))
metric_vals = [n.get("metric") for n in good if isinstance(n.get("metric"), (int, float))]
for n in nodes:
    m = n.get("metric")
    ops = n.get("operators_used") or []
    print(f"  step={n.get('step')} buggy={n.get('is_buggy')} metric={m} ops={ops} parents={n.get('parents')}")
    an = (n.get("analysis") or "").replace(chr(10), " ")
    if an:
        print("    analysis:", an[:300])
    to = n.get("term_out") or n.get("_term_out") or ""
    if isinstance(to, list):
        to = "".join(map(str, to))
    to = (to or "").replace(chr(10), " ")
    if to:
        print("    term_out tail:", to[-500:])
if metric_vals:
    mx = n.get("metric_maximize", True)
    best = max(metric_vals) if mx else min(metric_vals)
    print(f"BEST non-buggy metric: {best} (maximize={mx})")
else:
    print("BEST non-buggy metric: NONE (no non-buggy node with a numeric metric)")
PYEOF
echo "EXTRACT_AIRA_DONE"
