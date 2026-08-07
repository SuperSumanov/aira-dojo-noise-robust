"""Compute per-node score noise from repeated, externally graded executions.

Tau is the population standard deviation of repeated scores for the same card in
the same execution environment. Offset is mean(rerun) - original grade.
"""
import argparse
import collections
import csv
import json
import statistics as st

ap = argparse.ArgumentParser()
ap.add_argument("results", help="JSONL rows containing card_id, competition and score")
ap.add_argument("manifests", nargs="+", help="one or more regrade manifest JSONL files")
ap.add_argument("--out", required=True, help="output per-node CSV")
a = ap.parse_args()

man = {}
for manifest_path in a.manifests:
    try:
        for l in open(manifest_path):
            d = json.loads(l); man.setdefault(d["card_id"], d)
    except FileNotFoundError:
        raise SystemExit(f"manifest not found: {manifest_path}")
by = collections.defaultdict(list)
fails, caps = collections.Counter(), collections.Counter()
for l in open(a.results):
    d = json.loads(l)
    if d.get("score") is not None:
        by[d["card_id"]].append(d["score"])
    else:
        fails[d["competition"]] += 1
        if d.get("exec_rc") == 124: caps[d["competition"]] += 1

rows = collections.defaultdict(list)
for cid, ss in by.items():
    if len(ss) < 2: continue
    m = man.get(cid, {})
    comp = m.get("competition") or cid.split("__")[0]
    orig = m.get("graded")
    off = (sum(ss)/len(ss) - orig) if orig is not None else None
    rows[comp].append((st.pstdev(ss), off, cid))

print(f"{'task':28s} {'nodes':>5} {'det%':>5} {'med_tau':>9} {'p90_tau':>9} {'max_tau':>9} {'med_off':>9} {'gradeRange':>19} {'fail':>4} {'cap':>4}")
for comp, rs in sorted(rows.items()):
    taus = sorted(t for t, _, _ in rs)
    det = sum(1 for t in taus if t < 1e-9) / len(taus) * 100
    offs = [o for _, o, _ in rs if o is not None] or [float("nan")]
    gr = [m["graded"] for m in man.values() if m.get("competition") == comp and m.get("graded") is not None] or [float("nan")]
    p90 = taus[int(0.9 * (len(taus)-1))]
    print(f"{comp[:28]:28s} {len(rs):5d} {det:4.0f}% {st.median(taus):9.4f} {p90:9.4f} {max(taus):9.4f} "
          f"{st.median(offs):9.4f} [{min(gr):7.3f},{max(gr):7.3f}] {fails[comp]:4d} {caps[comp]:4d}")
    top = sorted(rs, reverse=True)[:2]
    for t, o, cid in top:
        if t > 1e-9:
            print(f"    noisiest {cid[-8:]}: tau={t:.4f} reps={by[cid]}")

# Per-node artifact consumed by build_budget_pairs.py.
with open(a.out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["card_id", "competition", "n_reps", "tau", "orig_graded", "mean_rerun", "offset", "reps"])
    for cid, ss in sorted(by.items()):
        m = man.get(cid, {})
        orig = m.get("graded")
        mean = sum(ss) / len(ss)
        w.writerow([cid, m.get("competition", ""), len(ss), f"{st.pstdev(ss):.6g}" if len(ss) > 1 else "",
                    orig, f"{mean:.6g}", f"{mean - orig:.6g}" if orig is not None else "", ";".join(str(x) for x in ss)])
print(f"wrote {a.out}")
