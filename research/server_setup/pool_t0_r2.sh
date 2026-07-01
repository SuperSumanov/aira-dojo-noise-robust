#!/usr/bin/env bash
# Pool T0 signals across ALL seed runs under a git_issue_id:
#  - RL line: parent->child external-true-value correlation (R^2) — does parent value predict child's?
#  - main line: self-reported validation <-> external true score consistency (the eval-noise signal).
# Usage: bash pool_t0_r2.sh [issue_dir]
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
ISSUE="${1:-/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_deepseek_mcts_t0}"
"$PY" - "$ISSUE" <<'PYEOF'
import json, sys, glob, os
import numpy as np
issue = sys.argv[1]
jfiles = sorted(glob.glob(os.path.join(issue, "*", "checkpoint", "journal.jsonl")))
print(f"seed journals found: {len(jfiles)}")
def score(n):
    mi = n.get("metric_info") or {}
    s = mi.get("score") if isinstance(mi, dict) else None
    return float(s) if isinstance(s, (int, float)) else None
all_pairs, all_se = [], []
tot_nodes = tot_nb = tot_scored = 0
for jf in jfiles:
    nodes = {}
    with open(jf) as f:
        for line in f:
            line = line.strip()
            if line:
                n = json.loads(line); nodes[n["step"]] = n
    tot_nodes += len(nodes)
    tot_nb += sum(1 for n in nodes.values() if n.get("is_buggy") is False)
    tot_scored += sum(1 for n in nodes.values() if score(n) is not None)
    for s, n in nodes.items():
        cs = score(n)
        if cs is None:
            continue
        sm = n.get("metric"); sm = float(sm) if isinstance(sm, (int, float)) else None
        if sm is not None:
            all_se.append((sm, cs))
        for p in (n.get("parents") or []):
            if not p:
                continue
            pn = nodes.get(p)
            if pn is not None and score(pn) is not None:
                all_pairs.append((score(pn), cs))
print(f"pooled: nodes={tot_nodes} non-buggy={tot_nb} scored={tot_scored}")
def rep(pairs, label):
    if len(pairs) < 3:
        print(f"{label}: n={len(pairs)} (too few)"); return
    x = np.array([a for a, _ in pairs]); y = np.array([b for _, b in pairs])
    if x.std() < 1e-12 or y.std() < 1e-12:
        print(f"{label}: n={len(pairs)} zero-variance"); return
    r = float(np.corrcoef(x, y)[0, 1])
    print(f"{label}: r={r:+.4f}  R^2={r*r:.4f}  n={len(pairs)}")
print("--- RL line: parent->child external-true-value ---")
rep(all_pairs, "parent->child")
print("  RL pairs (parent,child):", sorted([(round(a, 3), round(b, 3)) for a, b in all_pairs]))
if len(all_pairs) >= 4:
    xx = np.array([a for a, _ in all_pairs]); yy = np.array([b for _, b in all_pairs])
    loo = []
    for i in range(len(all_pairs)):
        m = np.ones(len(all_pairs), bool); m[i] = False
        if xx[m].std() > 1e-12 and yy[m].std() > 1e-12:
            loo.append(float(np.corrcoef(xx[m], yy[m])[0, 1]) ** 2)
    print(f"  RL R^2 leave-one-out range: [{min(loo):.3f}, {max(loo):.3f}] (if min collapses, a single point drives it)")
print("--- main line: self-reported validation <-> external true ---")
rep(all_se, "self<->external")
if all_se:
    g = np.array([a - b for a, b in all_se])
    print(f"self-external gap: mean={g.mean():+.4f}  #|gap|>0.1: {int((np.abs(g)>0.1).sum())}/{len(g)}")
echo_done = "POOL_DONE"
print(echo_done)
PYEOF
echo "POOL_T0_DONE"
