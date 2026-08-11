"""Follow-up on the gap mismatch: is any of it stale labels rather than a different quantity?

Two separate explanations produce the same mismatch and have opposite consequences:

  (a) DIFFERENT QUANTITY. For lookahead pairs the label is defined by the subtree's best
      score, so gap_raw is a subtree-best margin and the nodes' own scores are simply a
      different variable. Nothing is broken; the stratifier was just indexed wrong, and the
      fix is to stratify on gap_raw.

  (b) STALE LABELS. The pairs were built against an older grade for the same node, and the
      corpus has since been regraded. Then some pairs' better/worse assignment no longer
      matches the current scores -- and a label that disagrees with its own corpus is a
      correctness problem, not an indexing one.

(b) is distinguishable from (a) by the SIGN. Under (a) the magnitudes differ but the current
scores need not contradict the recorded order. Under (b) some pairs flip outright. Sibling
(decision) pairs are the clean probe: their label IS the own-score order by construction,
so any flip there is stale-label drift, full stop.
"""
import collections, glob, json, math

ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

regraded = set()
for p in sorted(glob.glob("phase1/regrade_results*.jsonl")):
    for l in open(p):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        if d.get("card_id"):
            regraded.add(d["card_id"])
print(f"nodes touched by a regrade: {len(regraded)}")


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


for name in ("decision_pairs_runsplit.jsonl", "hits_l1_uncapped.jsonl"):
    n = flip = tie = 0
    flip_regraded = flip_clean = 0
    per_task = collections.Counter()
    for l in open("phase1/" + name):
        p = json.loads(l)
        b, w, t = p["better"], p["worse"], p["task"]
        if b not in cards or w not in cards:
            continue
        gb, gw = fin(cards[b]["label"].get("graded")), fin(cards[w]["label"].get("graded"))
        if gb is None or gw is None:
            continue
        n += 1
        if gb == gw:
            tie += 1
            continue
        # lower_is_better tasks: "better" should have the SMALLER graded value
        ok = (gb < gw) if ORI.get(t, False) else (gb > gw)
        if not ok:
            flip += 1
            per_task[t] += 1
            if b in regraded or w in regraded:
                flip_regraded += 1
            else:
                flip_clean += 1
    print(f"\n{name}: n={n}")
    print(f"  recorded order CONTRADICTED by current graded scores: {flip} "
          f"({flip/max(n,1):.2%})")
    print(f"  exact ties under current scores: {tie} ({tie/max(n,1):.2%})")
    print(f"  of the contradictions, at least one endpoint regraded: {flip_regraded}; "
          f"neither endpoint regraded: {flip_clean}")
    if per_task:
        print(f"  by task: {dict(per_task.most_common(8))}")
    print("  For sibling pairs a contradiction can only be stale labelling. For lookahead")
    print("  pairs it is expected -- the label is about the subtree, not the node.")

# ---------------------------------------------------------------------------------
# Can sibling pairs serve as the evaluation set at all?
#
# The predictors are trained on the value-pair TRAIN split. Scoring them on sibling pairs is
# only legitimate if the two files partition the same runs the same way. If a run sits in
# value-train and also in decision-test, the model has seen those nodes and the sibling
# numbers are contaminated. This is the same run-level leak that forced the corpus rebuild,
# so it gets checked before anything is built on top of it, not after.
RUN = json.load(open("phase1/card_run_map.json"))


def runs_of(path, split):
    out = set()
    for l in open("phase1/" + path):
        p = json.loads(l)
        if p.get("intask_split") != split:
            continue
        for e in (p["better"], p["worse"]):
            r = RUN.get(e)
            if r is not None:
                out.add(r)
    return out


vtr = runs_of("value_pairs_runsplit.jsonl", "train")
vte = runs_of("value_pairs_runsplit.jsonl", "test")
dtr = runs_of("decision_pairs_runsplit.jsonl", "train")
dte = runs_of("decision_pairs_runsplit.jsonl", "test")
print(f"\nrun-level split consistency")
print(f"  value  train runs {len(vtr)}   test runs {len(vte)}   "
      f"overlap {len(vtr & vte)}")
print(f"  decis. train runs {len(dtr)}   test runs {len(dte)}   "
      f"overlap {len(dtr & dte)}")
print(f"  value-TRAIN runs that also appear in decision-TEST: {len(vtr & dte)}  "
      f"<- must be 0 to score sibling pairs with value-trained models")
print(f"  value-TEST runs that also appear in decision-TEST: {len(vte & dte)}")
if vtr & dte:
    print(f"  offending runs (first 10): {sorted(vtr & dte)[:10]}")

