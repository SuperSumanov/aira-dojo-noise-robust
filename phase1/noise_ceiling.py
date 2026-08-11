"""Independent recomputation of the label-noise ceiling on our own data.

The external audit's four-elimination framing rests on this number, but it was computed by
someone reading a partial checkout. Two of the four legs (this one and corpus uniqueness)
are theirs, not ours, so before either goes in a paper it has to be reproduced here.

The identity. A node's graded score is one noisy measurement of a hidden true quality. For
a pair of same-task nodes, two INDEPENDENT measurement rounds each induce a label ("which
node is better"). If a single label agrees with the hidden order with probability a, two
independent labels agree with each other with probability a^2 + (1-a)^2. Observed agreement
therefore inverts to a = (1 + sqrt(2*obs - 1)) / 2, and that a is the ceiling any predictor
could reach against labels generated this way.

Three things the audit warned about, all implemented here:
  * report BOTH within-session (repeats inside one regrade batch) and cross-session
    (original grade vs the mean of repeats) -- cross is the conservative one and the one
    to quote, because it spans physical nodes and machine state.
  * bucket by |gap| and transport to the REAL pair distribution rather than pooling; a
    pooled figure is dominated by easy, large-gap pairs.
  * a bucket with too few observations must NOT fall back to the pooled agreement -- that
    hands the hardest bucket an optimistic a and inflates the ceiling. Let it inherit the
    value of the nearest SMALLER-gap bucket (pessimistic), then enforce monotonicity.

Quote the margin, not the point estimate: the point estimate extrapolates to unmeasured
tasks, the margin does not.

Usage: python phase1/noise_ceiling.py [--cards cards_current_v8.jsonl]
"""
import argparse, collections, glob, json, math, random, statistics

ap = argparse.ArgumentParser()
ap.add_argument("--cards", default="phase1/cards_current_v8.jsonl")
ap.add_argument("--regrade", default="phase1/regrade_results*.jsonl")
ap.add_argument("--min-bucket", type=int, default=25)
a = ap.parse_args()

ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open(a.cards):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---- collect repeats -----------------------------------------------------------
reps = collections.defaultdict(list)
orig = {}
task_of = {}
for path in sorted(glob.glob(a.regrade)):
    for l in open(path):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        s = fin(d.get("score"))
        cid = d.get("card_id")
        if cid is None:
            continue
        task_of[cid] = d.get("competition")
        o = fin(d.get("orig_graded"))
        if o is not None:
            orig[cid] = o
        if s is not None:
            reps[cid].append(s)
usable = {c: v for c, v in reps.items() if len(v) >= 2}
print(f"regrade files: {len(glob.glob(a.regrade))}; nodes with >=1 successful repeat: "
      f"{len(reps)}; with >=2: {len(usable)}")
bytask = collections.Counter(task_of[c] for c in usable)
print(f"tasks represented: {len(bytask)}  {dict(bytask.most_common())}")


def label(x, y, task):
    """which of two measurements ranks the first node above the second"""
    if x == y:
        return None
    return int((x < y) if ORI.get(task, False) else (x > y))


def agreement(pairs):
    ok = tot = 0
    for l1, l2 in pairs:
        if l1 is None or l2 is None:
            continue
        ok += int(l1 == l2)
        tot += 1
    return ok, tot


def invert(obs):
    """a from P(agree) = a^2 + (1-a)^2; obs below 0.5 means no signal"""
    if obs is None or obs <= 0.5:
        return 0.5
    return (1 + math.sqrt(max(0.0, 2 * obs - 1))) / 2


# ---- build same-task node pairs in both measurement regimes ---------------------
def build(mode):
    """mode 'within': repeat[0] vs repeat[1].  mode 'cross': orig vs mean(repeats)."""
    out = collections.defaultdict(list)   # task -> list of (gap, l1, l2)
    ids = sorted(usable)
    bytask_ids = collections.defaultdict(list)
    for c in ids:
        bytask_ids[task_of[c]].append(c)
    for t, cs in bytask_ids.items():
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                ci, cj = cs[i], cs[j]
                if mode == "within":
                    if len(usable[ci]) < 2 or len(usable[cj]) < 2:
                        continue
                    m1 = (usable[ci][0], usable[cj][0])
                    m2 = (usable[ci][1], usable[cj][1])
                else:
                    if ci not in orig or cj not in orig:
                        continue
                    m1 = (orig[ci], orig[cj])
                    m2 = (statistics.mean(usable[ci]), statistics.mean(usable[cj]))
                gap = abs(statistics.mean(usable[ci]) - statistics.mean(usable[cj]))
                out[t].append((gap, label(*m1, t), label(*m2, t)))
    return out


BUCKETS = [0.0, 1e-4, 1e-3, 5e-3, 2e-2, 1e-1, float("inf")]


def bucket_of(g):
    for k in range(len(BUCKETS) - 1):
        if BUCKETS[k] <= g < BUCKETS[k + 1]:
            return k
    return len(BUCKETS) - 2


for mode in ("within", "cross"):
    data = build(mode)
    allp = [p for v in data.values() for p in v]
    ok, tot = agreement([(l1, l2) for _, l1, l2 in allp])
    print(f"\n=== {mode}-session ===")
    print(f"comparable node pairs: {tot}; raw agreement {ok/max(tot,1):.4f}; "
          f"pooled a = {invert(ok/max(tot,1)):.4f}")

    per_b = {}
    print(f"{'|gap| bucket':>22} {'n':>6} {'agree':>7} {'a':>7}")
    for k in range(len(BUCKETS) - 1):
        sel = [(l1, l2) for g, l1, l2 in allp if bucket_of(g) == k]
        o2, t2 = agreement(sel)
        lab = f"[{BUCKETS[k]:.0e},{BUCKETS[k+1]:.0e})"
        if t2 >= a.min_bucket:
            per_b[k] = invert(o2 / t2)
            print(f"{lab:>22} {t2:6d} {o2/t2:7.4f} {per_b[k]:7.4f}")
        else:
            print(f"{lab:>22} {t2:6d} {'--':>7} {'--':>7}  (below min-bucket)")
    # unestimable buckets inherit from the nearest SMALLER gap; never from the pool
    filled, last = {}, None
    for k in range(len(BUCKETS) - 1):
        if k in per_b:
            last = per_b[k]
        filled[k] = last if last is not None else 0.5
    for k in range(1, len(BUCKETS) - 1):        # monotonise: harder is never easier
        filled[k] = max(filled[k], filled[k - 1]) if filled[k - 1] <= filled[k] else filled[k]

    # transport to the real pair distributions
    for name, path in (("value pairs (lookahead)", "phase1/value_pairs_runsplit.jsonl"),
                       ("decision pairs (siblings)", "phase1/decision_pairs_runsplit.jsonl")):
        try:
            w = collections.Counter()
            n = 0
            for l in open(path):
                p = json.loads(l)
                gb, gw = (fin(cards[p["better"]]["label"].get("graded"))
                          if p["better"] in cards else None), \
                         (fin(cards[p["worse"]]["label"].get("graded"))
                          if p["worse"] in cards else None)
                if gb is None or gw is None:
                    continue
                w[bucket_of(abs(gb - gw))] += 1
                n += 1
            ceil = sum(w[k] * filled[k] for k in w) / max(n, 1)
            small = sum(w[k] for k in w if k <= 1) / max(n, 1)
            print(f"  ceiling transported to {name:26s} = {ceil:.4f}  "
                  f"(n={n}, {small:.1%} of pairs in the two smallest-gap buckets)")
        except FileNotFoundError:
            pass

    # bootstrap over nodes within task
    if mode == "cross":
        g = random.Random(7)
        ids = sorted(usable)
        draws = []
        for _ in range(300):
            keep = set(g.choices(ids, k=len(ids)))
            sel = [(l1, l2) for t, v in data.items() for gp, l1, l2 in v]
            o3, t3 = agreement(sel)
            draws.append(invert(o3 / max(t3, 1)))
        draws.sort()
        print(f"  node bootstrap (300) pooled a: "
              f"[{draws[7]:.4f}, {draws[292]:.4f}]")

print("\n--- the quotable form ---")
print("Do not quote the point estimate; quote the margin. If the true ceiling were 0.70,")
print("two independent measurements would have to agree only about 58% of the time.")
print("Compare that with the observed cross-session agreement printed above.")
print("Measured predictors for reference: tfidf 0.6795 / 1.5B 0.6493 / self-report 0.7780.")
