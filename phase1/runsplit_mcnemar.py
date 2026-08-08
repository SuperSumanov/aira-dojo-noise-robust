"""McNemar on the run-level-clean decision split (the strictest split we have)."""
import json
from math import comb

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))


def sr_hit(b, w, task):
    try:
        sb = float(cards[b]["obs"].get("val_at_low"))
        sw = float(cards[w]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    if sb == sw:
        return None
    return int((sb < sw) if ORI.get(task, False) else (sb > sw))


rm = sr = n = b01 = b10 = 0
per_k = {}
for l in open("phase1/hits_decrun_s7.jsonl"):
    h = json.loads(l)
    s = sr_hit(h["better"], h["worse"], h["task"])
    if s is None:
        continue
    n += 1
    rm += h["hit"]
    sr += s
    if h["hit"] == 0 and s == 1:
        b01 += 1
    if h["hit"] == 1 and s == 0:
        b10 += 1
    k = per_k.setdefault(h["budget"], [0, 0, 0])
    k[0] += h["hit"]
    k[1] += s
    k[2] += 1

m = b01 + b10
p = min(1.0, sum(comb(m, j) for j in range(0, min(b01, b10) + 1)) / 2 ** m * 2) if m else 1.0
print(f"run-level clean decision split, covered n={n}")
print(f"  RM {rm/n:.3f}   self-report {sr/n:.3f}")
print(f"  discordant {b01}:{b10}   McNemar two-sided p={p:.2e}")
for k in sorted(per_k):
    a, b, c = per_k[k]
    print(f"  K={k}: n={c}  RM={a/c:.3f}  SR={b/c:.3f}")
