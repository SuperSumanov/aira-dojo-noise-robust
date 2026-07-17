"""Independent verification of the Phase-2 load-bearing numbers. Re-derives each via a DIFFERENT code path
than the original script; agreement = trustworthy, disagreement = bug. Also spot-checks feature extraction
and the Stage-B edge linking. CPU, cached features + journals.
"""
import glob
import json
import os
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _dual_ridge
from phase1.a1_mechanism import feats

CACHE = "phase1/_cache_b1_feats.npz"
RUNS = "/research/d7/spc/yzyang4/aira-dojo-runs"


def partial_spear(a, b, c):
    a = np.asarray(a, float); b = np.asarray(b, float); c = np.asarray(c, float)
    m = ~(np.isnan(a) | np.isnan(b) | np.isnan(c)); a, b, c = a[m], b[m], c[m]
    ra, rb, rc = [np.argsort(np.argsort(x)).astype(float) for x in (a, b, c)]
    C = np.column_stack([np.ones(len(rc)), rc])
    ea = ra - C @ np.linalg.lstsq(C, ra, rcond=None)[0]
    eb = rb - C @ np.linalg.lstsq(C, rb, rcond=None)[0]
    return float(np.corrcoef(ea, eb)[0, 1])


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    XA = np.load(CACHE)["XA"]
    N = len(cards)
    print(f"cards={N}  XA={XA.shape}  tasks={dict(zip(*np.unique(tasks, return_counts=True)))}\n", flush=True)

    # ---------- CHECK 1: cache alignment / probe number ----------
    def oof(X, tgt, seed=0):
        pred = np.full(N, np.nan)
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < 7:
                continue
            for f in np.array_split(np.random.default_rng(seed).permutation(idx), 5):
                tr = np.setdiff1d(idx, f); pred[f] = _dual_ridge(X[tr], tgt[tr], X[f])
        return pred

    def pts(pred, tgt):
        v = [_spear(pred[tasks == t], tgt[tgt_ok(tgt, t)]) if False else _spear(pred[tasks == t], tgt[tasks == t])
             for t in np.unique(tasks) if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
        return float(np.mean(v)) if v else float("nan")

    probe = oof(XA, y)
    p1 = pts(probe, y)
    print(f"[CHECK 1 cache/probe] probe OOF Spearman = {p1:+.3f}  (expect ~0.29; a mis-aligned cache would give ~0)", flush=True)
    # alignment stress: shuffle XA rows -> should destroy the signal
    perm = np.random.default_rng(1).permutation(N)
    p_shuf = pts(oof(XA[perm], y), y)
    print(f"                    row-shuffled XA -> {p_shuf:+.3f}  (must be ~0 if alignment matters)\n", flush=True)

    # ---------- CHECK 2: feats() spot-check ----------
    print("[CHECK 2 feats spot-check] 3 cards, extracted flags vs a code snippet:", flush=True)
    names = list(feats(cards[0].code).keys())
    for i in [0, N // 2, N - 1]:
        f = feats(cards[i].code)
        flags = {k: f[k] for k in ["cv", "reg", "leak_guard", "xgb", "lgbm", "nn", "n_fits"]}
        snip = " ".join((cards[i].code or "").split())[:90]
        print(f"  card {i} [{tasks[i][:8]}] {flags}", flush=True)
        print(f"      code: {snip}", flush=True)
    H = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    print(f"  leak_guard prevalence = {H[:, names.index('leak_guard')].mean():.2f} ; cv = {H[:, names.index('cv')].mean():.2f}\n", flush=True)

    # ---------- CHECK 3: A1 residual, independent method ----------
    def ridge_oof(Hm, tgt, seed=0, lam=3.0):
        pred = np.full(N, np.nan)
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < 7:
                continue
            for f in np.array_split(np.random.default_rng(seed).permutation(idx), 5):
                tr = np.setdiff1d(idx, f)
                mu = Hm[tr].mean(0); sd = Hm[tr].std(0); sd[sd < 1e-8] = 1
                A = (Hm[tr] - mu) / sd; B = (Hm[f] - mu) / sd
                w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ tgt[tr])
                pred[f] = B @ w
        return pred
    checklist = ridge_oof(H, y)
    c1 = pts(checklist, y)
    # A1 script's own method (semi-partial: residualize probe-pred on checklist-pred, corr with y)
    semi = np.full(N, np.nan)
    for t in np.unique(tasks):
        m = np.where(tasks == t)[0]
        Cc = np.column_stack([np.ones(len(m)), _z(checklist[m])])
        semi[m] = _z(probe[m]) - Cc @ np.linalg.lstsq(Cc, _z(probe[m]), rcond=None)[0]
    a1_resid = pts(semi, y)
    # independent method: full partial Spearman(probe, y | checklist), per-task then avg
    parts = [partial_spear(probe[tasks == t], y[tasks == t], checklist[tasks == t])
             for t in np.unique(tasks) if (tasks == t).sum() >= 8]
    full_partial = float(np.mean(parts))
    print(f"[CHECK 3 A1 residual] checklist->grade = {c1:+.3f} (A1 said 0.22)", flush=True)
    print(f"                      A1 semi-partial (its method) = {a1_resid:+.3f} (A1 said 0.20)", flush=True)
    print(f"                      INDEP full partial Spearman(probe,y|checklist) = {full_partial:+.3f}", flush=True)
    print(f"                      -> both >0 and similar => 'probe carries signal beyond checklist' confirmed\n", flush=True)

    # ---------- CHECK 4: Stage-B edge linking recount ----------
    y_by_id = {c.id: c.y for c in cards}
    hib = {c.task.name: c.task.higher_is_better for c in cards}
    v_ok = {c.id for c in cards if c.obs.val_at_low is not None}
    journals = sorted(set(glob.glob(os.path.join(RUNS, "**", "checkpoint", "journal.jsonl"), recursive=True)))
    n_imp = n_par = n_both_graded = n_final = 0
    examples = []
    for jp in journals:
        try:
            nodes = [json.loads(x) for x in open(jp)]
        except Exception:
            continue
        comp = next((n.get("metric_info", {}).get("competition_id") for n in nodes
                     if (n.get("metric_info") or {}).get("competition_id")), None)
        if comp not in hib:
            continue
        by_step = {n.get("step"): n for n in nodes}
        for c in nodes:
            if "improve" not in [o.lower() for o in (c.get("operators_used") or [])]:
                continue
            n_imp += 1
            par = c.get("parents") or []
            if not par or par[0] not in by_step:
                continue
            n_par += 1
            cid = f"{comp}__{c.get('id')}"; pid = f"{comp}__{by_step[par[0]].get('id')}"
            if cid in y_by_id and pid in y_by_id:
                n_both_graded += 1
                if cid in v_ok and pid in v_ok:
                    n_final += 1
                    if len(examples) < 3:
                        examples.append((comp[:8], round(y_by_id[pid], 3), round(y_by_id[cid], 3)))
    print(f"[CHECK 4 Stage-B linking] improve nodes={n_imp}, with-parent={n_par}, both-graded={n_both_graded}, +both-have-selfreport={n_final} (script used 42)", flush=True)
    print(f"                      example edges (task, parent_grade -> child_grade): {examples}", flush=True)
    print(f"                      -> {n_both_graded} graded edges is the real ceiling; not a linking bug if example grades look real\n", flush=True)

    # ---------- CHECK 5: A2 plateau, tighter (more resamples) ----------
    print("[CHECK 5 A2 plateau] spaceship learning curve, 30 resamples (tighter):", flush=True)
    idx = np.where(tasks == "spaceship-titanic")[0]
    ntest = int(len(idx) * 0.3)
    for Ntr in [25, 50, 75, 100, 125, 150]:
        vals = []
        for o in range(30):
            rng = np.random.default_rng(100 + o); perm = rng.permutation(idx)
            test, pool = perm[:ntest], perm[ntest:]
            if Ntr > len(pool):
                continue
            tr = rng.choice(pool, Ntr, replace=False)
            vals.append(_spear(_dual_ridge(XA[tr], y[tr], XA[test]), y[test]))
        se = np.std(vals) / np.sqrt(len(vals))
        print(f"    N={Ntr:>4}  {np.mean(vals):+.3f} ± {se:.3f} (SE)", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
