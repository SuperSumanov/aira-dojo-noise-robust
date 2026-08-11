"""Where do the 293 self-contradicting sibling pairs come from?

A sibling pair's label IS the order of the two nodes' own scores. If the current corpus
disagrees with the recorded order, one of three things is true, and they have very different
consequences:

  ORIENTATION   the higher-is-better flag is wrong for that task -> then essentially ALL of
                that task's pairs should contradict, not 13% of them.
  CORPUS DRIFT  v7 -> v8 changed a card's graded value -> the pair files were built against
                numbers that no longer exist, and every downstream label is suspect.
  PRECISION     the two scores were always nearly equal and a rounding-level difference
                flips the order -> benign as a bug, but it means the labels in the small-gap
                region are not stable, which is itself a finding about that region.

All three are decidable. Print, for the contradicting pairs: their gap_raw distribution
(precision), the per-task contradiction RATE rather than count (orientation), and a direct
v7-vs-v8 comparison of graded for every shared card (drift).
"""
import collections, json, math

ORI = json.load(open("phase1/task_orientation.json"))


def load(p):
    m = {}
    for l in open(p):
        d = json.loads(l)
        m[d["id"]] = d
    return m


v7, v8 = load("phase1/cards_current_v7.jsonl"), load("phase1/cards_current_v8.jsonl")


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


shared = set(v7) & set(v8)
diff = []
for c in shared:
    a, b = fin(v7[c]["label"].get("graded")), fin(v8[c]["label"].get("graded"))
    if a is None and b is None:
        continue
    if a is None or b is None or abs(a - b) > 1e-12:
        diff.append((c, a, b))
print(f"cards in v7 {len(v7)}, in v8 {len(v8)}, shared {len(shared)}")
print(f"CORPUS DRIFT: shared cards whose graded changed v7->v8: {len(diff)}")
for c, a, b in diff[:8]:
    print(f"   {c[:52]:54s} {a} -> {b}")

print("\nper-task contradiction RATE for sibling pairs "
      "(orientation error would show ~100%)")
tot = collections.Counter()
bad = collections.Counter()
gaps_bad, gaps_all = [], []
for l in open("phase1/decision_pairs_runsplit.jsonl"):
    p = json.loads(l)
    b, w, t = p["better"], p["worse"], p["task"]
    if b not in v8 or w not in v8:
        continue
    gb, gw = fin(v8[b]["label"].get("graded")), fin(v8[w]["label"].get("graded"))
    if gb is None or gw is None or gb == gw:
        continue
    tot[t] += 1
    g = fin(p.get("gap_raw"))
    if g is not None:
        gaps_all.append(g)
    ok = (gb < gw) if ORI.get(t, False) else (gb > gw)
    if not ok:
        bad[t] += 1
        if g is not None:
            gaps_bad.append(g)
print(f"   {'task':46s} {'pairs':>7} {'contra':>7} {'rate':>7} {'lower_better':>13}")
for t in sorted(tot, key=lambda x: -bad[x]):
    print(f"   {t[:46]:46s} {tot[t]:7d} {bad[t]:7d} {bad[t]/tot[t]:7.2%} "
          f"{str(ORI.get(t)):>13}")

for nm, g in (("contradicting", gaps_bad), ("all", gaps_all)):
    if not g:
        continue
    g = sorted(g)
    q = lambda f: g[min(int(f * len(g)), len(g) - 1)]
    print(f"\nPRECISION: gap_raw of {nm} sibling pairs (n={len(g)})")
    print(f"   p10={q(.10):.6f}  p25={q(.25):.6f}  median={q(.50):.6f}  "
          f"p75={q(.75):.6f}  p90={q(.90):.6f}")
    print(f"   share with gap_raw < 1e-2: {sum(1 for x in g if x < 1e-2)/len(g):.1%}")

# how many decimals does graded actually carry?
dec = collections.Counter()
for c in list(v8)[:4000]:
    s = str(v8[c]["label"].get("graded"))
    if "." in s and "e" not in s.lower():
        dec[len(s.split(".")[1])] += 1
print(f"\ndecimal places present in graded (sample): {dict(sorted(dec.items()))}")
