"""Two things at once: why the judges score below chance, and whether tfidf really beats the RM.

(1) JUDGE ORIENTATION. In the corrected hard region the judges read 0.1667 and 0.2857. A
    weak judge lands near 0.5; one that lands at 0.17 is not weak, it is inverted. The
    judge files record `correct` relative to the pair set they were RUN on. If that set
    ordered a pair the other way round from the lookahead set they are now scored against,
    every recorded `correct` is flipped. Checked by looking up each judged pair in the
    lookahead file in both directions.

(2) PAIRED tfidf VS RM. In the corrected hard region tfidf_lr reads 0.5676 with both
    clustered intervals excluding 0.5, while the fine-tuned RM reads 0.5133 and spans it.
    That is the interesting claim -- a seconds-to-train n-gram model surviving where the
    GPU-trained reward model does not -- so it gets the paired test rather than the
    eyeball comparison of two separately-computed intervals. Same pairs, per-pair
    difference, clustered both ways.
"""
import collections, json, math, random

ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
PP = json.load(open("phase1/perpair_hits.json"))

fwd, rev = {}, {}
for l in open("phase1/hits_l1_uncapped.jsonl"):
    h = json.loads(l)
    fwd[(h["better"], h["worse"])] = h
    rev[(h["worse"], h["better"])] = h

print("--- (1) judge orientation against the lookahead pair set ---")
for tag, path in (("judge_qwen_max", "phase1/judge_qwenmax.jsonl"),
                  ("judge_deepseek", "phase1/judge_code8k.jsonl")):
    same = flip = absent = 0
    runs = collections.Counter()
    for l in open(path):
        d = json.loads(l)
        if d.get("correct") is None:
            continue
        k = (d["better"], d["worse"])
        runs[d.get("run", "?").split(":")[0]] += 1
        if k in fwd:
            same += 1
        elif k in rev:
            flip += 1
        else:
            absent += 1
    tot = same + flip + absent
    print(f"{tag}: judged rows {tot}")
    print(f"   pair present in lookahead SAME direction : {same} ({same/max(tot,1):.1%})")
    print(f"   pair present REVERSED                    : {flip} ({flip/max(tot,1):.1%})"
          f"   <- every one of these has its `correct` inverted")
    print(f"   pair absent from the lookahead set       : {absent} "
          f"({absent/max(tot,1):.1%})")
    print(f"   source files judged: {dict(runs.most_common(5))}")

print("\n--- (2) paired tfidf_lr vs rm_1.5b, corrected hard region ---")
rows = []
for l in open("phase1/hits_l1_uncapped.jsonl"):
    h = json.loads(l)
    g = h.get("gap_raw")
    if g is None:
        continue
    rows.append({"key": h["better"] + "|" + h["worse"], "task": h["task"],
                 "gap": float(g), "rm": h["hit"], "run": RUN.get(h["better"])})


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


for label, sel in (("HARD  gap_raw<1e-2", lambda r: r["gap"] < 1e-2),
                   ("EASY  gap_raw>=1e-2", lambda r: r["gap"] >= 1e-2)):
    sub = [r for r in rows if sel(r)]
    for name in ("tfidf_lr", "self_report", "static_gbm", "embed_frozen_0.5b"):
        if name not in PP:
            continue
        d_t, d_r, n_pos, n_neg = (collections.defaultdict(list),
                                  collections.defaultdict(list), 0, 0)
        for r in sub:
            x = PP[name].get(r["key"])
            if x is None:
                continue
            diff = float(x) - float(r["rm"])
            d_t[r["task"]].append(diff)
            d_r[r["run"]].append(diff)
            n_pos += int(diff > 0)
            n_neg += int(diff < 0)
        v = [x for vs in d_t.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_t)
        rlo, rhi = boot(d_r)
        # exact binomial sign test on discordant pairs (McNemar)
        n = n_pos + n_neg
        p = (sum(math.comb(n, i) for i in range(min(n_pos, n_neg) + 1)) * 2 /
             2 ** n) if n and n <= 1000 else float("nan")
        sig = "SIG" if (lo > 0 and rlo > 0) or (hi < 0 and rhi < 0) else ""
        print(f"{label}  {name:18s} - rm = {sum(v)/len(v):+.4f} "
              f"task[{lo:+.4f},{hi:+.4f}] run[{rlo:+.4f},{rhi:+.4f}] "
              f"n={len(v)} discordant {n_pos}/{n_neg} McNemar p={p:.2e} {sig}")
