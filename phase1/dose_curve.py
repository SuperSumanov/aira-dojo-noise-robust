"""The decision-cost dose-response curve: selection accuracy vs seconds of execution.

Input: fidelity_results.jsonl (capped reruns; one record per (child, cap)) plus the corpus
full-fidelity endpoint (val_at_low / graded, already paid for at collection time).

Per sibling set and per cap T, the selection policy "run every child for T seconds, then
commit" picks by, in order of preference: the child's stdout_val at T (metric parsed from
its own output, task orientation applied); if no child parsed, the set is undecidable at T
and falls back to random (counted and reported -- hiding fallbacks would flatter low caps).
sub_score at T is reported as a secondary channel (pristine grade of whatever submission
existed at the cut) but does not enter the headline policy: a real controller would not
have the hidden test labels.

Outputs, with parent-clustered bootstrap CIs: top-1 rate per cap against random / full
val_at_low / oracle, split by stratum (hard = top-2 true gap < 1e-2), plus the coverage
table (parse rate, submission rate, undecidable-set rate) that determines what the curve
can honestly claim.

Usage: python phase1/dose_curve.py [--results phase1/fidelity_results.jsonl]
"""
import argparse, collections, json, math, random

ap = argparse.ArgumentParser()
ap.add_argument("--results", default="phase1/fidelity_results.jsonl")
a = ap.parse_args()

ORI = json.load(open("phase1/task_orientation.json"))
G, OWN, TASK = {}, {}, {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    TASK[d["id"]] = d["task"]["name"]
    for tgt, src, key in ((G, d["label"], "graded"), (OWN, d["obs"], "val_at_low")):
        try:
            v = float(src.get(key))
            tgt[d["id"]] = v if math.isfinite(v) else None
        except (TypeError, ValueError):
            tgt[d["id"]] = None

R = collections.defaultdict(dict)          # card -> cap -> record
manifest_children = collections.defaultdict(set)
strat_of = {}
for l in open(a.results):
    try:
        d = json.loads(l)
    except json.JSONDecodeError:
        continue
    R[d["card_id"]][d["cap"]] = d
    manifest_children[d["parent"]].add(d["card_id"])
    strat_of[d["parent"]] = d.get("stratum")
CAPS = sorted({c for m in R.values() for c in m})
print(f"children with results: {len(R)}; sets: {len(manifest_children)}; caps: {CAPS}")

# coverage table first -- it bounds every claim below
print(f"\n{'cap':>5} {'runs':>5} {'rc=0':>6} {'stdout_val':>11} {'keyed':>6} "
      f"{'sub exists':>11} {'sub graded':>11} {'median wall':>12}")
for c in CAPS:
    rows = [m[c] for m in R.values() if c in m]
    walls = sorted(r["wall_s"] for r in rows)
    print(f"{c:>5} {len(rows):>5} {sum(1 for r in rows if r['rc']==0):>6} "
          f"{sum(1 for r in rows if r['stdout_val'] is not None):>11} "
          f"{sum(1 for r in rows if r.get('val_how')=='keyed'):>6} "
          f"{sum(1 for r in rows if r['sub_exists']):>11} "
          f"{sum(1 for r in rows if r['sub_score'] is not None):>11} "
          f"{walls[len(walls)//2] if walls else 0:>12}")


def lower(t):
    return ORI.get(t, False)


def pick_by(vals, t):
    """vals: {child: signal}; returns argmax under task orientation"""
    return (min if lower(t) else max)(vals, key=lambda c: vals[c])


def best_children(ch, t):
    bv = (min if lower(t) else max)(G[c] for c in ch)
    return {c for c in ch if G[c] == bv}, bv


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


def curve(universe, label):
    print(f"\n=== {label}: {len(universe)} sets ===")
    print(f"{'policy':>22} {'top1':>7} {'95% CI (parent)':>19} {'decided':>8} "
          f"{'fallback-random':>16}")
    # random + oracle + full endpoints
    pp_r, pp_full = {}, {}
    for par in universe:
        ch = [c for c in manifest_children[par] if G.get(c) is not None]
        if len(ch) < 2:
            continue
        t = TASK[ch[0]]
        best, _ = best_children(ch, t)
        pp_r[par] = [len(best) / len(ch)]
        have = {c: OWN[c] for c in ch if OWN.get(c) is not None}
        if len(have) == len(ch):
            pp_full[par] = [float(pick_by(have, t) in best)]
    for nm, pp in (("random", pp_r), (f"full exec (corpus)", pp_full)):
        if not pp:
            continue
        v = [x for vs in pp.values() for x in vs]
        lo, hi = boot(pp)
        print(f"{nm:>22} {sum(v)/len(v):7.4f} [{lo:.4f},{hi:.4f}] {len(pp):8d} "
              f"{'-':>16}")
    for c in CAPS:
        for chan, getter in (("stdout_val", lambda r: r["stdout_val"]),
                             ("sub_score", lambda r: r["sub_score"])):
            pp, fell = {}, 0
            dec_only = {}
            for par in universe:
                ch = [x for x in manifest_children[par] if G.get(x) is not None]
                if len(ch) < 2:
                    continue
                t = TASK[ch[0]]
                best, _ = best_children(ch, t)
                sig = {x: getter(R[x][c]) for x in ch
                       if c in R.get(x, {}) and getter(R[x][c]) is not None}
                if sig:
                    hit = float(pick_by(sig, t) in best)
                    pp[par] = [hit]
                    dec_only[par] = [hit]
                else:
                    fell += 1
                    pp[par] = [len(best) / len(ch)]      # honest fallback = random
            v = [x for vs in pp.values() for x in vs]
            if not v:
                continue
            lo, hi = boot(pp)
            line = (f"{'%s@%ds' % (chan, c):>22} {sum(v)/len(v):7.4f} "
                    f"[{lo:.4f},{hi:.4f}] {len(pp)-fell:8d} {fell:16d}")
            if dec_only:
                dv = [x for vs in dec_only.values() for x in vs]
                dlo, dhi = boot(dec_only)
                line += (f"   decided-only {sum(dv)/len(dv):.4f} "
                         f"[{dlo:.4f},{dhi:.4f}]")
            print(line)


all_sets = [p for p in manifest_children
            if len([c for c in manifest_children[p] if G.get(c) is not None]) >= 2]
curve(all_sets, "ALL sampled sets")
curve([p for p in all_sets if strat_of.get(p) == "hard"], "HARD stratum")
curve([p for p in all_sets if strat_of.get(p) == "easy"], "EASY stratum")

print("\nRead: the curve is the stdout_val@T rows against the two anchors (random below,")
print("full-exec above). A flat climb that reaches the full anchor by 120s means selection")
print("saturates at a fraction of median execution cost (561s); a slow climb means the")
print("cliff genuinely requires execution depth. Fallback counts bound the claim either way.")
