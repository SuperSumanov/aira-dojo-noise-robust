"""Every pair of the v8 clean b0 set must survive the v9 regeneration with its label intact.

Exits non-zero on any loss or label change, and the chain aborts before anything downstream
can be computed on a set that silently shrank. The snapshot is the file the pushed numbers
were computed on.
"""
import json, sys

old = {}
for l in open("phase1/decision_clean_b0.v8snap.jsonl"):
    p = json.loads(l)
    old[(p["better"], p["worse"])] = p["gap_raw"]
new = {}
for l in open("phase1/decision_clean_b0.jsonl"):
    p = json.loads(l)
    new[(p["better"], p["worse"])] = p["gap_raw"]
missing = [k for k in old if k not in new]
changed = [k for k in old if k in new and abs(old[k] - new[k]) > 1e-9]
print(f"verbatim survival: old {len(old)} pairs -> missing {len(missing)}, "
      f"gap changed {len(changed)}, new total {len(new)} (+{len(new) - len(old)})")
for k in missing[:5]:
    print("  missing:", k)
for k in changed[:5]:
    print("  changed:", k, old[k], "->", new[k])
if missing or changed:
    print("OLD PAIRS NOT PRESERVED -- do not use")
    sys.exit(1)
print("OK: the old clean set survives verbatim inside the new one")
