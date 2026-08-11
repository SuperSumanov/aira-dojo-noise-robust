"""The last open cell: does anything read POTENTIAL (K>=1) that cannot read PRESENT (K=0)?

K=0 is settled -- every decision-time predictor is at chance when ranking siblings by their
current quality. The K=1/2 sets ask the search-relevant variant the senior flagged as the
novel one: which sibling's next-K-step subtree reaches further. The earlier decision-point
analysis left exactly one cell alive (RM at K>=1), on the old conflicted pair file; these are
the clean per-budget sets, scored with the same frozen models.

The interesting outcome is a DISSOCIATION: a predictor at chance at K=0 but above it at
K>=1 reads improvement potential rather than present quality. The decisive comparison is
against self_report, which sees only the child's current val -- if critics beat self_report
at K>=1 specifically, potential is in the CODE, not in the score.

Ceiling note: K>=1 labels are subtree maxima, so the own-score ceiling is an upper bound
here (same caveat as lookahead pairs), exact only on pairs whose gap_raw equals the own
|graded| difference.
"""
import collections, json, math, random

ORI = json.load(open("phase1/task_orientation.json"))
PP = json.load(open("phase1/perpair_decision.json"))
G, OWN = {}, {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    try:
        v = float(d["label"].get("graded"))
        G[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        G[d["id"]] = None
    try:
        w = float(d["obs"].get("val_at_low"))
        OWN[d["id"]] = w if math.isfinite(w) else None
    except (TypeError, ValueError):
        OWN[d["id"]] = None


def sr_hit(p):
    a, b = OWN.get(p["better"]), OWN.get(p["worse"])
    if a is None or b is None or a == b:
        return None
    return int((a < b) if ORI.get(p["task"], False) else (a > b))


def boot(d, nb=4000, seed=7):
    ks = list(d)
    if not ks:
        return float("nan"), float("nan")
    rr = random.Random(seed)
    o = []
    for _ in range(nb):
        v = [x for k in (rr.choice(ks) for _ in ks) for x in d[k]]
        o.append(sum(v) / len(v))
    o.sort()
    return o[int(.025 * nb)], o[int(.975 * nb)]


NAMES = ["rm_1.5b_2048_SIBSUBSET", "tfidf_lr", "static_gbm", "static_lr",
         "embed_frozen_0.5b", "code_len", "n_lines", "n_ensemble", "random"]

print(f"{'set':>4} {'n':>5} {'exact-lab':>9}  predictor rows: acc [parent CI]  "
      f"(* = CI excludes 0.5)")
summary = collections.defaultdict(dict)
for K in (0, 1, 2):
    rows = []
    for l in open(f"phase1/decision_clean_b{K}.jsonl"):
        p = json.loads(l)
        gb, gw = G.get(p["better"]), G.get(p["worse"])
        exact = (gb is not None and gw is not None
                 and abs(abs(gb - gw) - float(p["gap_raw"])) < 1e-6)
        rows.append({**p, "key": p["better"] + "|" + p["worse"], "exact": exact})
    ex = sum(r["exact"] for r in rows)
    print(f"\n=== K={K}: {len(rows)} pairs, {ex} ({ex/max(len(rows),1):.0%}) "
          f"own-score-exact labels ===")
    for name in ["self_report"] + NAMES:
        d_p = collections.defaultdict(list)
        for r in rows:
            x = sr_hit(r) if name == "self_report" else PP.get(name, {}).get(r["key"])
            if x is None:
                continue
            d_p[r["parent"]].append(float(x))
        v = [x for vs in d_p.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_p)
        acc = sum(v) / len(v)
        summary[name][K] = (acc, lo, hi, len(v))
        star = " *" if (lo > 0.5 or hi < 0.5) else ""
        print(f"   {name:24s} {acc:.4f} [{lo:.4f},{hi:.4f}] n={len(v)}{star}")

print("\n=== DISSOCIATION TABLE: K=0 vs K>=1 (acc, parent CI) ===")
print(f"{'predictor':24s} {'K=0':>22} {'K=1':>22} {'K=2':>22}  verdict")
for name in ["self_report"] + NAMES:
    cells = []
    for K in (0, 1, 2):
        if K in summary[name]:
            a, lo, hi, n = summary[name][K]
            cells.append(f"{a:.3f}[{lo:.3f},{hi:.3f}]")
        else:
            cells.append("--")
    v0 = summary[name].get(0)
    v1 = summary[name].get(1)
    verdict = ""
    if v0 and v1:
        chance0 = v0[1] <= 0.5 <= v0[2]
        above1 = v1[1] > 0.5
        if chance0 and above1:
            verdict = "<-- reads potential, not present"
        elif (not chance0) and above1:
            verdict = "works at both"
    print(f"{name:24s} {cells[0]:>22} {cells[1]:>22} {cells[2]:>22}  {verdict}")
