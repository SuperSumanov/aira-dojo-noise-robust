"""Selection regret on real sibling sets: the cost-accuracy frontier, simulated not asserted.

Pairwise accuracy is the measurable but not the deliverable. What a search actually does is
pick ONE child of k to execute next, so the decision-relevant quantity is REGRET: how much
of the best sibling's quality the policy's pick gives up. The dataset contains every full
sibling set with both the post-hoc truth (graded) and the cheap signal (val_at_low), so the
frontier -- selection quality against per-decision cost -- can be simulated exactly on the
decisions search faced, with no modeling assumptions.

Policies, per sibling set (>=2 children with graded):
  oracle       argmax graded (free hindsight; upper bound)
  self_report  argmax val_at_low -- costs k executions
  tfidf        Copeland score from the frozen pairwise decisions -- costs ~0
  random       expectation over children (analytic)

Regret is medal-normalised per task ((chosen - best)/(gold - bronze) is unstable when
thresholds collapse, so instead: rank-of-chosen and the raw graded gap to the best child;
report medians and the fraction of sets where the pick IS the best child).
"""
import collections, json, math, statistics

ORI = json.load(open("phase1/task_orientation.json"))
PP = json.load(open("phase1/perpair_decision.json"))
TF = PP.get("tfidf_lr", {})
G, OWN, TASK, PARENT = {}, {}, {}, {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    TASK[d["id"]] = d["task"]["name"]
    PARENT[d["id"]] = d["lineage"].get("parent_id")
    for tgt, src, key in ((G, d["label"], "graded"), (OWN, d["obs"], "val_at_low")):
        try:
            v = float(src.get(key))
            tgt[d["id"]] = v if math.isfinite(v) else None
        except (TypeError, ValueError):
            tgt[d["id"]] = None

# eligible sibling sets: restrict to the b0 TEST universe so nothing here was trainable
test_children = collections.defaultdict(set)
for l in open("phase1/decision_clean_b0.jsonl"):
    p = json.loads(l)
    test_children[p["parent"]].update((p["better"], p["worse"]))

sets_ = {par: sorted(ch) for par, ch in test_children.items()
         if len([c for c in ch if G.get(c) is not None]) >= 2}
print(f"sibling sets in the b0 test universe: {len(sets_)}")


def better(a, b, t):
    return (a < b) if ORI.get(t, False) else (a > b)


def pick_oracle(ch, t):
    return max(ch, key=lambda c: (-G[c]) if ORI.get(t, False) else G[c])


def pick_sr(ch, t):
    have = [c for c in ch if OWN.get(c) is not None]
    if len(have) < len(ch):
        return None                       # a set with missing self-reports is not decidable
    return max(have, key=lambda c: (-OWN[c]) if ORI.get(t, False) else OWN[c])


def pick_tfidf(ch, t):
    score = collections.Counter()
    seen = 0
    for i, x in enumerate(ch):
        for y in ch[i + 1:]:
            d = TF.get(x + "|" + y)
            if d is None:
                d0 = TF.get(y + "|" + x)
                if d0 is None:
                    continue
                d = 1 - d0
            seen += 1
            score[x if d == 1 else y] += 1
    if not seen:
        return None
    return max(sorted(ch), key=lambda c: score[c])


POL = {"oracle": pick_oracle, "self_report": pick_sr, "tfidf_copeland": pick_tfidf}
res = collections.defaultdict(lambda: {"top1": 0, "n": 0, "gaps": [], "ranks": []})
rnd = {"top1": 0.0, "n": 0, "gaps": [], "ranks": []}
for par, ch in sets_.items():
    ch = [c for c in ch if G.get(c) is not None]
    t = TASK[ch[0]]
    lower = ORI.get(t, False)
    ranked = sorted(ch, key=lambda c: G[c], reverse=not lower)
    best = ranked[0]
    for name, fn in POL.items():
        pick = fn(ch, t)
        if pick is None:
            continue
        r = res[name]
        r["n"] += 1
        r["top1"] += int(G[pick] == G[best])
        r["gaps"].append(abs(G[best] - G[pick]))
        r["ranks"].append(1 + min(i for i, c in enumerate(ranked) if G[c] == G[pick]))
    rnd["n"] += 1
    rnd["top1"] += sum(1 for c in ch if G[c] == G[best]) / len(ch)
    rnd["gaps"].append(sum(abs(G[best] - G[c]) for c in ch) / len(ch))
    rnd["ranks"].append(sum(range(1, len(ch) + 1)) / len(ch))

MED_EXEC = 561   # measured median runtime_s; the cost of one self-report
print(f"\n{'policy':16s} {'sets':>5} {'picked best':>12} {'median gap':>11} "
      f"{'mean rank':>10} {'cost per decision':>22}")
for name in ("oracle", "self_report", "tfidf_copeland"):
    r = res[name]
    if not r["n"]:
        continue
    cost = ("k x %ds exec" % MED_EXEC if name == "self_report"
            else "hindsight" if name == "oracle" else "~0 (ms)")
    print(f"{name:16s} {r['n']:5d} {r['top1']/r['n']:12.1%} "
          f"{statistics.median(r['gaps']):11.5f} "
          f"{statistics.mean(r['ranks']):10.2f} {cost:>22}")
print(f"{'random':16s} {rnd['n']:5d} {rnd['top1']/rnd['n']:12.1%} "
      f"{statistics.median(rnd['gaps']):11.5f} {statistics.mean(rnd['ranks']):10.2f} "
      f"{'0':>22}")

# ---- inference: cluster bootstrap over parents (a parent IS one decision) -----------
import random as _random


def _boot_sets(per_parent, nb=4000, seed=7):
    ks = list(per_parent)
    rr = _random.Random(seed)
    out = []
    for _ in range(nb):
        v = [x for k in (rr.choice(ks) for _ in ks) for x in per_parent[k]]
        out.append(sum(v) / len(v))
    out.sort()
    return out[int(.025 * nb)], out[int(.975 * nb)]


def _per_parent(policy_fn, universe):
    d = {}
    for par in universe:
        ch = [c for c in sets_[par] if G.get(c) is not None]
        t = TASK[ch[0]]
        lower = ORI.get(t, False)
        best_v = (min if lower else max)(G[c] for c in ch)
        pick = policy_fn(ch, t)
        if pick is None:
            continue
        d[par] = [float(G[pick] == best_v)]
    return d


def _per_parent_rand(universe):
    d = {}
    for par in universe:
        ch = [c for c in sets_[par] if G.get(c) is not None]
        t = TASK[ch[0]]
        lower = ORI.get(t, False)
        best_v = (min if lower else max)(G[c] for c in ch)
        d[par] = [sum(1 for c in ch if G[c] == best_v) / len(ch)]
    return d


def _top2gap(par):
    ch = [c for c in sets_[par] if G.get(c) is not None]
    t = TASK[ch[0]]
    vs = sorted((G[c] for c in ch), reverse=not ORI.get(t, False))
    return abs(vs[0] - vs[1])


_hard = [p for p in sets_ if _top2gap(p) < 1e-2]

print("\nparent-clustered 95% CIs (top-1 rate; and paired differences on shared sets)")
for label, universe in (("ALL sets", list(sets_)),
                        ("HARD sets (top-2 true gap < 1e-2)", _hard)):
    pp_sr = _per_parent(pick_sr, universe)
    pp_tf = _per_parent(pick_tfidf, universe)
    pp_rd = _per_parent_rand(universe)
    rows = [("self_report", pp_sr), ("tfidf_copeland", pp_tf), ("random", pp_rd)]
    print(f"  {label}: n={len(universe)}")
    for nm, pp in rows:
        if not pp:
            continue
        v = [x for vs in pp.values() for x in vs]
        lo, hi = _boot_sets(pp)
        print(f"    {nm:16s} top1={sum(v)/len(v):.4f} [{lo:.4f},{hi:.4f}] "
              f"decidable={len(pp)}")
    shared = set(pp_sr) & set(pp_rd)
    diff = {k: [pp_sr[k][0] - pp_rd[k][0]] for k in shared}
    if diff:
        v = [x for vs in diff.values() for x in vs]
        lo, hi = _boot_sets(diff)
        print(f"    SR - random     = {sum(v)/len(v):+.4f} [{lo:+.4f},{hi:+.4f}]"
              f"{'  SIG' if lo > 0 or hi < 0 else ''}")
    shared = set(pp_sr) & set(pp_tf)
    diff = {k: [pp_sr[k][0] - pp_tf[k][0]] for k in shared}
    if diff:
        v = [x for vs in diff.values() for x in vs]
        lo, hi = _boot_sets(diff)
        print(f"    SR - tfidf      = {sum(v)/len(v):+.4f} [{lo:+.4f},{hi:+.4f}]"
              f"{'  SIG' if lo > 0 or hi < 0 else ''}")
    shared = set(pp_tf) & set(pp_rd)
    diff = {k: [pp_tf[k][0] - pp_rd[k][0]] for k in shared}
    if diff:
        v = [x for vs in diff.values() for x in vs]
        lo, hi = _boot_sets(diff)
        print(f"    tfidf - random  = {sum(v)/len(v):+.4f} [{lo:+.4f},{hi:+.4f}]"
              f"{'  SIG' if lo > 0 or hi < 0 else ''}")

# split by decision difficulty: sets whose top-2 true gap is inside the hard region
hard_sets = {p for p, ch in sets_.items()
             if len([c for c in ch if G.get(c) is not None]) >= 2
             and abs(sorted((G[c] for c in ch if G.get(c) is not None),
                            reverse=not ORI.get(TASK[ch[0]], False))[0]
                     - sorted((G[c] for c in ch if G.get(c) is not None),
                              reverse=not ORI.get(TASK[ch[0]], False))[1]) < 1e-2}
print(f"\nsets whose top-2 true gap < 1e-2 (the hard decisions): {len(hard_sets)} "
      f"({len(hard_sets)/max(len(sets_),1):.0%})")
print("Read: if self_report picks the best child far more often than random while every")
print("static policy sits at random's level, the frontier has a cliff between free and")
print("execution-grounded signals -- measured on the actual decisions, which is the")
print("positive, quantified form of the K=0 result.")
