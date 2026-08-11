"""Score the same predictors on a second evaluation set without retraining them.

The sibling (decision) pairs at budget 0 are the semantically right target -- "which of these
candidates should search run next" -- and, unlike the lookahead pairs, their label margin is
an own-score margin, so the regrade-derived noise ceiling applies exactly there. What they
lack is predictor decisions.

Retraining on them would answer a different question, and would break comparability with the
headline table. The models must be the identical ones: trained on the value-pair TRAIN split
and merely queried on a second set. That is legitimate here for a reason already measured --
value-TRAIN runs and decision-TEST runs share zero runs, so nothing the models saw appears in
the second set.

Adds a secondary eval pass to evaluate() and dumps its per-pair decisions separately, leaving
the primary CSV numbers untouched.
"""
P = "phase1/predictor_suite.py"
s = open(P, encoding="utf-8").read()

if "PERPAIR2" in s:
    print("already patched")
    raise SystemExit(0)

a = "results = []\nPERPAIR = {}\n"
assert s.count(a) == 1
s = s.replace(a, """results = []
PERPAIR = {}
PERPAIR2 = {}
import os as _os2
EVAL2 = []
_e2 = "phase1/decision_clean_b0.jsonl"
if _os2.path.exists(_e2):
    for _l in open(_e2):
        _p = json.loads(_l)
        if _p["better"] in cards and _p["worse"] in cards:
            EVAL2.append(_p)
print(f"secondary eval set: {len(EVAL2)} sibling pairs from {_e2}", flush=True)
""")

b = """    q = (time.time() - t0) / max(n_cov, 1)
"""
assert s.count(b) == 1
s = s.replace(b, """    q = (time.time() - t0) / max(n_cov, 1)
    if EVAL2:
        _p2 = PERPAIR2.setdefault(name, {})
        for p in EVAL2:
            v2 = pred_fn(p["better"], p["worse"])
            if v2 is not None:
                _p2[p["better"] + "|" + p["worse"]] = int(v2)
""")

c = 'json.dump(PERPAIR, _f)'
assert s.count(c) == 1
s = s.replace(c, """json.dump(PERPAIR, _f)
with open("phase1/perpair_decision.json", "w") as _f2:
    json.dump(PERPAIR2, _f2)""")

open(P, "w", encoding="utf-8").write(s)
print("patched", P)
