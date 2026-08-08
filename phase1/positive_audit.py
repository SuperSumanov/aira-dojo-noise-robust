"""Honest audit: is there ANY stratum where the trained RM beats the training-free baselines?

I claimed "zero positive results" from memory. That claim was never actually tested on
matched subsets -- the L1 clean number (0.6859) was compared against a self-report figure
(0.6345) computed on a DIFFERENT draw. Same-subset comparison is the only fair one, so
compute self-report, code_len, runtime and step_order on exactly the pairs the RM was
scored on, within each leakage stratum.

Sources: hits_l1_valuepairs.jsonl (RM per-pair hits on the 3000-pair L1 eval),
card_run_map.json + value_pairs_v3.jsonl train side (stratum membership).

Usage: python phase1/positive_audit.py
"""
import collections, json, math
from math import comb

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
RUN = json.load(open("phase1/card_run_map.json"))
ORI = json.load(open("phase1/task_orientation.json"))

root = {}
def tr(c, g=0):
    if c in root:
        return root[c]
    p = cards.get(c, {}).get("lineage", {}).get("parent_id")
    r = c if (not p or p not in cards or g > 200) else tr(p, g + 1)
    root[c] = r
    return r

train_frags = set()
for l in open("phase1/value_pairs_v3.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "train":
        for e in (p["better"], p["worse"]):
            if e in cards:
                train_frags.add(tr(e))


def feat(cid, name):
    d = cards[cid]
    if name == "self_report":
        try:
            return float(d["obs"].get("val_at_low"))
        except (TypeError, ValueError):
            return None
    if name == "code_len":
        return float(len(d.get("code") or ""))
    if name == "runtime":
        try:
            return float(d["obs"].get("runtime_s"))
        except (TypeError, ValueError):
            return None
    if name == "step_order":
        s = d["lineage"].get("step")
        return float(s) if s is not None else None


def base_hit(p, name):
    b, w = feat(p["better"], name), feat(p["worse"], name)
    if b is None or w is None or b == w:
        return None
    hi = b > w
    if name == "self_report" and ORI.get(p["task"], False):
        hi = b < w
    return int(hi)


rows = [json.loads(l) for l in open("phase1/hits_l1_valuepairs.jsonl")]
rows = [r for r in rows if r["better"] in cards and r["worse"] in cards]
strata = {
    "ALL": lambda r: True,
    "frag_mixed": lambda r: tr(r["better"]) in train_frags or tr(r["worse"]) in train_frags,
    "frag_clean": lambda r: tr(r["better"]) not in train_frags and tr(r["worse"]) not in train_frags,
}

BASES = ["self_report", "code_len", "runtime", "step_order"]
print("L1 eval (value pairs = 'which node leads somewhere better'), matched subsets\n")
for sname, cond in strata.items():
    sub = [r for r in rows if cond(r)]
    if not sub:
        continue
    rm = sum(r["hit"] for r in sub) / len(sub)
    print(f"[{sname}] n={len(sub)}   RM={rm:.4f}")
    for bn in BASES:
        pairs = [(r["hit"], base_hit(r, bn)) for r in sub]
        pairs = [(a, b) for a, b in pairs if b is not None]
        if len(pairs) < 50:
            print(f"    {bn:12s} (only {len(pairs)} covered, skipped)")
            continue
        n = len(pairs)
        rm_s = sum(a for a, _ in pairs) / n
        bs = sum(b for _, b in pairs) / n
        b01 = sum(1 for a, b in pairs if a == 0 and b == 1)
        b10 = sum(1 for a, b in pairs if a == 1 and b == 0)
        m = b01 + b10
        p = (min(1.0, sum(comb(m, j) for j in range(0, min(b01, b10) + 1)) / 2 ** m * 2)
             if m else 1.0)
        win = "RM WINS" if rm_s > bs else ("baseline wins" if bs > rm_s else "tie")
        print(f"    {bn:12s} n={n:5d}  RM={rm_s:.4f}  base={bs:.4f}  "
              f"delta={rm_s-bs:+.4f}  McNemar p={p:.2e}  -> {win}")
    print()
