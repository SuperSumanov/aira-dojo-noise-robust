"""Make predictor_suite dump its per-pair decisions.

The headline table gives one number per predictor. Gap-stratification needs the decision on
every individual pair, otherwise each stratum has to re-train everything. Cheapest correct
route: record what each predictor answered, keyed by the pair, and let the stratifier read
it. No predictor logic is touched -- only an observation point is added.
"""
import re

P = "phase1/predictor_suite.py"
s = open(P, encoding="utf-8").read()

if "PERPAIR" in s:
    print("already patched")
    raise SystemExit(0)

a = "results = []\n"
assert s.count(a) == 1, s.count(a)
s = s.replace(a, "results = []\nPERPAIR = {}\n")

b = """    n_cov = 0
    t0 = time.time()
    for p in test:
        v = pred_fn(p["better"], p["worse"])
        if v is None:
            continue
        n_cov += 1
"""
assert s.count(b) == 1, s.count(b)
s = s.replace(b, """    n_cov = 0
    t0 = time.time()
    _pp = PERPAIR.setdefault(name, {})
    for p in test:
        v = pred_fn(p["better"], p["worse"])
        if v is None:
            continue
        n_cov += 1
        _pp[p["better"] + "|" + p["worse"]] = int(v)
""")

c = 'print(f"\\nwrote {len(results)} rows -> {a.out}")'
assert s.count(c) == 1, s.count(c)
s = s.replace(c, c + """
with open("phase1/perpair_hits.json", "w") as _f:
    json.dump(PERPAIR, _f)
print(f"wrote per-pair decisions for {len(PERPAIR)} predictors "
      f"({sum(len(v) for v in PERPAIR.values())} decisions) -> phase1/perpair_hits.json")""")

open(P, "w", encoding="utf-8").write(s)
print("patched", P)
