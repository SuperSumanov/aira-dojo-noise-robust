"""Go/no-go gate between the third smoke and the full dose-response run.

Green requires, on the smoke results:
  * zero container mount failures (the class that wasted the first two smokes);
  * zero offline-HF failures (the worker now runs in the online regime collection used);
  * at least 3 children yielding a KEYED stdout val by 120s -- the signal the whole
    experiment measures; fewer means the parser or the caps need rework, not GPU hours.
Prints PASS/FAIL with the evidence; exit code feeds the overnight chain.
"""
import json, sys

path = sys.argv[1] if len(sys.argv) > 1 else "phase1/fidelity_smoke3_results.jsonl"
rows = [json.loads(l) for l in open(path)]
mount = [r for r in rows if "mount source" in (r.get("err_tail") or "")]
offline = [r for r in rows if "huggingface.co" in (r.get("err_tail") or "")
           and ("connect" in (r.get("err_tail") or "")
                or "LocalEntryNotFound" in (r.get("err_tail") or ""))]
keyed120 = [r for r in rows if r["cap"] == 120 and r.get("val_how") == "keyed"]
n_child = len({r["card_id"] for r in rows})
print(f"records {len(rows)} over {n_child} children")
print(f"mount failures: {len(mount)}  "
      f"({sorted({r['competition'][:24] for r in mount})})")
print(f"offline-HF failures: {len(offline)}  "
      f"({sorted({r['competition'][:24] for r in offline})})")
print(f"children with keyed val by 120s: {len(keyed120)}  "
      f"({sorted({r['competition'][:24] for r in keyed120})})")
ok = not mount and not offline and len(keyed120) >= 3
print("GATE:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
