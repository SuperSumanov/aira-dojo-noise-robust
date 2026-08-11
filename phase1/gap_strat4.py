"""Gap-stratified evaluation on the object search actually decides: sibling pairs at budget 0.

Why this set and not the lookahead pairs the first two passes used:

  * its label margin IS an own-score margin (gap_raw equals |graded diff| on 100.00% of rows,
    and the recorded order agrees with the current corpus on 100.00%), so the regrade-derived
    noise ceiling applies EXACTLY here rather than as an upper bound;
  * it carries no reversed conflicts and no duplicate rows once the budget is fixed, unlike
    the pooled sibling file where 12.14% of rows sit in a both-directions conflict;
  * it is the decision search faces -- which of these candidates to spend an execution on --
    rather than a retrospective comparison of two subtrees;
  * and 55.9% of it lies below gap 1e-2, against 19.8% for the lookahead pairs. That
    difference IS the distribution-shift argument, measured rather than asserted.

The predictors are the identical models from the headline table, trained on the value-pair
train split and only queried here; value-TRAIN and decision-TEST share zero runs.

Usage: python phase1/gap_strat4.py
"""
import collections, glob, json, math, random, statistics

EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, float("inf")]
HARD = 1e-2
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
PP = json.load(open("phase1/perpair_decision.json"))
G, task_of_card = {}, {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    try:
        v = float(d.get("label", {}).get("graded"))
        G[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        G[d["id"]] = None


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def bucket(g):
    for k in range(len(EDGES) - 1):
        if EDGES[k] <= g < EDGES[k + 1]:
            return k
    return len(EDGES) - 2


# ---- ceiling curve; here it is exact, not an upper bound -------------------------
reps, orig, task_of = collections.defaultdict(list), {}, {}
for path in sorted(glob.glob("phase1/regrade_results*.jsonl")):
    for l in open(path):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        cid = d.get("card_id")
        if not cid:
            continue
        task_of[cid] = d.get("competition")
        o = fin(d.get("orig_graded"))
        if o is not None:
            orig[cid] = o
        s = fin(d.get("score"))
        if s is not None:
            reps[cid].append(s)
usable = {c: v for c, v in reps.items() if len(v) >= 2 and c in orig}


def lab(x, y, t):
    return None if x == y else int((x < y) if ORI.get(t, False) else (x > y))


obs = collections.defaultdict(lambda: [0, 0])
bt = collections.defaultdict(list)
for c in usable:
    bt[task_of[c]].append(c)
for t, cs in bt.items():
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            ci, cj = cs[i], cs[j]
            mi, mj = statistics.mean(usable[ci]), statistics.mean(usable[cj])
            l1, l2 = lab(orig[ci], orig[cj], t), lab(mi, mj, t)
            if l1 is None or l2 is None:
                continue
            k = bucket(abs(mi - mj))
            obs[k][0] += int(l1 == l2)
            obs[k][1] += 1


def invert(p):
    return 0.5 if p is None or p <= 0.5 else (1 + math.sqrt(max(0.0, 2 * p - 1))) / 2


ceil, last = {}, None
for k in range(len(EDGES) - 1):
    o, n = obs[k]
    if n >= 25:
        last = invert(o / n)
    ceil[k] = last if last is not None else 0.5

rows = []
for l in open("phase1/decision_clean_b0.jsonl"):
    p = json.loads(l)
    g = fin(p.get("gap_raw"))
    if g is None:
        continue
    rows.append({"key": p["better"] + "|" + p["worse"], "task": p["task"], "gap": g,
                 "k": bucket(g), "run": RUN.get(p["better"]),
                 "parent": p.get("parent"), "set_size": p.get("set_size")})
print(f"sibling pairs at budget 0 (test split): {len(rows)}; "
      f"tasks {len(set(r['task'] for r in rows))}; "
      f"parents {len(set(r['parent'] for r in rows))}")

CORE = [p for p in ["rm_1.5b_2048_SIBSUBSET", "self_report", "tfidf_lr", "static_gbm",
                    "static_lr", "embed_frozen_0.5b", "code_len", "n_lines", "random"]
        if p in PP]
ORDER = CORE + [p for p in sorted(PP) if p not in CORE]


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


def report(sub, title, preds=None):
    preds = preds or ORDER
    n = len(sub)
    if not n:
        print(f"\n{title}: EMPTY")
        return
    wc = sum(ceil[r["k"]] for r in sub) / n
    print(f"\n{title}\n   n={n}   ceiling (EXACT on this set) = {wc:.4f}")
    print(f"   {'predictor':24s} {'acc':>7} {'task-clustered':>19} "
          f"{'parent-clustered':>19} {'n':>5} {'cov':>5}")
    for name in preds:
        d_t, d_p = collections.defaultdict(list), collections.defaultdict(list)
        for r in sub:
            x = PP[name].get(r["key"])
            if x is None:
                continue
            d_t[r["task"]].append(float(x))
            d_p[r["parent"]].append(float(x))
        v = [x for vs in d_t.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_t)
        plo, phi = boot(d_p)
        star = "  *" if (lo > 0.5 and plo > 0.5) else ""
        print(f"   {name:24s} {sum(v)/len(v):7.4f} [{lo:6.4f},{hi:6.4f}] "
              f"[{plo:6.4f},{phi:6.4f}] {len(v):5d} {len(v)/n:5.2f}{star}")
    print("   * = both clustered intervals exclude 0.5   "
          "(parent = the sibling set, the true independent unit here)")


print("\n" + "=" * 96)
print("GAP-STRATIFIED, SIBLING DECISIONS AT BUDGET 0")
print("=" * 96)
print(f"{'bucket':>16} {'n':>5} {'ceil':>6} " + " ".join(f"{p[:11]:>11}" for p in ORDER))
for k in range(len(EDGES) - 1):
    sub = [r for r in rows if r["k"] == k]
    if not sub:
        continue
    cells = []
    for name in ORDER:
        v = [PP[name].get(r["key"]) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):11.4f}" if v else f"{'--':>11}")
    print(f"[{EDGES[k]:.0e},{EDGES[k+1]:.0e}) {len(sub):5d} {ceil[k]:6.3f} " +
          " ".join(cells))

hard = [r for r in rows if r["gap"] < HARD]
report(hard, "HARD  gap < 1e-2   -- the region search mostly operates in")
report([r for r in rows if r["gap"] >= HARD], "EASY  gap >= 1e-2")

print("\n" + "=" * 96)
print("SAME-POOL over the core predictors (the judges cover ~10% by design and are "
      "excluded here)")
print("=" * 96)
common = [r for r in rows if all(PP[p].get(r["key"]) is not None for p in CORE)]
print(f"pairs answered by all {len(CORE)} core predictors: {len(common)} "
      f"({len(common)/max(len(rows),1):.1%})")
ch = [r for r in common if r["gap"] < HARD]
report(ch, "HARD  same-pool", CORE)
report([r for r in common if r["gap"] >= HARD], "EASY  same-pool", CORE)

if ch and "tfidf_lr" in PP:
    print("\npaired differences vs tfidf_lr in the same-pool hard region")
    for name in CORE:
        if name == "tfidf_lr":
            continue
        d = collections.defaultdict(list)
        pos = neg = 0
        for r in ch:
            a, b = PP[name].get(r["key"]), PP["tfidf_lr"].get(r["key"])
            if a is None or b is None:
                continue
            d[r["parent"]].append(float(a) - float(b))
            pos += int(a > b)
            neg += int(a < b)
        v = [x for vs in d.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d)
        n = pos + neg
        p = (sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) * 2 / 2 ** n
             if 0 < n <= 900 else float("nan"))
        print(f"   {name:24s} - tfidf = {sum(v)/len(v):+.4f} [{lo:+.4f},{hi:+.4f}] "
              f"discordant {pos}/{neg} p={p:.2e}"
              + ("  SIG" if (lo > 0 or hi < 0) else ""))

print("\n" + "=" * 96)
print("KILL CONDITIONS on the clean set")
print("=" * 96)
byt = collections.Counter(r["task"] for r in hard)
top = byt.most_common(1)[0] if byt else ("-", 0)
print(f"K1  hard pairs = {len(hard)} (need >= 400) -> "
      f"{'PASS' if len(hard) >= 400 else 'FAIL'}")
print(f"    dominant task {top[0][:34]} = {top[1]/max(len(hard),1):.1%} (need <= 85%) -> "
      f"{'PASS' if top[1]/max(len(hard),1) <= 0.85 else 'FAIL'}")
best = CORE[0] if CORE else None
print(f"    {'task':44s} {'n':>5} " + " ".join(f"{p[:10]:>10}" for p in CORE[:4]))
for t, c in byt.most_common(10):
    sub = [r for r in hard if r["task"] == t]
    cells = []
    for name in CORE[:4]:
        v = [PP[name].get(r["key"]) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):10.4f}" if v else f"{'--':>10}")
    print(f"    {t[:44]:44s} {c:5d} " + " ".join(cells))
big = [t for t, c in byt.items() if c >= 60]
print(f"K2  tasks with n>=60 in the hard region: {len(big)} {big} (need >= 3)")
if len(big) >= 3:
    accs = []
    for t in big:
        sub = [r for r in hard if r["task"] == t]
        v = [PP[best].get(r["key"]) for r in sub]
        v = [x for x in v if x is not None]
        if v:
            accs.append((t, sum(v) / len(v)))
    hi = [t for t, x in accs if x > 0.55]
    lo = [t for t, x in accs if x < 0.45]
    print(f"    above 0.55: {len(hi)}; below 0.45: {len(lo)} -> "
          f"{'FAIL (not one phenomenon)' if hi and lo else 'PASS (consistent)'}")
else:
    print(f"    -> CANNOT ASSESS (their condition needs >=3)")
wc = sum(ceil[r["k"]] for r in hard) / max(len(hard), 1)
print(f"K3  hard-region ceiling = {wc:.4f} (need >= 0.65), EXACT on this set -> "
      f"{'PASS' if wc >= 0.65 else 'FAIL'}")
