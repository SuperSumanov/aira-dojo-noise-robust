"""Build a decision-pair evaluation set that is actually evaluable.

Why the existing file cannot be used as-is: 12.14% of its rows sit in a reversed conflict --
the same two sibling nodes labelled both ways -- and the field that distinguishes them is
`budget`. So the label is "which sibling is better AT THIS BUDGET", and a budget-blind
predictor is capped below 100% by construction. Mixing budgets and then reporting one
accuracy measures the mixture, not the predictor.

The fix is to fix the budget. For each budget separately:
  * drop exact duplicate rows (the same ordered pair repeated adds no information but does
    add weight, and 830 such rows are present)
  * verify no reversed conflict SURVIVES inside a single budget -- if one does, the budget
    is not the whole story and this needs re-thinking rather than patching
  * check whether gap_raw reduces to |graded diff| within the budget. Where it does, the
    label margin is an own-score margin and the regrade-derived noise ceiling applies
    EXACTLY rather than as an upper bound -- which is what the lookahead pairs could not
    give us.

Writes phase1/decision_clean_b<k>.jsonl per budget, test split only.
"""
import collections, json, math

ORI = json.load(open("phase1/task_orientation.json"))
G = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    try:
        v = float(d.get("label", {}).get("graded"))
        G[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        G[d["id"]] = None

rows = [json.loads(l) for l in open("phase1/decision_pairs_runsplit.jsonl")]
print(f"input rows: {len(rows)}")
by_budget = collections.defaultdict(list)
for p in rows:
    by_budget[p.get("budget")].append(p)
print(f"budgets present: "
      f"{ {k: len(v) for k, v in sorted(by_budget.items(), key=lambda kv: str(kv[0]))} }")

print(f"\n{'budget':>7} {'split':>6} {'rows':>6} {'dedup':>6} {'rev-conflict':>13} "
      f"{'gap==|graded|':>14} {'order ok':>9}")
for bud in sorted(by_budget, key=lambda x: (x is None, x)):
    for split in ("train", "test"):
        sub = [p for p in by_budget[bud] if p.get("intask_split") == split]
        if not sub:
            continue
        seen, ded = set(), []
        for p in sub:
            k = (p["better"], p["worse"])
            if k in seen:
                continue
            seen.add(k)
            ded.append(p)
        und = collections.defaultdict(set)
        for p in ded:
            und[tuple(sorted((p["better"], p["worse"])))].add((p["better"], p["worse"]))
        rev = sum(1 for v in und.values() if len(v) > 1)
        gm = ok = n = 0
        for p in ded:
            a, b = G.get(p["better"]), G.get(p["worse"])
            g = p.get("gap_raw")
            if a is None or b is None or g is None or a == b:
                continue
            n += 1
            gm += int(abs(abs(a - b) - float(g)) < 1e-6)
            ok += int((a < b) if ORI.get(p["task"], False) else (a > b))
        print(f"{str(bud):>7} {split:>6} {len(sub):6d} {len(ded):6d} {rev:13d} "
              f"{(gm/n if n else float('nan')):14.2%} {(ok/n if n else float('nan')):9.2%}")
        if split == "test":
            out = f"phase1/decision_clean_b{bud}.jsonl"
            with open(out, "w") as f:
                for p in ded:
                    f.write(json.dumps(p) + "\n")
            tasks = collections.Counter(p["task"] for p in ded)
            gaps = sorted(float(p["gap_raw"]) for p in ded if p.get("gap_raw") is not None)
            hard = sum(1 for g in gaps if g < 1e-2)
            print(f"        -> wrote {out}: {len(ded)} pairs, {len(tasks)} tasks, "
                  f"{hard} ({hard/max(len(gaps),1):.1%}) below gap 1e-2")
            print(f"        tasks with >=30 hard pairs: "
                  f"{ {t: sum(1 for p in ded if p['task'] == t and p.get('gap_raw') is not None and float(p['gap_raw']) < 1e-2) for t in tasks if sum(1 for p in ded if p['task'] == t and p.get('gap_raw') is not None and float(p['gap_raw']) < 1e-2) >= 30} }")

print("\nRead: a budget whose rev-conflict column is 0 and whose gap==|graded| column is ~100%")
print("is a clean evaluation target with an exactly-applicable noise ceiling. That is the")
print("set the hard-region claim should be tested on, not the lookahead pairs.")
