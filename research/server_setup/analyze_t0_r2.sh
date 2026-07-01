#!/usr/bin/env bash
# T0 go/no-go: parent->child TRUE-value (external pristine score) conditional correlation (R^2).
# Reads an aira-dojo run's journal.jsonl; for each parent->child edge where BOTH endpoints have an
# external score (metric_info["score"]), regress child_score ~ parent_score. R^2~0 => TD has no
# poolable structure (RED). R^2>0 => poolable (GREEN, proceed).
# Usage: bash analyze_t0_r2.sh <run_dir>
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
RUN="${1:-/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_deepseek_mcts_t0}"
J="$(ls -t "$RUN"/*/checkpoint/journal.jsonl 2>/dev/null | head -1)"
echo "JOURNAL=$J"
"$PY" - "$J" <<'PYEOF'
import json, sys
import numpy as np
nodes = {}
try:
    with open(sys.argv[1]) as f:
        for line in f:
            line = line.strip()
            if line:
                n = json.loads(line); nodes[n["step"]] = n
except Exception as e:
    print("read failed:", e); sys.exit(0)

def score(n):
    mi = n.get("metric_info") or {}
    s = mi.get("score") if isinstance(mi, dict) else None
    return float(s) if isinstance(s, (int, float)) else None

total = len(nodes)
nonbuggy = [s for s, n in nodes.items() if n.get("is_buggy") is False]
scored = [s for s, n in nodes.items() if score(n) is not None]
depth = {}
for s in sorted(nodes):
    ps = [p for p in (nodes[s].get("parents") or []) if p is not None]
    depth[s] = 0 if not ps else 1 + max(depth.get(p, 0) for p in ps)
print(f"total nodes={total} | non-buggy={len(nonbuggy)} | with external score={len(scored)} | max depth={max(depth.values()) if depth else 0}")

pairs = []
for s, n in nodes.items():
    cs = score(n)
    if cs is None:
        continue
    for p in (n.get("parents") or []):
        if not p:  # skip None / virtual root step 0
            continue
        pn = nodes.get(p)
        if pn is None:
            continue
        ps = score(pn)
        if ps is not None:
            pairs.append((ps, cs))

print(f"parent->child edges with BOTH external scores: {len(pairs)}")
if len(pairs) >= 3:
    x = np.array([a for a, _ in pairs]); y = np.array([b for _, b in pairs])
    if x.std() > 1e-12 and y.std() > 1e-12:
        r = float(np.corrcoef(x, y)[0, 1]); r2 = r * r
        print(f"Pearson r={r:.4f}  R^2={r2:.4f}  (n={len(pairs)})")
        print(f"parent: mean={x.mean():.4f} std={x.std():.4f} | child: mean={y.mean():.4f} std={y.std():.4f}")
        verdict = "GREEN (R^2>0 -> poolable structure -> proceed)" if r2 > 0.05 else "RED (R^2~0 -> TD has nothing to pool)"
        print("T0 VERDICT:", verdict, "[n small -> need more seeds for confidence]" if len(pairs) < 20 else "")
    else:
        print("zero variance in scores -> cannot compute R^2 (scores nearly constant)")
    print("pairs (parent,child):", [(round(a, 4), round(b, 4)) for a, b in pairs])
else:
    print("Too few working parent->child edges (need >=3) -> collect more steps/seeds.")

# Self-reported validation metric vs external pristine score (evaluation-noise / val<->test consistency)
print("=== per-node: self-reported validation metric vs external true score ===")
se = []
for s in sorted(nodes):
    n = nodes[s]
    ext = score(n)
    if ext is None:
        continue
    sm = n.get("metric")
    sm = float(sm) if isinstance(sm, (int, float)) else None
    print(f"  step={s:>2} self_val={sm} external_true={ext:.4f} gap={None if sm is None else round(sm-ext,4)}")
    if sm is not None:
        se.append((sm, ext))
if len(se) >= 3:
    a = np.array([p for p, _ in se]); b = np.array([q for _, q in se])
    if a.std() > 1e-12 and b.std() > 1e-12:
        rse = float(np.corrcoef(a, b)[0, 1])
        print(f"self-reported <-> external: Pearson r={rse:.4f}  R^2={rse*rse:.4f}  (n={len(se)})  meanGap={np.mean(a-b):.4f}")
        print("  -> low R^2 / large gap = noisy self-reported evaluation (the main-line problem to fix)")
PYEOF
echo "T0_R2_DONE"
