#!/usr/bin/env bash
# Dump per-node summary (stage, buggy, metric, analysis, term_out tail) from a run's journal.json.
# Usage: bash extract_journal.sh <run_dir>
RUN="${1:-/research/d7/spc/yzyang4/MLEvolve/runs}"
PY=/research/d7/spc/yzyang4/venvs/exp/bin/python
JOURNAL="$RUN/logs/journal.json"
echo "JOURNAL=$JOURNAL"
"$PY" - "$JOURNAL" <<'PYEOF'
import json, sys
j = json.load(open(sys.argv[1]))
nodes = j.get("nodes", [])
print("total nodes:", len(nodes))
for n in nodes:
    nid = (n.get("id") or "")[:8]
    metric = (n.get("metric") or {})
    mv = metric.get("value") if isinstance(metric, dict) else None
    print("="*70)
    print(f"node {nid} stage={n.get('stage')} parent={(n.get('parent') or {}).get('id','-') if isinstance(n.get('parent'),dict) else n.get('parent')} buggy={n.get('is_buggy')} metric={mv}")
    an = (n.get("analysis") or "")
    if an:
        print("ANALYSIS:", an[:500])
    to = n.get("_term_out")
    if to:
        s = to if isinstance(to, str) else "".join(map(str, to))
        print("TERM_OUT_TAIL:", s[-800:])
PYEOF
echo "EXTRACT_DONE"
