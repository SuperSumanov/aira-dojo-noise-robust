"""Sibling-level flips on the run-clean decision split: the deployment-granularity
version of the 08-06 doc's 'monopoly region'.

A sibling pair emitted at K=0 and again at K>=1 with the OPPOSITE winner is a flip:
the child that looks better by its own eventual score is not the one whose subtree goes
further. On such pairs any current-quality proxy is wrong by construction, so the RM only
needs > 0.5 to be the sole usable signal. Small n expected -- this is the directional
check; the powered version comes from l1run's hits on the big value-pairs flip set.

Usage: python phase1/sibling_flips.py
"""
import json, math

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

by_pair = {}
for l in open("phase1/decision_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] != "test":
        continue
    key = (p["parent"], frozenset((p["better"], p["worse"])))
    by_pair.setdefault(key, {})[p["budget"]] = p

hits = {}
for l in open("phase1/hits_decrun_s7.jsonl"):
    h = json.loads(l)
    hits[(h["better"], h["worse"], h["budget"])] = h["hit"]

flips, agrees = [], []
for key, ks in by_pair.items():
    if 0 not in ks:
        continue
    base = ks[0]["better"]
    for K in (1, 2):
        if K in ks:
            (flips if ks[K]["better"] != base else agrees).append(ks[K])

print(f"sibling pairs seen at K=0 and K>=1: flips {len(flips)}, agree {len(agrees)}")


def sr_hit(p):
    try:
        sb = float(cards[p["better"]]["obs"].get("val_at_low"))
        sw = float(cards[p["worse"]]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    if sb == sw:
        return None
    return int((sb < sw) if ORI.get(p["task"], False) else (sb > sw))


for name, subset in (("FLIP", flips), ("AGREE", agrees)):
    rm_k = rm_n = sr_k = sr_n = 0
    for p in subset:
        h = hits.get((p["better"], p["worse"], p["budget"]))
        if h is not None:
            rm_k += h
            rm_n += 1
        s = sr_hit(p)
        if s is not None:
            sr_k += s
            sr_n += 1
    if rm_n:
        se = math.sqrt(rm_k/rm_n*(1-rm_k/rm_n)/rm_n)
        print(f"  {name:5s} RM {rm_k}/{rm_n} = {rm_k/rm_n:.3f}±{se:.3f}   "
              f"SR {sr_k}/{sr_n} = {sr_k/max(sr_n,1):.3f}")
