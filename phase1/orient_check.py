"""Verify the -0.59 dVal~dTrue: is it a real 'validation illusion' or an orientation artifact?
Reparse cache; per node compute oriented (val_LEVEL, true_LEVEL). If per-task corr(val_level,true_level)>0
but corr(dVal,dTrue)<0 -> real overfitting/regression signature. If level-corr<0 -> orientation flipped.
"""
import os
import re
import json
import glob

import numpy as np

ROOT = "/research/d7/spc/yzyang4/foreagent_agentruns"
NUM = re.compile(r"[-+]?\d*\.?\d+")


def pf(s):
    if not s:
        return None
    m = NUM.findall(str(s))
    return float(m[-1]) if m else None


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) < 8:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() < 1e-9 or rb.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


nodes_rec, edges_rec, samples = [], [], []
for run in sorted(glob.glob(os.path.join(ROOT, "agent_runs", "*", "*"))):
    if run.split(os.sep)[-2].startswith("__"):
        continue
    jp = os.path.join(run, "logs", "journal.json")
    if not os.path.exists(jp):
        continue
    try:
        J = json.load(open(jp))
    except Exception:
        continue
    nodes = J.get("nodes") if isinstance(J, dict) else J
    n2p = J.get("node2parent", {}) if isinstance(J, dict) else {}
    if not nodes:
        continue
    evl = {}; task = None
    for ef in glob.glob(os.path.join(run, "logs", "all_nodes", "*", "eval_output.json")):
        short = os.path.basename(os.path.dirname(ef)).replace("node_", "")
        try:
            ev = json.load(open(ef))
        except Exception:
            continue
        sc = ev.get("score")
        if sc is None or not ev.get("valid_submission", False):
            continue
        evl[short] = (float(sc), bool(ev.get("is_lower_better", False)))
        task = ev.get("competition_id", task)
    if not evl or task is None:
        continue
    byid = {str(n.get("id")): n for n in nodes}
    for n in nodes:
        if n.get("is_buggy"):
            continue
        nid = str(n.get("id"))
        cs = evl.get(nid[:8]); cv = pf(n.get("metric"))
        if cs is None or cv is None:
            continue
        true = -cs[0] if cs[1] else cs[0]
        val = -cv if ("↓" in str(n.get("metric"))) else cv
        nodes_rec.append((task, val, true))
        if len(samples) < 8:
            samples.append((task[:22], str(n.get("metric"))[:26], round(cs[0], 4), cs[1]))
        par = n.get("parent") or n2p.get(nid)
        p = byid.get(str(par))
        if p is None:
            continue
        ps = evl.get(str(p.get("id"))[:8]); pv = pf(p.get("metric"))
        if ps is None or pv is None:
            continue
        ptrue = -ps[0] if ps[1] else ps[0]
        pval = -pv if ("↓" in str(p.get("metric"))) else pv
        edges_rec.append((task, val - pval, true - ptrue))

print("sample (task, metric_str, raw_score, is_lower_better):", flush=True)
for s in samples:
    print("  ", s, flush=True)
print("\nper-task:  n_nodes  corr(val_LEVEL,true_LEVEL)  |  n_edges  corr(dVal,dTrue)", flush=True)
for t in sorted(set(r[0] for r in nodes_rec)):
    nl = [(v, tr) for (tk, v, tr) in nodes_rec if tk == t]
    el = [(dv, dt) for (tk, dv, dt) in edges_rec if tk == t]
    lv = spear([a for a, _ in nl], [b for _, b in nl])
    de = spear([a for a, _ in el], [b for _, b in el])
    print(f"  {t[:34]:34s} n={len(nl):>4} levelcorr={lv:+.3f} | edges={len(el):>4} deltacorr={de:+.3f}", flush=True)
print("\nINTERPRET: levelcorr>0 & deltacorr<0 => REAL illusion/overfit dynamics; levelcorr<0 => orientation flipped.", flush=True)
print("=== done ===", flush=True)
