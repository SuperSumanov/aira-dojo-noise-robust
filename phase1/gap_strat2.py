"""E-A: the full gap-stratified table, plus the two checks the first pass exposed.

The first pass (gap_strat.py) cleared all three pre-registered kill conditions, but it also
falsified the strongest form of the claim it was testing. In the hard region every cheap
decision-time predictor sits on chance, while SELF-REPORT does not: 0.5676 with a
run-clustered interval of [0.5103, 0.6618], which excludes 0.5. "Everything collapses" is
therefore wrong as stated. What survives is narrower and, if it holds up here, more useful:
cheap features carry no information at small true-score gaps, a post-execution signal still
does, and the label-noise ceiling there is 0.91 -- so the region is neither unlearnable nor
noise-dominated.

Two things could still explain that dissociation away, and both are checked before it is
believed:

  SAME-POOL   self-report is missing on 110 of the 709 hard pairs. A predictor evaluated on
              a different subset is not comparable. Everything is re-scored on the pairs
              where EVERY predictor answers, and differences get a paired interval.

  DROP-SPOOKY 73.5% of the hard region is one task. It passes the pre-registered <=85% bar,
              but a finding that lives inside a single task is a finding about that task.
              The hard region is recomputed with it removed.

Also fills in the predictors the first pass lacked (tfidf, static_gbm, the LLM judges, the
fine-tuned RMs) by reading the decisions predictor_suite now dumps.

Usage: python phase1/gap_strat2.py
"""
import collections, glob, json, math, random, statistics

EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, float("inf")]
HARD = 1e-2
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
PP = json.load(open("phase1/perpair_hits.json"))
cards = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d


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


# ---- ceiling curve, recomputed from our own regrades (identical to gap_strat.py) ----
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

# ---- the pair table -------------------------------------------------------------
rows = []
for l in open("phase1/hits_l1_uncapped.jsonl"):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    gb, gw = fin(cards[b]["label"].get("graded")), fin(cards[w]["label"].get("graded"))
    if gb is None or gw is None:
        continue
    rows.append({"b": b, "w": w, "key": b + "|" + w, "task": h["task"],
                 "gap": abs(gb - gw), "k": bucket(abs(gb - gw)), "run": RUN.get(b)})
print(f"pairs with a computable gap: {len(rows)}")
print(f"predictors dumped by predictor_suite: {sorted(PP)}")

ORDER = [p for p in ["random", "code_len", "n_lines", "n_cv", "n_ensemble", "static_lr",
                     "static_gbm", "tfidf_lr", "embed_frozen_05b", "rm_05b_2048",
                     "rm_1.5b_2048", "judge_ds8k", "judge_qwenmax", "self_report"]
         if p in PP]
ORDER += [p for p in sorted(PP) if p not in ORDER]


def hit(name, r):
    return PP[name].get(r["key"])


def boot(d, nb=3000, seed=7):
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


def report(sub, title, preds):
    n = len(sub)
    if not n:
        print(f"\n{title}: empty")
        return
    wc = sum(ceil[r["k"]] for r in sub) / n
    print(f"\n{title}: n={n}   recomputed ceiling = {wc:.4f}")
    print(f"   {'predictor':18s} {'acc':>7} {'task-clustered':>20} {'run-clustered':>20} "
          f"{'n':>6} {'cov':>6}")
    for name in preds:
        d_t, d_r = collections.defaultdict(list), collections.defaultdict(list)
        for r in sub:
            x = hit(name, r)
            if x is None:
                continue
            d_t[r["task"]].append(float(x))
            d_r[r["run"]].append(float(x))
        v = [x for vs in d_t.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_t)
        rlo, rhi = boot(d_r)
        star = "  *" if (rlo > 0.5 and lo > 0.5) else ""
        print(f"   {name:18s} {sum(v)/len(v):7.4f} [{lo:7.4f},{hi:7.4f}] "
              f"[{rlo:7.4f},{rhi:7.4f}] {len(v):6d} {len(v)/n:6.2f}{star}")
    print("   * = both intervals exclude 0.5")


print("\n" + "=" * 78)
print("E-A  FULL GAP-STRATIFIED TABLE (all predictors, all buckets)")
print("=" * 78)
print(f"{'bucket':>16} {'n':>6} {'ceil':>6} " + " ".join(f"{p[:12]:>12}" for p in ORDER))
for k in range(len(EDGES) - 1):
    sub = [r for r in rows if r["k"] == k]
    if not sub:
        continue
    cells = []
    for name in ORDER:
        v = [hit(name, r) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):12.4f}" if v else f"{'--':>12}")
    print(f"[{EDGES[k]:.0e},{EDGES[k+1]:.0e}) {len(sub):6d} {ceil[k]:6.3f} " +
          " ".join(cells))

hard = [r for r in rows if r["gap"] < HARD]
easy = [r for r in rows if r["gap"] >= HARD]
report(hard, "HARD  gap<1e-2  (all pairs, coverage differs per predictor)", ORDER)
report(easy, "EASY  gap>=1e-2 (all pairs, coverage differs per predictor)", ORDER)

# ---- SAME-POOL ------------------------------------------------------------------
print("\n" + "=" * 78)
print("SAME-POOL: only pairs every predictor answers, so coverage cannot explain a gap")
print("=" * 78)
common = [r for r in rows if all(hit(p, r) is not None for p in ORDER)]
print(f"pairs answered by all {len(ORDER)} predictors: {len(common)} "
      f"({len(common)/len(rows):.1%})")
ch = [r for r in common if r["gap"] < HARD]
report(ch, "HARD  gap<1e-2  SAME-POOL", ORDER)
report([r for r in common if r["gap"] >= HARD], "EASY  gap>=1e-2  SAME-POOL", ORDER)

if "self_report" in ORDER and ch:
    print("\npaired differences against self_report inside the same-pool hard region")
    print("(run-clustered bootstrap on the per-pair difference; the pairing removes the")
    print(" pair-difficulty variance that separate intervals leave in)")
    for name in ORDER:
        if name == "self_report":
            continue
        d = collections.defaultdict(list)
        for r in ch:
            d[r["run"]].append(float(hit(name, r)) - float(hit("self_report", r)))
        v = [x for vs in d.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d)
        sig = "  SIGNIFICANT" if (lo > 0 or hi < 0) else ""
        print(f"   {name:18s} - self_report = {sum(v)/len(v):+.4f} "
              f"[{lo:+.4f},{hi:+.4f}]{sig}")

# ---- DROP-SPOOKY ----------------------------------------------------------------
print("\n" + "=" * 78)
print("DROP-SPOOKY: the hard region without the task that supplies 73.5% of it")
print("=" * 78)
SP = "spooky-author-identification"
hs = [r for r in hard if r["task"] != SP]
byt = collections.Counter(r["task"] for r in hs)
print(f"remaining hard pairs: {len(hs)}; task mix: {dict(byt.most_common())}")
report(hs, "HARD  gap<1e-2  WITHOUT spooky", ORDER)
report([r for r in hard if r["task"] == SP], "HARD  gap<1e-2  spooky ONLY", ORDER)

print("\nper-task hard region, every task with n>=10 (the K2 evidence in full)")
print(f"   {'task':44s} {'n':>5} " + " ".join(f"{p[:11]:>11}" for p in ORDER))
for t, c in byt.most_common() + [(SP, sum(1 for r in hard if r["task"] == SP))]:
    sub = [r for r in hard if r["task"] == t]
    if len(sub) < 10:
        continue
    cells = []
    for name in ORDER:
        v = [hit(name, r) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):11.4f}" if v else f"{'--':>11}")
    print(f"   {t[:44]:44s} {len(sub):5d} " + " ".join(cells))

# ---- where do the pairs come from -----------------------------------------------
print("\n" + "=" * 78)
print("GAP DISTRIBUTION: the headline is a weighted average over THIS, and this is a")
print("property of how pairs were built, not of any decision a search faces")
print("=" * 78)
sib = 0
try:
    sibset = set()
    for l in open("phase1/decision_pairs_runsplit.jsonl"):
        p = json.loads(l)
        sibset.add(p["better"] + "|" + p["worse"])
    sg = [r["gap"] for r in rows if r["key"] in sibset]
    sib = len(sg)
    if sg:
        sg.sort()
        print(f"sibling (decision) pairs present here: {len(sg)}; "
              f"median gap {sg[len(sg)//2]:.5f}; "
              f"share below 1e-2 = {sum(1 for g in sg if g < HARD)/len(sg):.1%}")
except FileNotFoundError:
    pass
allg = sorted(r["gap"] for r in rows)
print(f"all evaluated pairs: {len(allg)}; median gap {allg[len(allg)//2]:.5f}; "
      f"share below 1e-2 = {sum(1 for g in allg if g < HARD)/len(allg):.1%}")
print("Read: if the sibling share below 1e-2 is materially higher than the evaluated share,")
print("the headline is measured on an easier distribution than search actually sees. If it")
print("is not, the honest claim is sensitivity, not 'search lives in the hard region'.")
