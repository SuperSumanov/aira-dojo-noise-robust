"""Point build_runsplit's decision job at the v9 regeneration.

The other three JOBS keep their old sources deliberately: with the holdout frozen, re-splitting
an unchanged source reproduces the file byte-for-byte, and regenerating value pairs would
resample under the cap and silently change the training set every model was fitted on.
"""
P = "phase1/build_runsplit.py"
s = open(P, encoding="utf-8").read()
a = '("phase1/decision_pairs_v1b.jsonl", "phase1/decision_pairs_runsplit.jsonl"),'
b = '("phase1/decision_pairs_v9raw.jsonl", "phase1/decision_pairs_runsplit.jsonl"),'
if b in s:
    print("already patched")
elif a in s:
    open(P, "w", encoding="utf-8").write(s.replace(a, b))
    print("patched", P)
else:
    raise SystemExit("anchor not found")
