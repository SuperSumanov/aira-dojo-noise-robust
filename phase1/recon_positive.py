"""Reconnaissance for a positive result: three axes where self-report is structurally absent.

Every experiment so far asked "rank nodes better than X", and X = the agent's own reported
validation score, which is free and has weighted |rho| = 0.81. We kept competing on its home
turf. A positive result can only live where the self-report does not exist or cannot apply:

  A REPAIR-WORTHINESS. A crashed node has NO score at all -- self-report is undefined, not
    merely weak. Yet the search must decide whether to spend a debug step on it. Measure:
    how often crashes happen, how often they get repaired, and whether repair outcome VARIES
    (no variance -> nothing to learn -> axis dead).

  B SELF-REPORT TRUSTWORTHINESS. Predicting "is this node's own reported score lying" is
    self-referentially unavailable to the self-report. Measure: does the lie magnitude have
    within-task variance (beyond the known between-task rho spectrum), i.e. is there a
    per-node signal at all, or is unreliability purely a task-level constant?

  C RUN-LEVEL EARLY TERMINATION. All prior work was node-level pairwise; the unit that is
    actually independent is the RUN (515 of them). "Will this run still improve?" is
    forward-looking where best-so-far is backward-looking. Measure the HEADROOM: if runs
    plateau immediately, there is no decision to make and the axis is dead.

Each block prints a GO/DEAD line with the number that decides it. Zero GPU.

Usage: python phase1/recon_positive.py [cards.jsonl]
"""
import collections, json, math, statistics, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current_v7.jsonl"
ORI = json.load(open("phase1/task_orientation.json"))

cards = {}
for l in open(PATH):
    d = json.loads(l)
    cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)
print(f"corpus: {len(cards)} cards, {len({d['run_id'] for d in cards.values()})} runs\n")


def is_crash(d):
    e = d["obs"].get("error")
    return e not in (None, "None", "", "null")


def sr_of(d):
    try:
        return float(d["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- A
print("=" * 78)
print("AXIS A -- repair-worthiness (self-report undefined by construction)")
print("=" * 78)
crashed = [c for c, d in cards.items() if is_crash(d)]
nosr = [c for c, d in cards.items() if sr_of(d) is None]
print(f"crashed nodes (obs.error set): {len(crashed)} ({len(crashed)/len(cards):.1%})")
print(f"nodes with NO self-report:     {len(nosr)} ({len(nosr)/len(cards):.1%})")
ops = collections.Counter(d["lineage"].get("op") for d in cards.values())
print(f"operators: {dict(ops)}")

# a crash that has children = the search chose to spend a step on it
repaired = [c for c in crashed if kids.get(c)]
print(f"crashed nodes that got children (repair attempted): {len(repaired)}")
outcomes = []
for c in repaired:
    ch = [x for x in kids[c] if x in cards]
    gs = [cards[x]["label"]["graded"] for x in ch
          if cards[x]["label"].get("graded") is not None]
    if gs:
        t = cards[c]["task"]["name"]
        best = min(gs) if ORI.get(t, False) else max(gs)
        outcomes.append((c, t, best, len(ch)))
print(f"  of those, with at least one GRADED child: {len(outcomes)}")
if outcomes:
    by_t = collections.defaultdict(list)
    for c, t, b, n in outcomes:
        by_t[t].append(b)
    # does repair outcome vary WITHIN a task? no variance -> nothing to predict
    usable = {t: v for t, v in by_t.items() if len(v) >= 20}
    print(f"  tasks with >=20 repaired-and-graded crashes: {len(usable)}")
    for t, v in sorted(usable.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"    {t[:40]:40s} n={len(v):4d}  child-best sd={statistics.pstdev(v):.4f}  "
              f"range=[{min(v):.3f}, {max(v):.3f}]")
    tot = sum(len(v) for v in usable.values())
    print(f"  --> usable repair decisions: {tot}")
    print(f"  VERDICT A: {'GO' if tot >= 300 else 'DEAD'} "
          f"(need >=300 graded repair outcomes across >=3 tasks; got {tot}/{len(usable)})")
else:
    print("  VERDICT A: DEAD (no graded repair outcomes)")

# ---------------------------------------------------------------- B
print()
print("=" * 78)
print("AXIS B -- is self-report unreliability a per-NODE signal or a per-TASK constant?")
print("=" * 78)


def z(vals):
    n = len(vals)
    mu = sum(vals) / n
    sd = (sum((v - mu) ** 2 for v in vals) / n) ** 0.5
    return [(v - mu) / sd for v in vals] if sd > 1e-12 else [0.0] * n


tot_var, within_var = 0.0, 0.0
rows = []
for t in {d["task"]["name"] for d in cards.values()}:
    sub = [(sr_of(d), d["label"].get("graded"), cid)
           for cid, d in cards.items() if d["task"]["name"] == t]
    sub = [(s, g, c) for s, g, c in sub if s is not None and g is not None]
    if len(sub) < 40:
        continue
    sgn = -1.0 if ORI.get(t, False) else 1.0
    zs = z([sgn * s for s, _, _ in sub])
    zg = z([sgn * g for _, g, _ in sub])
    gaps = [abs(a - b) for a, b in zip(zs, zg)]
    rows.append((t, len(sub), statistics.mean(gaps), statistics.pstdev(gaps)))
print(f"{'task':44s} {'n':>5} {'mean|gap|':>10} {'sd|gap|':>8}")
for t, n, m, s in sorted(rows, key=lambda r: -r[2]):
    print(f"{t[:44]:44s} {n:5d} {m:10.3f} {s:8.3f}")
if rows:
    grand = statistics.mean([m for _, _, m, _ in rows])
    within = statistics.mean([s for _, _, _, s in rows])
    between = statistics.pstdev([m for _, _, m, _ in rows])
    print(f"\nmean |gap| = {grand:.3f}; WITHIN-task sd = {within:.3f}; "
          f"BETWEEN-task sd = {between:.3f}")
    ratio = within / between if between > 1e-9 else float("inf")
    print(f"within/between = {ratio:.2f}")
    print(f"  VERDICT B: {'GO' if ratio >= 1.5 else 'WEAK'} "
          f"(need within-task variation to dominate; else unreliability is just a task constant)")

# ---------------------------------------------------------------- C
print()
print("=" * 78)
print("AXIS C -- run-level headroom: is there anything to decide by killing runs early?")
print("=" * 78)
runs = collections.defaultdict(list)
for cid, d in cards.items():
    g = d["label"].get("graded")
    if g is not None:
        runs[d["run_id"]].append((d["lineage"].get("step") or 0, g, d["task"]["name"]))
print(f"runs with >=1 graded node: {len(runs)}")
sizes = sorted(len(v) for v in runs.values())
print(f"graded nodes per run: median {sizes[len(sizes)//2]}, "
      f"p90 {sizes[int(0.9*len(sizes))]}, max {sizes[-1]}")

for K in (3, 5, 8):
    elig = {r: sorted(v) for r, v in runs.items() if len(v) > K}
    if not elig:
        continue
    improved, gains, fracs = 0, [], []
    for r, v in elig.items():
        t = v[0][2]
        lower = ORI.get(t, False)
        pick = min if lower else max
        early = pick(g for _, g, _ in v[:K])
        final = pick(g for _, g, _ in v)
        # normalise the gain by the run's own spread so tasks are comparable
        spread = max(g for _, g, _ in v) - min(g for _, g, _ in v)
        better = (final < early - 1e-12) if lower else (final > early + 1e-12)
        if better:
            improved += 1
            if spread > 1e-12:
                fracs.append(abs(final - early) / spread)
        gains.append(abs(final - early))
    print(f"\n  K={K}: {len(elig)} runs have >{K} graded nodes")
    print(f"    runs that IMPROVE after step {K}: {improved} ({improved/len(elig):.1%})")
    if fracs:
        print(f"    among improvers, gain as fraction of run spread: "
              f"median {statistics.median(fracs):.2f}")
    print(f"    mean absolute late gain: {statistics.mean(gains):.4f}")
K = 5
elig = {r: sorted(v) for r, v in runs.items() if len(v) > K}
if elig:
    imp = sum(1 for r, v in elig.items()
              if (min if ORI.get(v[0][2], False) else max)(g for _, g, _ in v)
              != (min if ORI.get(v[0][2], False) else max)(g for _, g, _ in v[:K]))
    print(f"\n  VERDICT C: {'GO' if len(elig) >= 150 and 0.2 <= imp/len(elig) <= 0.8 else 'CHECK'} "
          f"(need >=150 eligible runs and a non-degenerate improve rate; "
          f"got {len(elig)} runs, {imp/len(elig):.1%} improve)")
