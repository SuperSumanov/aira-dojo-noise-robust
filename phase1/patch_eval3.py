"""Extend the suite's secondary scoring to the K=1 and K=2 sibling sets.

Why these two sets suddenly matter: the K=0 verdict is that no decision-time predictor can
rank siblings by their CURRENT quality. But the earlier decision-point analysis left one cell
alive -- the RM's only winning cell was K>=1 lookahead -- and the senior independently
flagged "which node leads to the better solution k steps later" as the version of the
question with novelty. K=1/2 labels ask exactly that (subtree max over the next K
descendants). If anything beats chance there while sitting at chance at K=0, the story flips
from "critics are useless" to "critics read potential, not present quality" -- a positive,
mechanistic claim. If nothing does, the negative closes the last open cell. Either way the
cell has to be scored with the same frozen models, so it happens inside the suite.
"""
P = "phase1/predictor_suite.py"
s = open(P, encoding="utf-8").read()

if "EVAL2SETS" in s:
    print("already patched")
    raise SystemExit(0)

a = '''EVAL2 = []
_e2 = "phase1/decision_clean_b0.jsonl"
if _os2.path.exists(_e2):
    for _l in open(_e2):
        _p = json.loads(_l)
        if _p["better"] in cards and _p["worse"] in cards:
            EVAL2.append(_p)
print(f"secondary eval set: {len(EVAL2)} sibling pairs from {_e2}", flush=True)
'''
assert s.count(a) == 1, s.count(a)
b = '''EVAL2 = []
EVAL2SETS = ["phase1/decision_clean_b0.jsonl", "phase1/decision_clean_b1.jsonl",
             "phase1/decision_clean_b2.jsonl"]
for _e2 in EVAL2SETS:
    if _os2.path.exists(_e2):
        for _l in open(_e2):
            _p = json.loads(_l)
            if _p["better"] in cards and _p["worse"] in cards:
                EVAL2.append(_p)
print(f"secondary eval sets: {len(EVAL2)} sibling pairs from {len(EVAL2SETS)} files "
      f"(keys carry no budget; the budget lives in the pair files)", flush=True)
'''
s = s.replace(a, b)
open(P, "w", encoding="utf-8").write(s)
print("patched", P)
