"""Which score field actually defines the labels?

Established so far: v7->v8 changed no graded value (0 drift), and no task shows an
orientation-sized contradiction rate. Yet 6.6% of sibling pairs have a recorded order that
`label.graded` contradicts. With drift and orientation excluded, the remaining explanation
is that the pair files were never built on `label.graded` at all -- they were built on some
other numeric field on the card, and everything downstream that reads `graded` as "the true
score" has been reading a different variable than the one the labels encode.

This is decidable by brute force: enumerate every numeric field on a card, and for each ask
two questions on the sibling pairs, whose label is by construction the order of that field:
  reproduces the ORDER  -- how often the field's order matches the recorded better/worse
  reproduces gap_raw    -- how often |field_b - field_w| equals the recorded gap_raw
The field that defines the labels answers ~100% to both. Whatever we have been calling the
true score should be that field.
"""
import collections, json, math

ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

sample = next(iter(cards.values()))
print("card top-level keys:", sorted(sample.keys()))
for sec in ("label", "obs"):
    if isinstance(sample.get(sec), dict):
        print(f"  {sec}: {json.dumps(sample[sec])[:600]}")


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def numeric_fields(d, prefix=""):
    out = {}
    for k, v in d.items():
        p = prefix + k
        if isinstance(v, dict):
            out.update(numeric_fields(v, p + "."))
        elif isinstance(v, bool):
            continue
        elif fin(v) is not None:
            out[p] = fin(v)
    return out


keys = collections.Counter()
for c in list(cards.values())[:2000]:
    for k in numeric_fields(c):
        keys[k] += 1
cand = [k for k, n in keys.items() if n >= 1500]
print(f"\nnumeric fields present on >=75% of a 2000-card sample: {cand}")


def get(cid, path):
    d = cards[cid]
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return fin(d)


pairs = [json.loads(l) for l in open("phase1/decision_pairs_runsplit.jsonl")]
pairs = [p for p in pairs if p["better"] in cards and p["worse"] in cards]
print(f"\nsibling pairs usable: {len(pairs)}")
print(f"{'field':34s} {'n':>6} {'order OK':>9} {'gap match':>10} {'gap match (sign-free)':>22}")
for k in sorted(cand):
    n = ok = gm = gs = 0
    for p in pairs:
        a, b = get(p["better"], k), get(p["worse"], k)
        g = fin(p.get("gap_raw"))
        if a is None or b is None or g is None or a == b:
            continue
        n += 1
        if ((a < b) if ORI.get(p["task"], False) else (a > b)):
            ok += 1
        if abs(abs(a - b) - g) < 1e-6:
            gm += 1
        if abs(abs(a - b) - abs(g)) < 1e-4:
            gs += 1
    if n:
        print(f"{k:34s} {n:6d} {ok/n:9.2%} {gm/n:10.2%} {gs/n:22.2%}")
