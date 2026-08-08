"""Recon round 3: stress the two survivors before committing GPU.

Round 2 left axis A (repair-worthiness) looking strong -- 875 repair attempts, 53.3% success,
8 tasks -- and axis C (run-level early stop) usable. Both need one more adversarial pass,
because "balanced overall" can still be "predict the task and you are done", and because a
decision task is only interesting if the incumbent policy is beatable.

A1 per-task base rates: if success rate swings wildly by task, a task-prior baseline eats
   most of the headroom and the learnable residual is small.
A2 what does the search ACTUALLY do now: how often does it retry a failure, how many times,
   and does persistence pay? That is the incumbent policy the paper must beat.
A3 cheap-feature signal on repair success, leave-one-task-out, controlling for task prior.

B' the untested configuration: our RMs are code-only and never saw the agent's own score.
   Before proposing "condition the model on the self-report", check the ceiling: among pairs
   the self-report gets WRONG, is the code-only RM right more often than chance? If not,
   conditioning cannot help and the whole idea dies for free.

Usage: python phase1/recon3.py [cards.jsonl]
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


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def sr_of(d):
    return fin(d["obs"].get("val_at_low"))


def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
                j += 1
            m = (i + j) / 2.0
            for k in range(i, j + 1):
                r[o[k]] = m
            i = j + 1
        return r
    a, b = rank(xs), rank(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


broken = {c for c, d in cards.items() if sr_of(d) is None}
repairs = [(c, cards[c]) for c, d in cards.items()
           if d["lineage"].get("op") == "Debug" and d["lineage"].get("parent_id") in broken]
print(f"repair attempts (Debug on a scoreless parent): {len(repairs)}\n")

print("=" * 78)
print("A1 -- per-task base rate: is 'predict the task' most of the answer?")
print("=" * 78)
byt = collections.defaultdict(lambda: [0, 0])
for c, d in repairs:
    t = d["task"]["name"]
    byt[t][0] += int(sr_of(d) is not None)
    byt[t][1] += 1
big = {t: v for t, v in byt.items() if v[1] >= 30}
print(f"{'task':44s} {'n':>5} {'repair-success rate':>20}")
for t, (k, n) in sorted(big.items(), key=lambda kv: -kv[1][1]):
    print(f"{t[:44]:44s} {n:5d} {k/n:20.3f}")
tot_n = sum(v[1] for v in big.values())
tot_k = sum(v[0] for v in big.values())
pri = tot_k / tot_n
# accuracy a task-prior classifier reaches: pick the majority class per task
prior_acc = sum(max(k, n - k) for k, n in big.values()) / tot_n
print(f"\npooled success {pri:.3f} over n={tot_n}; "
      f"per-task majority-class accuracy = {prior_acc:.3f}")
print(f"  a learned model must clear {prior_acc:.3f}, not 0.5")

print()
print("=" * 78)
print("A2 -- the incumbent policy: how does the search currently handle failures?")
print("=" * 78)
n_broken_with_kids = sum(1 for c in broken if kids.get(c))
print(f"scoreless nodes: {len(broken)}; of them retried at least once: {n_broken_with_kids} "
      f"({n_broken_with_kids/max(len(broken),1):.1%})")
retry_counts = collections.Counter(len(kids.get(c, [])) for c in broken)
print(f"retries per scoreless node: {dict(sorted(retry_counts.items())[:8])}")
# does persistence pay? among scoreless nodes retried k times, how often does ANY child score
pay = collections.defaultdict(lambda: [0, 0])
for c in broken:
    ch = [x for x in kids.get(c, []) if x in cards]
    if not ch:
        continue
    ok = any(sr_of(cards[x]) is not None for x in ch)
    pay[min(len(ch), 4)][0] += int(ok)
    pay[min(len(ch), 4)][1] += 1
print(f"{'#retries':>9} {'n':>6} {'P(at least one repair scores)':>32}")
for k in sorted(pay):
    a, b = pay[k]
    print(f"{k:>9} {b:6d} {a/b:32.3f}")

print()
print("=" * 78)
print("A3 -- cheap signal on repair success (leave-one-task-out Spearman)")
print("=" * 78)


def rfeat(parent, child):
    pc = parent.get("code") or ""
    tail = parent["obs"].get("stdout_tail") or ""
    low = tail.lower()
    return {
        "parent_code_len": float(len(pc)),
        "parent_runtime": float(parent["obs"].get("runtime_s") or 0),
        "tail_len": float(len(tail)),
        "has_traceback": float("traceback" in low),
        "is_oom": float("out of memory" in low or "oom" in low),
        "is_timeout": float("timeout" in low or "timelimit" in low),
        "is_keyerr": float("keyerror" in low or "valueerror" in low
                           or "typeerror" in low),
        "depth": float(parent["lineage"].get("depth") or 0),
        "n_prior_sibs": float(parent["lineage"].get("n_siblings") or 0),
    }


rows = []
for c, d in repairs:
    p = cards.get(d["lineage"]["parent_id"])
    if p is None:
        continue
    rows.append((d["task"]["name"], int(sr_of(d) is not None), rfeat(p, d)))
FN = list(rows[0][2].keys())
agg = {f: [] for f in FN}
for t in big:
    sub = [r for r in rows if r[0] == t]
    if len(sub) < 30:
        continue
    ys = [float(r[1]) for r in sub]
    if statistics.pstdev(ys) < 1e-9:
        continue
    for f in FN:
        xs = [r[2][f] for r in sub]
        if statistics.pstdev(xs) > 1e-12:
            agg[f].append(spearman(xs, ys))
print(f"{'feature':18s} {'mean rho':>10} {'tasks':>6}")
best = []
for f in FN:
    if agg[f]:
        m = statistics.mean(agg[f])
        best.append((abs(m), f, m))
        print(f"{f:18s} {m:10.3f} {len(agg[f]):6d}")
best.sort(reverse=True)
if best:
    print(f"\nstrongest cheap feature: {best[0][1]} rho={best[0][2]:+.3f}")

print()
print("=" * 78)
print("B' -- ceiling check: where the self-report is WRONG, is the code-only RM right?")
print("=" * 78)
flipf = {}
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "test":
        flipf[(p["better"], p["worse"])] = True
both = [0, 0]
srwrong = [0, 0]
for l in open("phase1/hits_l1_runsplit.jsonl"):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    sb, sw = sr_of(cards[b]), sr_of(cards[w])
    if sb is None or sw is None or sb == sw:
        continue
    s_ok = int((sb < sw) if ORI.get(h["task"], False) else (sb > sw))
    both[0] += h["hit"]
    both[1] += 1
    if not s_ok:
        srwrong[0] += h["hit"]
        srwrong[1] += 1
print(f"covered pairs: {both[1]}, RM overall {both[0]/both[1]:.4f}")
n, k = srwrong[1], srwrong[0]
se = math.sqrt(max(k/n*(1-k/n), 1e-12)/n)
print(f"pairs the self-report gets WRONG: {n}")
print(f"  RM correct on them: {k}/{n} = {k/n:.4f} +- {se:.4f}")
lo = k/n - 1.96*se
print(f"  95% CI lower bound {lo:.4f}")
print(f"  VERDICT B': {'GO' if lo > 0.5 else 'DEAD'} "
      f"(if the RM is at chance where the self-report fails, no amount of conditioning "
      f"or gating can add anything -- the information simply is not in the code)")
