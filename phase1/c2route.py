"""Does C2 turn into a ROUTING RULE? The positive reading of the reliability-transfer result.

C2 established that a task's self-report reliability (rho between val_at_low and graded)
transfers: cheap statistics predict it before search runs. On its own that is a curiosity.
It becomes a positive, actionable result if the transferred rho predicts WHERE self-report
selection actually fails at the decision point -- because then a controller can route per
task: predicted-reliable -> trust the child's own val; predicted-unreliable -> spend real
executions. The v9 hard region just handed us candidate failure cases (whale 0.54, leaf
0.50 while most tasks sit at 0.6-0.9), so the correlation is testable rather than
hypothetical.

Test: per task, x = rho(val_at_low, graded) over all v9 cards; y = self-report sibling
accuracy in the b0 hard region (n>=10). Spearman + permutation p. If it holds, the routing
rule is validated out of its own construction sample.
"""
import collections, itertools, json, math, random

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


def rankv(v):
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


def spearman(x, y):
    a, b = rankv(x), rankv(y)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    den = math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))
    return num / den if den else 0.0


# x: per-task self-report reliability over the corpus
by_task = collections.defaultdict(list)
for cid, t in TASK.items():
    if G.get(cid) is not None and OWN.get(cid) is not None:
        by_task[t].append((OWN[cid], G[cid]))
rho = {}
for t, v in by_task.items():
    if len(v) >= 30:
        s = spearman([a for a, _ in v], [b for _, b in v])
        rho[t] = abs(s)   # orientation-free reliability

# y: self-report accuracy on hard-region sibling decisions
acc = collections.defaultdict(lambda: [0, 0])
for l in open("phase1/decision_clean_b0.jsonl"):
    p = json.loads(l)
    if float(p["gap_raw"]) >= 1e-2:
        continue
    a, b = OWN.get(p["better"]), OWN.get(p["worse"])
    if a is None or b is None or a == b:
        continue
    hit = int((a < b) if ORI.get(p["task"], False) else (a > b))
    acc[p["task"]][0] += hit
    acc[p["task"]][1] += 1

xs, ys, names = [], [], []
print(f"{'task':46s} {'rho(corpus)':>12} {'SR acc hard':>12} {'n':>5}")
for t in sorted(acc, key=lambda t: -acc[t][1]):
    o, n = acc[t]
    if n < 10 or t not in rho:
        continue
    xs.append(rho[t])
    ys.append(o / n)
    names.append(t)
    print(f"{t[:46]:46s} {rho[t]:12.4f} {o/n:12.4f} {n:5d}")

if len(xs) >= 5:
    r = spearman(xs, ys)
    n = len(xs)
    ge = tot = 0
    if math.factorial(n) <= 500000:
        for perm in itertools.permutations(range(n)):
            tot += 1
            if spearman(xs, [ys[i] for i in perm]) >= r:
                ge += 1
    else:
        rr = random.Random(7)
        idx = list(range(n))
        ge, tot = 1, 100001
        for _ in range(100000):
            rr.shuffle(idx)
            if spearman(xs, [ys[i] for i in idx]) >= r:
                ge += 1
    print(f"\nROUTING TEST: Spearman(rho_corpus, SR_hard_acc) = {r:+.4f} over {n} tasks, "
          f"perm p = {ge/tot:.4f}")
    print("Positive if clearly > 0: the transferable reliability statistic predicts where")
    print("self-report selection fails, so a controller can route trust per task.")
else:
    print(f"\nonly {len(xs)} tasks eligible -- underpowered")
