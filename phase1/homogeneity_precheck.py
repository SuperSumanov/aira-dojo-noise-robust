"""0-GPU precheck: does cross-generator transfer track how homogeneous a task's solutions are?

The cross-generator table has one outlier -- tps_dec keeps 0.687 while the other three fall to
~0.50. If that is because tps_dec's solution space is templated (everyone writes the same
gradient-boosting pipeline) then "transfer rate is predictable from solution diversity" is a
law, not an anecdote. With only 4 tasks we cannot fit anything; what we CAN check is whether
the ordering is even consistent. If the diversity ranking does not line up with the transfer
ranking on 4 points, spending GPU to collect 6-8 more tasks is not justified.

Diversity is measured three cheap ways, all on code only:
  import_entropy   Shannon entropy over imported top-level modules (which libraries get used)
  call_entropy     entropy over called function names (how the solution is assembled)
  pair_distance    mean pairwise Jaccard distance over identifier sets (how different two
                   solutions to the same task look)

Usage: python phase1/homogeneity_precheck.py cards_for_crossgen.jsonl
"""
import ast, collections, itertools, json, math, random, sys

path = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_for_crossgen.jsonl"

# measured cross-generator gap (DS held-out minus Qwen), job 8934, full FT + 2 epochs
GAP = {"spooky-author-identification": 32.7, "leaf-classification": 26.6,
       "random-acts-of-pizza": 17.5, "tabular-playground-series-dec-2021": 4.2}

by_task = collections.defaultdict(list)
for l in open(path):
    d = json.loads(l)
    t = d["task"]["name"]
    gen = "qwen" if t.startswith("QWEN::") else "deepseek"
    by_task[(t.replace("QWEN::", ""), gen)].append(d.get("code") or "")


def features(code):
    """(top-level imports, called names, identifiers) -- None if the code will not parse."""
    try:
        tree = ast.parse(code)
    except Exception:
        return None
    imps, calls, idents = set(), [], set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imps.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            imps.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call):
            f = n.func
            calls.append(f.attr if isinstance(f, ast.Attribute) else
                         (f.id if isinstance(f, ast.Name) else "?"))
        elif isinstance(n, ast.Name):
            idents.add(n.id)
    return imps, calls, idents


def entropy(counter):
    tot = sum(counter.values())
    if not tot: return 0.0
    return -sum((c / tot) * math.log2(c / tot) for c in counter.values() if c)


rng = random.Random(7)
rows = []
for (task, gen), codes in sorted(by_task.items()):
    feats = [f for f in (features(c) for c in codes) if f]
    if len(feats) < 10: continue
    imp_c, call_c = collections.Counter(), collections.Counter()
    for imps, calls, _ in feats:
        imp_c.update(imps); call_c.update(calls)
    sample = feats if len(feats) <= 60 else rng.sample(feats, 60)
    ds = []
    for a, b in itertools.combinations(sample, 2):
        ia, ib = a[2], b[2]
        if ia or ib:
            ds.append(1 - len(ia & ib) / len(ia | ib))
    rows.append((task, gen, len(feats), entropy(imp_c), entropy(call_c),
                 sum(ds) / len(ds) if ds else float("nan")))

print(f"{'task':40s} {'gen':9s} {'n':>4} {'import_H':>9} {'call_H':>8} {'pair_dist':>10} {'gap':>7}")
print("-" * 92)
for task, gen, n, ih, ch, pd in rows:
    g = f"{GAP.get(task, float('nan')):.1f}" if gen == "deepseek" else ""
    print(f"{task[:40]:40s} {gen:9s} {n:>4} {ih:>9.3f} {ch:>8.3f} {pd:>10.3f} {g:>7}")

print()
print("Ranking check (DeepSeek side only) -- does more diversity mean a bigger collapse?")
ds_rows = [r for r in rows if r[1] == "deepseek" and r[0] in GAP]
for label, idx in (("import_H", 3), ("call_H", 4), ("pair_dist", 5)):
    order = sorted(ds_rows, key=lambda r: r[idx])
    seq = " < ".join(f"{r[0][:14]}({GAP[r[0]]:.0f})" for r in order)
    gaps = [GAP[r[0]] for r in order]
    mono = all(gaps[i] <= gaps[i + 1] for i in range(len(gaps) - 1))
    print(f"  by {label:10s}: {seq}    {'MONOTONE' if mono else 'not monotone'}")
print("  (4 points land monotone by chance with p=1/12; three metrics were tried, so ~24%")
print("   chance at least one does. This is a hypothesis, not evidence.)")

# Entropy is biased upward by sample size, and the tasks differ 129..201 cards. Subsample every
# task to a common n and average over draws, so the ranking cannot be a sample-size artifact.
print()
NSUB = min(len(codes) for (t, g), codes in by_task.items()
           if g == "deepseek" and t in GAP)
print(f"Sample-size control: every task subsampled to n={NSUB}, 200 draws")
feat_cache = {}
for (task, gen), codes in by_task.items():
    if gen != "deepseek" or task not in GAP: continue
    feat_cache[task] = [f for f in (features(c) for c in codes) if f]

ctrl = []
for task, feats in feat_cache.items():
    vals = []
    for _ in range(200):
        draw = rng.sample(feats, min(NSUB, len(feats)))
        c = collections.Counter()
        for imps, _, _ in draw: c.update(imps)
        vals.append(entropy(c))
    vals.sort()
    ctrl.append((task, sum(vals) / len(vals), vals[5], vals[-6]))
for task, m, lo, hi in sorted(ctrl, key=lambda r: r[1]):
    print(f"  {task[:40]:40s} import_H={m:.3f}  [{lo:.3f}, {hi:.3f}]   gap={GAP[task]:.1f}")
g2 = [GAP[t] for t, _, _, _ in sorted(ctrl, key=lambda r: r[1])]
print("  ordering after control:",
      "MONOTONE" if all(g2[i] <= g2[i + 1] for i in range(len(g2) - 1)) else "not monotone")
