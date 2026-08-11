"""What rule actually assigned better/worse on sibling pairs?

Ruled out by measurement: corpus drift (0 across all four versions), stale labels (the
original corpus reproduces the identical 293 contradictions), orientation (no task near
100%), and every other numeric field (none reproduces gap_raw). `label.graded` matches the
order 93.4% and the gap 82.1% -- close enough that it IS the field, but not the whole rule.

So print the pairs and read them. Contradicting ones alongside agreeing ones, with every
quantity a builder could plausibly have keyed on, and the two subsets separated by whether
gap_raw reproduces |graded diff|. A rule that is 93% right is usually the right field with
one extra condition attached; the condition should be visible here.
"""
import collections, json, math

ORI = json.load(open("phase1/task_orientation.json"))
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


def g(c):
    return fin(cards[c]["label"].get("graded"))


def yn(c):
    return fin(cards[c]["label"].get("y_norm"))


rows = []
for l in open("phase1/decision_pairs_runsplit.jsonl"):
    p = json.loads(l)
    b, w = p["better"], p["worse"]
    if b not in cards or w not in cards:
        continue
    gb, gw, gr = g(b), g(w), fin(p.get("gap_raw"))
    if gb is None or gw is None or gr is None:
        continue
    lower = ORI.get(p["task"], False)
    ok = (gb < gw) if lower else (gb > gw)
    gapmatch = abs(abs(gb - gw) - gr) < 1e-6
    rows.append({"p": p, "gb": gb, "gw": gw, "gr": gr, "lower": lower,
                 "ok": ok, "gm": gapmatch})

x = collections.Counter((r["ok"], r["gm"]) for r in rows)
print("cross-tab of (order agrees with graded, gap_raw equals |graded diff|)")
for k in sorted(x, key=lambda t: (-x[t])):
    print(f"   order_ok={k[0]!s:5s} gap_match={k[1]!s:5s}  n={x[k]:5d} "
          f"({x[k]/len(rows):6.2%})")

print("\n--- CONTRADICTING examples ---")
print(f"{'task':30s} {'lower?':>6} {'graded(better)':>15} {'graded(worse)':>14} "
      f"{'|diff|':>10} {'gap_raw':>10} {'ynB':>7} {'ynW':>7} {'set':>4} {'tau':>6}")
for r in [r for r in rows if not r["ok"]][:14]:
    p = r["p"]
    print(f"{p['task'][:30]:30s} {str(r['lower']):>6} {r['gb']:15.5f} {r['gw']:14.5f} "
          f"{abs(r['gb']-r['gw']):10.5f} {r['gr']:10.5f} "
          f"{(yn(p['better']) if yn(p['better']) is not None else float('nan')):7.3f} "
          f"{(yn(p['worse']) if yn(p['worse']) is not None else float('nan')):7.3f} "
          f"{p.get('set_size', '-')!s:>4} {p.get('clears_tau')!s:>6}")

print("\n--- AGREEING but gap_raw does NOT match ---")
for r in [r for r in rows if r["ok"] and not r["gm"]][:14]:
    p = r["p"]
    print(f"{p['task'][:30]:30s} {str(r['lower']):>6} {r['gb']:15.5f} {r['gw']:14.5f} "
          f"{abs(r['gb']-r['gw']):10.5f} {r['gr']:10.5f} "
          f"{(yn(p['better']) if yn(p['better']) is not None else float('nan')):7.3f} "
          f"{(yn(p['worse']) if yn(p['worse']) is not None else float('nan')):7.3f} "
          f"{p.get('set_size', '-')!s:>4} {p.get('clears_tau')!s:>6}")

# does gap_raw equal the y_norm difference instead?
for nm, f in (("|y_norm diff|", lambda p: (yn(p["better"]), yn(p["worse"]))),):
    n = m = 0
    for r in rows:
        a, b = f(r["p"])
        if a is None or b is None:
            continue
        n += 1
        if abs(abs(a - b) - r["gr"]) < 1e-6:
            m += 1
    print(f"\ngap_raw == {nm} on {m}/{n}")

# is gap_raw perhaps |graded diff| computed at a DIFFERENT precision?
rounded = sum(1 for r in rows if abs(round(abs(r["gb"] - r["gw"]), 5) - r["gr"]) < 1e-9)
print(f"gap_raw == round(|graded diff|, 5) on {rounded}/{len(rows)} = "
      f"{rounded/len(rows):.2%}")
