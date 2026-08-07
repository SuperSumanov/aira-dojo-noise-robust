"""Flip files carry x/y (not better/worse): filter budget_flip_v3 by the run-split rule.
Flip metrics have no train side -- keep only records where BOTH x,y are in HELD runs so the
retrained model's flip eval never touches training runs."""
import collections, json

RUN = json.load(open("phase1/card_run_map.json"))
hold = set(json.load(open("phase1/runsplit_holdruns.json")))
n = collections.Counter()
with open("phase1/budget_flip_v3_runsplit.jsonl", "w") as out:
    for l in open("phase1/budget_flip_v3.jsonl"):
        p = json.loads(l)
        if p["x"] not in RUN or p["y"] not in RUN:
            n["unmapped"] += 1
            continue
        if RUN[p["x"]] in hold and RUN[p["y"]] in hold:
            out.write(l)
            n["kept_" + p["kind"]] += 1
        else:
            n["dropped"] += 1
print(dict(n))
