"""How much of the v1 'budget flip' phenomenon survives count-matching?

v1 defined value(node, B) as the best score anywhere within depth B, so a node with a bigger
subtree simply drew more samples. Here value(node, K) uses the first K expansions in the order
the search actually made them, and both nodes of a pair must have at least K -- equal draws.
If the flip rate collapses, the v1 flips were a sampling artifact, not a budget effect.
"""
import collections, itertools, json

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)


def dio(c):
    out, st, seen = [], list(kids.get(c, [])), set()
    while st:
        x = st.pop()
        if x in seen or x not in cards: continue
        seen.add(x); out.append(x); st.extend(kids.get(x, []))
    return sorted(out, key=lambda k: (cards[k]["lineage"].get("step") or 0, k))


D = {c: dio(c) for c in cards}
KS = [1, 2, 3, 5, 8]
val = collections.defaultdict(dict)
depthval = collections.defaultdict(dict)   # v1-style: everything within DEPTH B
for cid, d in cards.items():
    t = d["task"]["name"]
    if t not in ORI: continue
    pk = min if ORI[t] else max
    own = d["label"]["graded"]
    for K in KS:
        if len(D[cid]) >= K:
            val[K][cid] = pk([own] + [cards[x]["label"]["graded"] for x in D[cid][:K]])
    if D[cid]:
        depthval[0][cid] = pk([own] + [cards[x]["label"]["graded"] for x in D[cid]])
    depthval[1][cid] = pk([own] + [cards[x]["label"]["graded"] for x in kids.get(cid, []) if x in cards])

by_task = collections.defaultdict(list)
for cid, d in cards.items():
    if d["task"]["name"] in ORI: by_task[d["task"]["name"]].append(cid)


def lab(x, y, table, lower):
    if x not in table or y not in table: return None
    vx, vy = table[x], table[y]
    if vx == vy: return None
    return (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)


print("A) v1 style (depth-bounded, UNEQUAL draws):  1 step  vs  unlimited subtree")
tot = fl = 0
for t, cs in sorted(by_task.items()):
    lower = ORI[t]
    for x, y in itertools.combinations([c for c in cs if c in depthval[0]], 2):
        L = lab(x, y, depthval[1], lower); H = lab(x, y, depthval[0], lower)
        if L is None or H is None: continue
        tot += 1; fl += (L != H)
print(f"   flips {fl}/{tot} = {fl / max(tot, 1) * 100:.2f}%")

print()
print("B) count-matched (EQUAL draws): K=1 vs K=KHI, both nodes need >= KHI expansions")
for KHI in (2, 3, 5, 8):
    tot = fl = 0
    for t, cs in sorted(by_task.items()):
        lower = ORI[t]
        elig = [c for c in cs if c in val[KHI]]
        for x, y in itertools.combinations(elig, 2):
            L = lab(x, y, val[1], lower); H = lab(x, y, val[KHI], lower)
            if L is None or H is None: continue
            tot += 1; fl += (L != H)
    print(f"   K=1 vs K={KHI}: flips {fl}/{tot} = {fl / max(tot, 1) * 100:.2f}%   (usable pairs {tot})")
