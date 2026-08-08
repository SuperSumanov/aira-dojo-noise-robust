"""The load-bearing premise test, before any GPU is spent.

Two things must hold for "predict when the self-report is misleading" to be a real target:

P1  The orthogonal signal must survive RUN clustering. On the 444 pairs the self-report gets
    wrong, the code-only RM scored 0.559 -- but that CI treated pairs as independent, and we
    have already been burned once (the flip-set CI spanned 0.5 the moment it was clustered).
    Bootstrap over runs.

P2  The gap must be a PROGRAM property, not best-of-k winner's curse. Taking the argmax of k
    noisy self-reports inflates the winner by an amount that grows with k and is not written
    anywhere in the code. Critically, the within/between-task variance ratio CANNOT tell these
    apart, because selection noise is within-task too. Tests:
      (a) does |gap| grow with sibling count, and specifically for the sibling-best node?
      (b) after residualising |gap| on sibling count and within-sibling rank, does ANY code
          feature retain partial correlation?
    If (a) is strong and (b) is empty, the target is mostly not code-determined and both
    directions die here, for free.

Usage: python phase1/premise_test.py [cards.jsonl]
"""
import collections, json, math, random, statistics, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current_v7.jsonl"
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open(PATH):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def sr_of(d):
    return fin(d["obs"].get("val_at_low"))


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        m = (i + j) / 2.0
        for k in range(i, j + 1):
            r[o[k]] = m
        i = j + 1
    return r


def spearman(xs, ys):
    a, b = rank(xs), rank(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def partial(x, y, ctrls):
    """rho(x,y | ctrls) by iterative rank residualisation -- crude but adequate here."""
    rx, ry = rank(x), rank(y)
    for c in ctrls:
        rc = rank(c)
        n = len(rc)
        mc = sum(rc) / n
        vc = sum((v - mc) ** 2 for v in rc) or 1e-12
        for tgt in (rx, ry):
            mt = sum(tgt) / n
            cov = sum((a - mc) * (b - mt) for a, b in zip(rc, tgt))
            beta = cov / vc
            for i in range(n):
                tgt[i] -= beta * (rc[i] - mc)
    return spearman(rx, ry)


print("=" * 78)
print("P1 -- does the orthogonal signal survive RUN clustering?")
print("=" * 78)
rows = []
for l in open("phase1/hits_l1_runsplit.jsonl"):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    sb, sw = sr_of(cards[b]), sr_of(cards[w])
    if sb is None or sw is None or sb == sw:
        continue
    lower = ORI.get(h["task"], False)
    s_ok = int((sb < sw) if lower else (sb > sw))
    rows.append({"rm": h["hit"], "sr": s_ok, "run": RUN.get(b), "task": h["task"]})
wrong = [r for r in rows if r["sr"] == 0]
k, n = sum(r["rm"] for r in wrong), len(wrong)
print(f"pairs the self-report gets wrong: {n}, RM correct {k} = {k/n:.4f}")


def boot(sub, nboot=4000, seed=7):
    by = collections.defaultdict(list)
    for r in sub:
        by[r["run"]].append(r["rm"])
    runs = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(nboot):
        vals = [v for x in (rng.choice(runs) for _ in runs) for v in by[x]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(0.025 * nboot)], out[int(0.975 * nboot)], len(runs)


lo, hi, nr = boot(wrong)
print(f"  run-clustered 95% CI: [{lo:.4f}, {hi:.4f}]  ({nr} runs)")
print(f"  P1 VERDICT: {'SURVIVES' if lo > 0.5 else 'FAILS'}")
byt = collections.defaultdict(lambda: [0, 0])
for r in wrong:
    byt[r["task"]][0] += r["rm"]
    byt[r["task"]][1] += 1
print("  per task:", {t[:18]: f"{a}/{b}={a/b:.2f}" for t, (a, b) in
                      sorted(byt.items(), key=lambda kv: -kv[1][1])[:6]})

print()
print("=" * 78)
print("P2 -- winner's curse, or a program property?")
print("=" * 78)
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)

recs = []
for t in {d["task"]["name"] for d in cards.values()}:
    sub = [(c, d) for c, d in cards.items() if d["task"]["name"] == t]
    pack = [(c, sr_of(d), fin(d["label"].get("graded"))) for c, d in sub]
    pack = [(c, s, g) for c, s, g in pack if s is not None and g is not None]
    if len(pack) < 80:
        continue
    sgn = -1.0 if ORI.get(t, False) else 1.0
    ss = [sgn * s for _, s, _ in pack]
    gg = [sgn * g for _, _, g in pack]
    ms, ds = statistics.mean(ss), statistics.pstdev(ss) or 1.0
    mg, dg = statistics.mean(gg), statistics.pstdev(gg) or 1.0
    for (c, _, _), s, g in zip(pack, ss, gg):
        zs, zg = (s - ms) / ds, (g - mg) / dg
        d = cards[c]
        p = d["lineage"].get("parent_id")
        sibs = [x for x in kids.get(p, []) if x in cards] if p else []
        sib_sr = [(x, sr_of(cards[x])) for x in sibs]
        sib_sr = [(x, v) for x, v in sib_sr if v is not None]
        k_sib = len(sib_sr)
        if k_sib:
            order = sorted(sib_sr, key=lambda kv: -sgn * kv[1])
            my_rank = [x for x, _ in order].index(c) if c in [x for x, _ in order] else -1
            is_best = int(my_rank == 0)
        else:
            my_rank, is_best = -1, 0
        recs.append({
            "task": t, "gap": abs(zs - zg), "signed": zg - zs, "zs": zs,
            "k_sib": float(k_sib), "is_best": float(is_best),
            "rank": float(my_rank if my_rank >= 0 else 0),
            "code_len": float(len(d.get("code") or "")),
            "n_cv": float((d.get("code") or "").lower().count("kfold")
                          + (d.get("code") or "").lower().count("cross_val")),
            "runtime": float(d["obs"].get("runtime_s") or 0),
        })
print(f"nodes with both scores: {len(recs)}")

# (a) winner's curse signature: sibling-best nodes should be inflated (signed gap negative
#     means the true grade is worse than the self-report suggests, after z-scoring)
best = [r for r in recs if r["is_best"] == 1 and r["k_sib"] >= 2]
rest = [r for r in recs if r["is_best"] == 0 and r["k_sib"] >= 2]
if best and rest:
    print(f"\n(a) sibling-best nodes  n={len(best)}: mean signed (true - reported) z "
          f"= {statistics.mean([r['signed'] for r in best]):+.3f}, "
          f"|gap| = {statistics.mean([r['gap'] for r in best]):.3f}")
    print(f"    non-best siblings   n={len(rest)}: mean signed "
          f"= {statistics.mean([r['signed'] for r in rest]):+.3f}, "
          f"|gap| = {statistics.mean([r['gap'] for r in rest]):.3f}")
    r_k = spearman([r["k_sib"] for r in recs], [r["gap"] for r in recs])
    print(f"    rho(sibling count, |gap|) = {r_k:+.3f}")
    r_kb = spearman([r["k_sib"] for r in best], [r["gap"] for r in best])
    print(f"    rho(sibling count, |gap|) among sibling-BEST = {r_kb:+.3f}  "
          f"<- winner's curse predicts clearly positive")

# (b) after controlling sibling count + rank + reported level, does code retain signal?
print(f"\n(b) partial correlation with |gap|, controlling k_sib, rank, reported level")
ctrl_names = ["k_sib", "rank", "zs"]
for f in ("code_len", "n_cv", "runtime"):
    per = []
    for t in {r["task"] for r in recs}:
        sub = [r for r in recs if r["task"] == t]
        if len(sub) < 80 or statistics.pstdev([r[f] for r in sub]) < 1e-12:
            continue
        per.append(partial([r[f] for r in sub], [r["gap"] for r in sub],
                           [[r[c] for r in sub] for c in ctrl_names]))
    if per:
        print(f"    {f:10s} mean partial rho = {statistics.mean(per):+.3f}  ({len(per)} tasks)")
print("\n  P2 VERDICT: if (a) shows a clear winner's-curse gradient and (b) is ~0,")
print("  the gap is mostly selection noise and is not code-determined.")
