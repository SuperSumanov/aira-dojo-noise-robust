"""The paired version of the dose-response comparison, on identical set populations.

The headline curve's decided-only column carries a selection bias: sets whose candidates
emit early submissions are systematically the faster, simpler ones, so comparing
sub_score@120's decided-only 0.73 against full-exec's 0.79-on-its-own-89-sets conflates
signal quality with set difficulty. Here every comparison is WITHIN one fixed set
population, as paired per-set differences with a parent-clustered bootstrap:

  P1  sets decidable by sub_score@120 AND covered by full val_at_low
      -> is the 120s partial-submission grade actually as good as the full signal
         where both exist? (the "1/5 cost, full quality" claim lives or dies here)
  P2  same for stdout_val@120 vs full
  P3  sub_score@120 vs random on its decidable sets (the deployable-policy margin)

Usage: python phase1/dose_paired.py
"""
import collections, json, math, random

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

R = collections.defaultdict(dict)
kids = collections.defaultdict(set)
strat_of = {}
for l in open("phase1/fidelity_results.jsonl"):
    d = json.loads(l)
    R[d["card_id"]][d["cap"]] = d
    kids[d["parent"]].add(d["card_id"])
    strat_of[d["parent"]] = d.get("stratum")


def lower(t):
    return ORI.get(t, False)


def pick(vals, t):
    return (min if lower(t) else max)(vals, key=lambda c: vals[c])


def hit_of(par, sig):
    ch = [c for c in kids[par] if G.get(c) is not None]
    t = TASK[ch[0]]
    bv = (min if lower(t) else max)(G[c] for c in ch)
    best = {c for c in ch if G[c] == bv}
    return float(pick(sig, t) in best), len(best) / len(ch)


def sig_sub(par, cap):
    ch = [c for c in kids[par] if G.get(c) is not None]
    s = {c: R[c][cap]["sub_score"] for c in ch
         if cap in R.get(c, {}) and R[c][cap]["sub_score"] is not None}
    return s or None


def sig_stdout(par, cap):
    ch = [c for c in kids[par] if G.get(c) is not None]
    s = {c: R[c][cap]["stdout_val"] for c in ch
         if cap in R.get(c, {}) and R[c][cap]["stdout_val"] is not None}
    return s or None


def sig_full(par):
    ch = [c for c in kids[par] if G.get(c) is not None]
    s = {c: OWN[c] for c in ch if OWN.get(c) is not None}
    return s if len(s) == len(ch) else None


def boot(d, nb=4000, seed=7):
    ks = list(d)
    rr = random.Random(seed)
    o = []
    for _ in range(nb):
        v = [x for k in (rr.choice(ks) for _ in ks) for x in d[k]]
        o.append(sum(v) / len(v))
    o.sort()
    return o[int(.025 * nb)], o[int(.975 * nb)]


def paired(name, a_fn, b_fn, universe):
    da, db, dd = {}, {}, {}
    for par in universe:
        ch = [c for c in kids[par] if G.get(c) is not None]
        if len(ch) < 2:
            continue
        sa, sb = a_fn(par), b_fn(par)
        if sa is None or sb is None:
            continue
        ha, _ = hit_of(par, sa)
        hb, _ = hit_of(par, sb)
        da[par], db[par], dd[par] = [ha], [hb], [ha - hb]
    if not dd:
        print(f"  {name}: no overlapping sets")
        return
    va = [x for v in da.values() for x in v]
    vb = [x for v in db.values() for x in v]
    vd = [x for v in dd.values() for x in v]
    lo, hi = boot(dd)
    print(f"  {name}: n={len(dd)} sets   A={sum(va)/len(va):.4f}  B={sum(vb)/len(vb):.4f}"
          f"   A-B={sum(vd)/len(vd):+.4f} [{lo:+.4f},{hi:+.4f}]"
          f"{'  SIG' if lo > 0 or hi < 0 else ''}")


def paired_rand(name, a_fn, universe):
    dd = {}
    for par in universe:
        ch = [c for c in kids[par] if G.get(c) is not None]
        if len(ch) < 2:
            continue
        sa = a_fn(par)
        if sa is None:
            continue
        ha, rexp = hit_of(par, sa)
        dd[par] = [ha - rexp]
    if not dd:
        return
    vd = [x for v in dd.values() for x in v]
    lo, hi = boot(dd)
    print(f"  {name}: n={len(dd)} sets   A-random={sum(vd)/len(vd):+.4f} "
          f"[{lo:+.4f},{hi:+.4f}]{'  SIG' if lo > 0 or hi < 0 else ''}")


ALL = list(kids)
for label, uni in (("ALL", ALL),
                   ("HARD", [p for p in ALL if strat_of.get(p) == "hard"]),
                   ("EASY", [p for p in ALL if strat_of.get(p) == "easy"])):
    print(f"\n=== {label} ({len(uni)} sets) ===")
    paired("P1 sub@120 vs full", lambda p: sig_sub(p, 120), sig_full, uni)
    paired("P2 stdout@120 vs full", lambda p: sig_stdout(p, 120), sig_full, uni)
    paired("P2b stdout@30 vs full", lambda p: sig_stdout(p, 30), sig_full, uni)
    paired_rand("P3 sub@120 vs random (its own sets)", lambda p: sig_sub(p, 120), uni)
    paired_rand("P3b stdout@120 vs random", lambda p: sig_stdout(p, 120), uni)

print("\nRead: P1 near zero with a tight CI is the strong form of the claim -- where a")
print("120s submission exists, grading it externally matches the full execution signal at")
print("a fifth of the cost. P1 clearly negative would demote the dose-response prescription")
print("to 'cheap but lossy'. P3 is the deployable margin on the sets the policy can act on.")
