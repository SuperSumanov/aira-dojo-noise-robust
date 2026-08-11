"""Score the arXiv:2601.05930 reproduction the way the original was not scored.

Order-averaged accuracy (both orderings of every pair), stratified at the pre-registered
gap threshold, parent-clustered bootstrap, between-order disagreement as the reliability
diagnostic, and self_report on the SAME sampled pairs so the comparison is same-pool.

Usage: python phase1/pbe_score.py phase1/pbe_desc.jsonl phase1/pbe_report.jsonl
"""
import collections, json, math, random, sys

ORI = json.load(open("phase1/task_orientation.json"))
OWN = {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    try:
        v = float(d["obs"].get("val_at_low"))
        OWN[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        OWN[d["id"]] = None


def boot(d, nb=4000, seed=7):
    ks = list(d)
    if not ks:
        return float("nan"), float("nan")
    rr = random.Random(seed)
    o = []
    for _ in range(nb):
        v = [x for k in (rr.choice(ks) for _ in ks) for x in d[k]]
        o.append(sum(v) / len(v))
    o.sort()
    return o[int(.025 * nb)], o[int(.975 * nb)]


for path in sys.argv[1:]:
    by = collections.defaultdict(dict)   # (better,worse) -> {order: correct}
    meta = {}
    tok_in = tok_out = 0
    for l in open(path):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        k = (d["better"], d["worse"])
        if d.get("correct") is not None:
            by[k][d["order"]] = d["correct"]
        meta[k] = d
        tok_in += d.get("tok_in", 0)
        tok_out += d.get("tok_out", 0)
    print(f"\n==== {path} ====")
    print(f"pairs with >=1 parsed order: {len(by)}; "
          f"tokens {tok_in/1e6:.2f}M in / {tok_out/1e3:.0f}k out")
    both = {k: v for k, v in by.items() if len(v) == 2}
    dis = sum(1 for v in both.values() if v[0] != v[1])
    print(f"pairs with BOTH orders parsed: {len(both)}; "
          f"between-order disagreement: {dis}/{len(both)} = "
          f"{dis/max(len(both),1):.1%}")

    for label, sel in (("HARD gap<1e-2", lambda g: g < 1e-2),
                       ("EASY gap>=1e-2", lambda g: g >= 1e-2),
                       ("ALL", lambda g: True)):
        d_par, d_task = collections.defaultdict(list), collections.defaultdict(list)
        d_sr = collections.defaultdict(list)
        n = 0
        for k, v in both.items():
            m = meta[k]
            if not sel(float(m["gap_raw"])):
                continue
            n += 1
            avg = (v[0] + v[1]) / 2.0
            d_par[m.get("parent")].append(avg)
            d_task[m["task"]].append(avg)
            sa, sb = OWN.get(k[0]), OWN.get(k[1])
            if sa is not None and sb is not None and sa != sb:
                d_sr[m.get("parent")].append(
                    float((sa < sb) if ORI.get(m["task"], False) else (sa > sb)))
        v = [x for vs in d_par.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_par)
        tlo, thi = boot(d_task)
        sv = [x for vs in d_sr.values() for x in vs]
        slo, shi = boot(d_sr)
        print(f"  {label:16s} n={n:4d}  judge={sum(v)/len(v):.4f} "
              f"parent[{lo:.4f},{hi:.4f}] task[{tlo:.4f},{thi:.4f}]"
              + (f"   self_report(same pool)={sum(sv)/len(sv):.4f} "
                 f"parent[{slo:.4f},{shi:.4f}] n={len(sv)}" if sv else ""))
    print("  Read: their global figure is the ALL row's ancestor; the claim under test")
    print("  lives in the HARD row. Chance-level there with a tight CI, against ceiling")
    print("  0.8962, adjudicates the execution-free claim at the decision point.")
