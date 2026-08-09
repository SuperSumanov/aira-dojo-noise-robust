"""Is the k>=4 curse one task in disguise? (the check that killed five directions)"""
import collections, json, math, statistics
ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l); cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)
def fin(x):
    try: v = float(x)
    except (TypeError, ValueError): return None
    return v if math.isfinite(v) else None
rows = []
for t in {d["task"]["name"] for d in cards.values()}:
    pool = [(c, fin(d["obs"].get("val_at_low")), fin(d["label"].get("graded")))
            for c, d in cards.items() if d["task"]["name"] == t]
    pool = [(c, v, g) for c, v, g in pool if v is not None and g is not None]
    if len(pool) < 80: continue
    sgn = -1.0 if ORI.get(t, False) else 1.0
    vv = [sgn*v for _, v, _ in pool]; gg = [sgn*g for _, _, g in pool]
    mv, dv = statistics.mean(vv), statistics.pstdev(vv) or 1.0
    mg, dg = statistics.mean(gg), statistics.pstdev(gg) or 1.0
    zv = {c: (sgn*v-mv)/dv for c, v, _ in pool}
    zg = {c: (sgn*g-mg)/dg for c, _, g in pool}
    for c, _, _ in pool:
        p = cards[c]["lineage"].get("parent_id")
        sib = [x for x in (kids.get(p, []) if p else []) if x in zv]
        if len(sib) < 2: continue
        if max(sib, key=lambda x: zv[x]) != c: continue
        rows.append((t, len(sib), zg[c]-zv[c]))
for lo, hi, lab in ((2,3,"k=2-3"), (4,99,"k>=4")):
    sub = [r for r in rows if lo <= r[1] <= hi]
    by = collections.defaultdict(list)
    for t, k, s in sub: by[t].append(s)
    print(f"\n{lab}: n={len(sub)}, mean {statistics.mean([s for _,_,s in sub]):+.4f}")
    for t, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"   {t[:40]:40s} n={len(v):4d} mean={statistics.mean(v):+.4f}")
