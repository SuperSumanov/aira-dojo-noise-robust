"""Stage B -- generation-side offline gate.

Question: in the existing search trees, when an *improve* edit moves the code toward the A1 high-grade
direction (esp. the actionable factors: adding a leakage guard / simplifying), does the TRUE grade go up
-- AFTER controlling for the candidate's own self-report? If yes, steering generation toward those factors
has promise (-> Stage C online A/B). If not, generation side does not pay either (another honest negative,
no GPU spent).

We walk every improve edge (parent->child) across all journals, keep edges where BOTH ends are graded,
and for each compute: dGrade (true), dSelf (self-report), dH (move along the A1 checklist grade-direction),
dLeakGuard, dSimplicity. Gate = partial effect of the factor on dGrade controlling dSelf (bootstrap CI).
Refinement: also a within-parent (sibling improves) version to reduce the 'already on a good trajectory'
confound.
"""
import glob
import json
import os
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear
from phase1.a1_mechanism import feats

RUNS = "/research/d7/spc/yzyang4/aira-dojo-runs"


def _boot_ci(x, B=3000, seed=0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 5:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    bs = [np.mean(rng.choice(x, len(x), replace=True)) for _ in range(B)]
    return float(np.mean(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _partial_spear(a, b, c, B=3000, seed=0):
    """Partial Spearman of a,b controlling c: rank, residualize a and b on c, correlate; + bootstrap CI."""
    a = np.asarray(a, float); b = np.asarray(b, float); c = np.asarray(c, float)
    m = ~(np.isnan(a) | np.isnan(b) | np.isnan(c))
    a, b, c = a[m], b[m], c[m]
    if len(a) < 8:
        return float("nan"), float("nan"), float("nan"), len(a)

    def _pc(a, b, c):
        ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
        rc = np.argsort(np.argsort(c)).astype(float)
        C = np.column_stack([np.ones(len(rc)), rc])
        ea = ra - C @ np.linalg.lstsq(C, ra, rcond=None)[0]
        eb = rb - C @ np.linalg.lstsq(C, rb, rcond=None)[0]
        return 0.0 if ea.std() < 1e-9 or eb.std() < 1e-9 else float(np.corrcoef(ea, eb)[0, 1])
    pt = _pc(a, b, c)
    rng = np.random.default_rng(seed); n = len(a); bs = []
    for _ in range(B):
        idx = rng.choice(n, n, replace=True)
        bs.append(_pc(a[idx], b[idx], c[idx]))
    return pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), n


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    names = list(feats(cards[0].code).keys())
    H = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    mu = H.mean(0); sd = H.std(0); sd[sd < 1e-8] = 1.0
    w = np.linalg.solve(((H - mu) / sd).T @ ((H - mu) / sd) + 3.0 * np.eye(H.shape[1]),
                        ((H - mu) / sd).T @ _z(y))                    # A1 checklist -> grade direction

    def hscore(code):
        return float(((np.array([feats(code)[k] for k in names]) - mu) / sd) @ w)

    y_by_id = {c.id: c.y for c in cards}
    hib = {c.task.name: c.task.higher_is_better for c in cards}
    v_by_id = {}
    for c in cards:
        vv = c.obs.val_at_low
        if vv is not None:
            v_by_id[c.id] = vv if c.task.higher_is_better else -vv
    li = names.index("leak_guard"); nf = names.index("n_fits")

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
            cc = c.get("code") or ""; pc = p.get("code") or ""
            fc = feats(cc); fp = feats(pc)
            edges.append(dict(
                pid=pid,
                dGrade=y_by_id[cid] - y_by_id[pid],
                dSelf=v_by_id[cid] - v_by_id[pid],
                dH=hscore(cc) - hscore(pc),
                dLeak=fc["leak_guard"] - fp["leak_guard"],
                dSimpl=-(fc["n_fits"] - fp["n_fits"]),
            ))
    print(f"journals={len(journals)}  graded improve-edges={len(edges)}", flush=True)
    if len(edges) < 10:
        print("too few edges; abort", flush=True); return
    dG = np.array([e["dGrade"] for e in edges]); dS = np.array([e["dSelf"] for e in edges])
    dH = np.array([e["dH"] for e in edges]); dL = np.array([e["dLeak"] for e in edges])
    dSm = np.array([e["dSimpl"] for e in edges])
    print(f"  moved-toward-checklist>0: {np.mean(dH>0):.2f}   added-leak-guard: {np.mean(dL>0):.2f}   simplified: {np.mean(dSm>0):.2f}", flush=True)

    print("\n=== gate: partial Spearman( dGrade , factor | dSelf ), 95% bootstrap CI ===", flush=True)
    for label, fac in [("checklist direction dH", dH), ("added leak-guard dLeak", dL), ("simplified dSimpl", dSm)]:
        pt, lo, hi, n = _partial_spear(dG, fac, dS)
        verdict = "PASS (CI>0)" if lo > 0 else ("neg (CI<0)" if hi < 0 else "n.s.")
        print(f"  {label:26s} r={pt:+.3f} [{lo:+.3f},{hi:+.3f}] n={n}  -> {verdict}", flush=True)

    # context: does self-report itself predict dGrade? and raw (uncontrolled) factor corr?
    print("\n  context: corr(dSelf, dGrade)     =", f"{_spear(dS, dG):+.3f}", flush=True)
    print("  context: raw corr(dH, dGrade)      =", f"{_spear(dH, dG):+.3f}", flush=True)

    # sibling refinement: within-parent demeaning (parents with >=2 improve children)
    from collections import defaultdict
    grp = defaultdict(list)
    for i, e in enumerate(edges):
        grp[e["pid"]].append(i)
    sib = [i for g in grp.values() if len(g) >= 2 for i in g]
    if len(sib) >= 12:
        idx = np.array(sib)
        def demean(v):
            out = v[idx].copy().astype(float)
            for g in grp.values():
                if len(g) >= 2:
                    gi = np.array(g); out_pos = np.isin(idx, gi)
                    out[out_pos] -= out[out_pos].mean()
            return out
        print(f"\n=== sibling-controlled (within same parent, {len(sib)} edges from {sum(len(g)>=2 for g in grp.values())} parents) ===", flush=True)
        for label, fac in [("checklist dH", dH), ("leak-guard dLeak", dL), ("simplified dSimpl", dSm)]:
            pt, lo, hi, n = _partial_spear(demean(dG), demean(fac), demean(dS))
            verdict = "PASS" if lo > 0 else ("neg" if hi < 0 else "n.s.")
            print(f"  {label:20s} r={pt:+.3f} [{lo:+.3f},{hi:+.3f}] n={n} -> {verdict}", flush=True)
    else:
        print(f"\n(sibling set too small: {len(sib)} edges)", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
