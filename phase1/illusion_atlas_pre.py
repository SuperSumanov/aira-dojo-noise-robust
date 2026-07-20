"""Illusion-atlas PRE-CHECK on our 289 tree (quick, underpowered -> red-flag gate before the FOREAGENT pull).

Claim under test (pivot main line): on parent->child improve edges, do EDITS split into GENUINE (raise the
external true grade) vs ILLUSION (raise the self-reported validation but NOT the true grade)? hp_search is the
pre-identified illusion candidate (factor-gate: it inflates self-report, partial corr w/ true grade = -0.18).

Per graded improve-edge: dVal = child.val-parent.val (self-report), dTrue = child.y-parent.y (external),
dFactor = feats(child)-feats(parent). Within-task standardized so 3 comps pool fairly. For each factor's
ADDITION: mean dVal vs mean dTrue -> genuine / illusion / net-neg. Reuses stage_b_gate's edge-builder + a1.
289 gives ~42 edges -> READ DIRECTION ONLY; purpose = confirm plumbing + catch a red flag (e.g. dVal==dTrue,
no illusion to study) before pulling FOREAGENT agent_runs for the powered cross-agent version.
"""
import glob
import json
import os

import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _spear
from phase1.a1_mechanism import feats

RUNS = "/research/d7/spc/yzyang4/aira-dojo-runs"


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    names = list(feats(cards[0].code).keys())
    y_by_id = {c.id: c.y for c in cards}
    hib = {c.task.name: c.task.higher_is_better for c in cards}
    v_by_id = {}
    for c in cards:
        vv = c.obs.val_at_low
        if vv is not None:
            v_by_id[c.id] = vv if c.task.higher_is_better else -vv

    journals = sorted(set(glob.glob(os.path.join(RUNS, "**", "checkpoint", "journal.jsonl"), recursive=True)))
    edges = []
    for jp in journals:
        try:
            nodes = [json.loads(x) for x in open(jp)]
        except Exception:
            continue
        comp = None
        for n in nodes:
            comp = (n.get("metric_info") or {}).get("competition_id")
            if comp:
                break
        if comp is None or comp not in hib:
            continue
        by_step = {n.get("step"): n for n in nodes}
        for c in nodes:
            ops = [o.lower() for o in (c.get("operators_used") or [])]
            if "improve" not in ops:
                continue
            par = c.get("parents") or []
            if not par or par[0] not in by_step:
                continue
            p = by_step[par[0]]
            cid = f"{comp}__{c.get('id')}"; pid = f"{comp}__{p.get('id')}"
            if cid not in y_by_id or pid not in y_by_id or cid not in v_by_id or pid not in v_by_id:
                continue
            fc = feats(c.get("code") or ""); fp = feats(p.get("code") or "")
            edges.append(dict(comp=comp,
                              dTrue=y_by_id[cid] - y_by_id[pid],
                              dVal=v_by_id[cid] - v_by_id[pid],
                              df={k: fc[k] - fp[k] for k in names}))
    print(f"graded improve-edges = {len(edges)}", flush=True)
    if len(edges) < 10:
        print("too few edges; abort (plumbing or data issue)", flush=True)
        return

    comps = np.array([e["comp"] for e in edges])
    dT = np.array([e["dTrue"] for e in edges]); dV = np.array([e["dVal"] for e in edges])

    def zt(x):  # within-task standardize (comps differ in metric scale)
        out = np.zeros_like(x, float)
        for cc in np.unique(comps):
            m = comps == cc; s = x[m].std()
            out[m] = (x[m] - x[m].mean()) / (s if s > 1e-9 else 1.0)
        return out
    zT, zV = zt(dT), zt(dV)

    # ---- diagnostic: are dVal and dTrue DECOUPLED (room for illusion)? ----
    dec = _spear(zV, zT)
    print(f"\ncorr(dVal, dTrue) [within-task z] = {dec:+.3f}   (low => decoupled => room for illusion)", flush=True)
    print(f"edges: dVal>0 in {np.mean(dV > 0):.2f}   dTrue>0 in {np.mean(dT > 0):.2f}   per-comp n={dict(zip(*np.unique(comps, return_counts=True)))}", flush=True)
    up = dV > 0
    ill = (up & (dT <= 0)).sum(); gen = (up & (dT > 0)).sum()
    print(f"among dVal>0 (self-report rose): ILLUSION(dTrue<=0)={ill}  GENUINE(dTrue>0)={gen}", flush=True)

    # ---- operator atlas: among edges that ADDED factor, mean dVal vs mean dTrue ----
    print("\n=== operator atlas: edges that ADDED a factor -> mean dVal / mean dTrue (within-task z) ===", flush=True)
    print(f"  {'operator(+factor)':16s} {'n':>3} {'meanDVal':>9} {'meanDTrue':>10}  class", flush=True)
    hp_class = None
    genuine_ops, illusion_ops = [], []
    for k in ["hp_search", "ensemble", "cv", "leak_guard", "feat_eng", "reg", "nn", "xgb", "lgbm"]:
        add = np.array([e["df"][k] > 0 for e in edges])
        if add.sum() < 3:
            print(f"  {k:16s} {int(add.sum()):>3}  (too few)", flush=True)
            continue
        mv, mt = zV[add].mean(), zT[add].mean()
        cls = "ILLUSION" if (mv > 0.05 and mt <= 0.05) else ("genuine" if mt > 0.05 else ("net-neg" if mt < -0.05 else "flat"))
        if k == "hp_search":
            hp_class = cls
        if cls == "genuine":
            genuine_ops.append(k)
        if cls == "ILLUSION":
            illusion_ops.append(k)
        print(f"  {k:16s} {int(add.sum()):>3} {mv:>+9.3f} {mt:>+10.3f}  {cls}", flush=True)

    dlen = np.array([e["df"]["code_len"] for e in edges]); dfit = np.array([e["df"]["n_fits"] for e in edges])
    print(f"\n  complexity: corr(d code_len,dVal)={_spear(dlen, zV):+.3f}  corr(d code_len,dTrue)={_spear(dlen, zT):+.3f}", flush=True)
    print(f"  n_fits    : corr(d n_fits,  dVal)={_spear(dfit, zV):+.3f}  corr(d n_fits,  dTrue)={_spear(dfit, zT):+.3f}", flush=True)

    # ---- directional verdict ----
    print("\n=== VERDICT (directional only; 289 underpowered -> this is a RED-FLAG gate, not proof) ===", flush=True)
    decoupled = abs(dec) < 0.55
    print(f"  decoupled(dVal vs dTrue)? {decoupled} (corr={dec:+.3f})   hp_search class = {hp_class}", flush=True)
    print(f"  genuine ops = {genuine_ops or 'none seen'}   illusion ops = {illusion_ops or 'none seen'}", flush=True)
    if decoupled and (illusion_ops or hp_class == "ILLUSION") and genuine_ops:
        print("  -> DIRECTIONALLY PROMISING: dVal/dTrue decouple AND both an illusion op and a genuine op show up."
              " Worth pulling FOREAGENT agent_runs for the powered, cross-agent version.", flush=True)
    elif not decoupled:
        print("  -> RED FLAG: dVal and dTrue are near-collinear -> little 'illusion' to study. Rethink before pulling.", flush=True)
    else:
        print("  -> UNCLEAR at 289 (expected: underpowered). No red flag; the split just isn't resolvable here."
              " The FOREAGENT pull is what decides it -- proceed if no red flag above.", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
