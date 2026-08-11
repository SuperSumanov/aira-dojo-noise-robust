"""Remove the vestigial fragment-root holdout inside decision_pairs.py.

It predates the run-level split. It draws 20% of tree roots per task (seed 7) and DROPS any
sibling set whose members straddle the draw -- which only orphaned siblings can do, since
intact sets share one root. The draw is over the whole root universe, so growing the corpus
reshuffles it and a different set of orphan groups gets dropped: exactly the 19 old pairs
that vanished from the v9 regeneration while every surviving pair kept its label bit-for-bit.

build_runsplit.py now assigns the only split that counts, at physical-run level, downstream
of this file; sibling pairs live inside one run and can never straddle it. The generator's
own split column is a placeholder the re-splitter overwrites, so the drop rule protects
nothing and costs pairs as a function of corpus size. It goes.
"""
P = "phase1/decision_pairs.py"
s = open(P, encoding="utf-8").read()

if "vestigial" in s:
    print("already patched")
    raise SystemExit(0)

a = """rng = random.Random(a.seed)
by_task_roots = collections.defaultdict(set)
for cid in cards:
    t = cards[cid]["task"]["name"]
    if t in ORI:
        by_task_roots[t].add(tree_root(cid))
hold = {}
for t, roots in by_task_roots.items():
    rs = sorted(roots)
    rng.shuffle(rs)
    hold[t] = set(rs[int(0.8 * len(rs)):])
"""
assert s.count(a) == 1, s.count(a)
s = s.replace(a, """# (vestigial fragment-root holdout removed -- build_runsplit.py assigns the real split
# at physical-run level downstream; the drop rule here only ever hit orphaned sibling sets
# and which ones it hit depended on corpus size through the shuffle.)
""")

b = """        lower = ORI[t]
        sides_ = {tree_root(c) in hold[t] for c in ch}
        if len(sides_) > 1:
            n["__dropped_cross_fragment_sets__", -1, "drop"] += 1
            continue
        in_hold = sides_.pop()
        split = "test" if in_hold else "train"
        sets_seen[(t, split)] += 1
"""
assert s.count(b) == 1, s.count(b)
s = s.replace(b, """        lower = ORI[t]
        split = "train"   # placeholder; build_runsplit.py overwrites at run level
        sets_seen[(t, split)] += 1
""")

open(P, "w", encoding="utf-8").write(s)
print("patched", P)
