"""Did graded drift between the corpus the pair files were built on and v8?

Timeline forces the question: decision_pairs_runsplit.jsonl is dated Aug 8 07:37, which is
BEFORE cards_current_v6 (Aug 8 11:20). So the pairs were labelled against cards_current.jsonl
(Aug 7) or earlier, not against v7/v8. v7->v8 showed zero drift, but that only rules out the
last hop. If graded moved on an earlier hop, every pair label is stale with respect to the
corpus we now evaluate on -- and the 6.6% self-contradiction rate is the visible symptom.

Streams id -> graded only; the full card records are far too large to hold several versions
of at once.
"""
import collections, json, math

VERS = ["cards_current.jsonl", "cards_current_v6.jsonl",
        "cards_current_v7.jsonl", "cards_current_v8.jsonl"]


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


G = {}
for v in VERS:
    m = {}
    try:
        for l in open("phase1/" + v):
            d = json.loads(l)
            m[d["id"]] = fin(d.get("label", {}).get("graded"))
    except FileNotFoundError:
        print(f"{v}: absent")
        continue
    G[v] = m
    print(f"{v}: {len(m)} cards, {sum(1 for x in m.values() if x is None)} without graded")

print(f"\n{'from -> to':46s} {'shared':>8} {'changed':>8} {'rate':>8} {'median |d|':>11}")
for i in range(len(VERS) - 1):
    a, b = VERS[i], VERS[i + 1]
    if a not in G or b not in G:
        continue
    sh = set(G[a]) & set(G[b])
    ch = []
    for c in sh:
        x, y = G[a][c], G[b][c]
        if x is None and y is None:
            continue
        if x is None or y is None or abs(x - y) > 1e-12:
            ch.append(abs((x or 0) - (y or 0)))
    ch.sort()
    print(f"{a[:21]:22s} -> {b[:21]:22s} {len(sh):8d} {len(ch):8d} "
          f"{len(ch)/max(len(sh),1):8.2%} "
          f"{ch[len(ch)//2] if ch else 0:11.6f}")

# end to end, and does the drift explain the self-contradicting sibling pairs?
a, b = VERS[0], VERS[-1]
if a in G and b in G:
    sh = set(G[a]) & set(G[b])
    moved = {c for c in sh
             if (G[a][c] is None) != (G[b][c] is None)
             or (G[a][c] is not None and abs(G[a][c] - G[b][c]) > 1e-12)}
    print(f"\nend to end {a} -> {b}: {len(moved)}/{len(sh)} cards moved "
          f"({len(moved)/max(len(sh),1):.2%})")

    ORI = json.load(open("phase1/task_orientation.json"))
    n = contra = contra_moved = 0
    by = collections.Counter()
    for l in open("phase1/decision_pairs_runsplit.jsonl"):
        p = json.loads(l)
        x, y, t = p["better"], p["worse"], p["task"]
        if x not in G[b] or y not in G[b]:
            continue
        gx, gy = G[b][x], G[b][y]
        if gx is None or gy is None or gx == gy:
            continue
        n += 1
        if not ((gx < gy) if ORI.get(t, False) else (gx > gy)):
            contra += 1
            if x in moved or y in moved:
                contra_moved += 1
            by[t] += 1
    print(f"sibling pairs contradicting v8: {contra}/{n} = {contra/max(n,1):.2%}")
    print(f"  of those, at least one endpoint drifted since {a}: {contra_moved} "
          f"({contra_moved/max(contra,1):.1%})  <- if high, the labels are simply stale")

    # and does the ORIGINAL corpus reproduce them?
    n2 = contra2 = 0
    for l in open("phase1/decision_pairs_runsplit.jsonl"):
        p = json.loads(l)
        x, y, t = p["better"], p["worse"], p["task"]
        if x not in G[a] or y not in G[a]:
            continue
        gx, gy = G[a][x], G[a][y]
        if gx is None or gy is None or gx == gy:
            continue
        n2 += 1
        if not ((gx < gy) if ORI.get(t, False) else (gx > gy)):
            contra2 += 1
    print(f"same test against the ORIGINAL corpus {a}: {contra2}/{n2} = "
          f"{contra2/max(n2,1):.2%}  <- near 0 means the labels were right when made")
