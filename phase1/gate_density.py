"""Gate-density check: does |z(RM) - z(self-report)| concentrate the flip pairs?

Ported from the 08-06 critique doc's appendix D onto our run-clean artifacts. The gate is
Direction A's whole mechanism -- it must be computable at decision time (RM score +
self-report only, never the grade). Two criteria, both required:
  (1) flip density inside the gate / outside >= 2.0 AND above the permutation null's
      95th percentile (RM shuffled within task; kills any third-variable artefact);
  (2) RM accuracy INSIDE the gate significantly > 0.5 -- this is the paper claim.
Traps honoured: SR_in ~ 1 - RM_in is arithmetic, not evidence; 'mass' is over gateable
pairs, '%all' is the true intervention rate; nodes without a self-report never gate
(fail-safe to vanilla UCT).

Usage: python phase1/gate_density.py rm_scores_runsplit.json  [NPERM]
"""
import collections, json, random, sys

SCORES = sys.argv[1] if len(sys.argv) > 1 else "phase1/rm_scores_runsplit.json"
NPERM = int(sys.argv[2]) if len(sys.argv) > 2 else 200
MASSES = (0.10, 0.20, 0.30, 0.50)

rm = {k: float(v) for k, v in json.load(open(SCORES)).items()}
ORI = json.load(open("phase1/task_orientation.json"))

task_of, sr = {}, {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    task_of[d["id"]] = d["task"]["name"]
    try:
        v = float(d["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        continue
    # orient so that higher = better, using benchmark metadata (known pre-label)
    sr[d["id"]] = -v if ORI.get(d["task"]["name"], False) else v

test = []
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "test" and p["better"] in rm and p["worse"] in rm:
        test.append(p)


def zmap(vals):
    n = len(vals)
    mu = sum(vals.values()) / n
    sd = (sum((v - mu) ** 2 for v in vals.values()) / n) ** 0.5
    return ({k: (v - mu) / sd for k, v in vals.items()} if sd > 1e-12
            else {k: 0.0 for k in vals})


by_task = collections.defaultdict(list)
for cid in rm:
    by_task[task_of[cid]].append(cid)
zrm, zsr = {}, {}
for t, ids in by_task.items():
    zrm.update(zmap({c: rm[c] for c in ids}))
    have = [c for c in ids if c in sr]
    if have:
        zsr.update(zmap({c: sr[c] for c in have}))

dis = {c: abs(zrm[c] - zsr[c]) for c in zrm if c in zsr}
print(f"[gate] {len(test)} test pairs, {len(zrm)} scored nodes, "
      f"{len(zrm) - len(dis)} without self-report (never gated, fail-safe)")

rows = []
for p in test:
    b, w = p["better"], p["worse"]
    rows.append({
        "flip": p.get("agrees_with_quality") is False,
        "rm_ok": 1.0 if rm[b] > rm[w] else (0.5 if rm[b] == rm[w] else 0.0),
        "sr_ok": (None if (b not in sr or w not in sr) else
                  (1.0 if sr[b] > sr[w] else (0.5 if sr[b] == sr[w] else 0.0))),
        "d": (max(dis[b], dis[w]) if (b in dis and w in dis) else None),
    })


def frac(rs, key):
    vals = [r[key] for r in rs if r[key] is not None]
    return sum(vals) / len(vals) if vals else float("nan")


def ratio_at(dv, mass):
    s = sorted(v for v in dv if v is not None)
    if not s:
        return None
    th = s[max(0, min(len(s) - 1, int(round((1 - mass) * len(s)))))]
    ins = [r for r, v in zip(rows, dv) if v is not None and v >= th]
    out = [r for r, v in zip(rows, dv) if v is None or v < th]
    if not ins or not out:
        return None
    fi, fo = frac(ins, "flip"), frac(out, "flip")
    return (fi / fo if fo > 0 else float("inf")), fi, fo, ins, out


dv0 = [r["d"] for r in rows]
n_gate = sum(v is not None for v in dv0)
print(f"gateable pairs = {n_gate}/{len(rows)} ({n_gate/len(rows):.1%})\n")
print(f"{'mass':>6} {'n_in':>6} {'%all':>6} {'flip_in':>8} {'flip_out':>9} "
      f"{'ratio':>7} {'null95':>7} {'RM_in':>7} {'RM_out':>7} {'SR_in':>7}")
print("-" * 80)
rng = random.Random(11)
for m in MASSES:
    got = ratio_at(dv0, m)
    if got is None:
        continue
    ratio, fi, fo, ins, out = got
    null = []
    for _ in range(NPERM):
        perm = {}
        for t, ids in by_task.items():
            sh = ids[:]
            rng.shuffle(sh)
            for a, c in zip(ids, sh):
                perm[a] = zrm[c]
        pdis = {c: abs(perm[c] - zsr[c]) for c in perm if c in zsr}
        pv = [(max(pdis[p["better"]], pdis[p["worse"]])
               if (p["better"] in pdis and p["worse"] in pdis) else None) for p in test]
        g = ratio_at(pv, m)
        if g:
            null.append(g[0])
    null.sort()
    n95 = null[int(0.95 * len(null))] if null else float("nan")
    print(f"{m:6.2f} {len(ins):6d} {len(ins)/len(rows):6.1%} {fi:8.3f} {fo:9.3f} "
          f"{ratio:7.2f} {n95:7.2f} {frac(ins,'rm_ok'):7.4f} "
          f"{frac(out,'rm_ok'):7.4f} {frac(ins,'sr_ok'):7.4f}")
print("-" * 80)
print("PASS needs: ratio >= 2.0 AND ratio > null95 AND RM_in significantly > 0.5.")
print("SR_in ~ 1 - RM_in inside the gate is arithmetic (the gate selects disagreement).")
