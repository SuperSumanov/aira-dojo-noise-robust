"""Does the pair set contain the same two nodes labelled both ways?

The examples point that way: the same two graded values appear once as (better, worse) and
once as (worse, better), with a DIFFERENT gap_raw each time even though |graded diff| is
identical. If those are literally the same two card ids, the pair set carries mutually
contradictory labels -- a predictor cannot be right on both, so a fixed fraction of the
"unpredictable hard region" would just be self-cancelling duplicates rather than anything
about difficulty. That would be the single most consequential defect available to find here,
so it is checked directly rather than inferred.

Reported for every pair file, since the same builder made all of them:
  reversed duplicates   the same unordered node pair present in both directions
  exact duplicates      the same ordered pair present more than once
  gap_raw multiplicity  how many distinct gap_raw values one unordered node pair carries
"""
import collections, json, math

for name in ("decision_pairs_runsplit.jsonl", "value_pairs_runsplit.jsonl",
             "hits_l1_uncapped.jsonl"):
    seen = collections.Counter()
    gaps = collections.defaultdict(set)
    extra = collections.defaultdict(set)
    n = 0
    for l in open("phase1/" + name):
        p = json.loads(l)
        b, w = p["better"], p["worse"]
        n += 1
        seen[(b, w)] += 1
        key = tuple(sorted((b, w)))
        g = p.get("gap_raw")
        if g is not None:
            gaps[key].add(round(float(g), 6))
        for f in ("parent", "budget", "budget_steps", "set_size", "intask_split"):
            if f in p:
                extra[key].add((f, str(p[f])))
    und = collections.defaultdict(set)
    for (b, w) in seen:
        und[tuple(sorted((b, w)))].add((b, w))
    rev = [k for k, v in und.items() if len(v) > 1]
    exact = [k for k, c in seen.items() if c > 1]
    multi = [k for k, v in gaps.items() if len(v) > 1]
    print(f"\n{name}")
    print(f"  rows {n}; distinct ordered pairs {len(seen)}; "
          f"distinct unordered node pairs {len(und)}")
    print(f"  REVERSED duplicates (same two nodes, both directions): {len(rev)} "
          f"({len(rev)/max(len(und),1):.2%} of unordered pairs)")
    print(f"  exact ordered duplicates (same direction, repeated): {len(exact)}; "
          f"extra rows they contribute: {sum(seen[k]-1 for k in exact)}")
    print(f"  unordered pairs carrying MORE THAN ONE gap_raw: {len(multi)} "
          f"({len(multi)/max(len(und),1):.2%})")
    if multi:
        ex = multi[:4]
        for k in ex:
            print(f"     {k[0][-12:]}/{k[1][-12:]}  gap_raw values {sorted(gaps[k])[:6]}")
    if rev:
        k = rev[0]
        print(f"  example reversed pair: {k[0][-14:]} vs {k[1][-14:]}")
        print(f"     distinguishing fields seen: "
              f"{sorted(extra[k])[:10]}")
    # how many ROWS are involved in a reversed conflict
    rows_rev = sum(seen[o] for k in rev for o in und[k])
    print(f"  rows involved in a reversed conflict: {rows_rev} "
          f"({rows_rev/max(n,1):.2%} of rows)")
