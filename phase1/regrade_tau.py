"""Re-grade arm analysis: per-task noise floor tau + cross-env offset.
tau = within-env pstdev of scores across K same-container re-executions per node.
offset = mean(rerun) - orig_graded (raw score units; orientation task-specific).
Usage: python phase1/regrade_tau.py"""
import json, collections, statistics as st

RES = "/research/d7/spc/yzyang4/aira-dojo/phase1/regrade_results.jsonl"
MAN = "/research/d7/spc/yzyang4/aira-dojo/phase1/regrade_manifest.jsonl"
man = {json.loads(l)["card_id"]: json.loads(l) for l in open(MAN)}
by = collections.defaultdict(list)
fails, caps = collections.Counter(), collections.Counter()
for l in open(RES):
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
    offs = [o for _, o, _ in rs if o is not None]
    gr = [m["graded"] for m in man.values() if m["competition"] == comp]
    p90 = taus[int(0.9 * (len(taus)-1))]
    print(f"{comp[:28]:28s} {len(rs):5d} {det:4.0f}% {st.median(taus):9.4f} {p90:9.4f} {max(taus):9.4f} "
          f"{st.median(offs):9.4f} [{min(gr):7.3f},{max(gr):7.3f}] {fails[comp]:4d} {caps[comp]:4d}")
    top = sorted(rs, reverse=True)[:2]
    for t, o, cid in top:
        if t > 1e-9:
            print(f"    noisiest {cid[-8:]}: tau={t:.4f} reps={by[cid]}")

# per-node CSV artifact (for effective-pairs / noise-aware training)
import csv
with open("phase1/regrade_tau_nodes.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["card_id", "competition", "n_reps", "tau", "orig_graded", "mean_rerun", "offset", "reps"])
    for cid, ss in sorted(by.items()):
        m = man.get(cid, {})
        orig = m.get("graded")
        mean = sum(ss) / len(ss)
        w.writerow([cid, m.get("competition", ""), len(ss), f"{st.pstdev(ss):.6g}" if len(ss) > 1 else "",
                    orig, f"{mean:.6g}", f"{mean - orig:.6g}" if orig is not None else "", ";".join(str(x) for x in ss)])
print("wrote phase1/regrade_tau_nodes.csv")
