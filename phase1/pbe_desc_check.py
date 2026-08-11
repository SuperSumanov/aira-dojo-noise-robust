"""Robustness check the smoke exposed: did missing task descriptions drive the PBE verdict?

The fidelity smoke revealed that three tasks have no local data directory at all and one
more had its public tar unextracted -- so pbe_judge's desc_of() handed the judge a
"(description unavailable)" placeholder for pairs from those tasks. If the at-chance verdict
were concentrated on placeholder pairs, the adjudication would be attacking a strawman.

Split every judged pair by whether its task's description.md existed at judge time, and
re-score both arms both ways. The verdict stands only if the full-description subset is
itself at chance.
"""
import collections, json, math, os, random

DATA = "/research/d7/spc/yzyang4/mle-bench-data"


def has_desc(task):
    return os.path.isfile(f"{DATA}/{task}/prepared/public/description.md")


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


# NOTE: kuzushiji's tar may have been extracted between judge time and now; determine
# availability from the JUDGED RECORDS' tasks against the set known missing at judge time.
MISSING_AT_JUDGE = {"aptos2019-blindness-detection", "dog-breed-identification",
                    "histopathologic-cancer-detection", "kuzushiji-recognition"}

for path in ("phase1/pbe_desc.jsonl", "phase1/pbe_report.jsonl"):
    by = collections.defaultdict(dict)
    meta = {}
    for l in open(path):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        k = (d["better"], d["worse"])
        if d.get("correct") is not None:
            by[k][d["order"]] = d["correct"]
        meta[k] = d
    both = {k: v for k, v in by.items() if len(v) == 2}
    print(f"\n==== {path} ====")
    for label, sel in (
            ("desc PRESENT at judge time",
             lambda t: t not in MISSING_AT_JUDGE and has_desc(t)),
            ("desc MISSING at judge time (placeholder header)",
             lambda t: t in MISSING_AT_JUDGE)):
        d_par = collections.defaultdict(list)
        n = h = 0
        hard_vals = collections.defaultdict(list)
        for k, v in both.items():
            m = meta[k]
            if not sel(m["task"]):
                continue
            n += 1
            avg = (v[0] + v[1]) / 2.0
            d_par[m.get("parent")].append(avg)
            if float(m["gap_raw"]) < 1e-2:
                h += 1
                hard_vals[m.get("parent")].append(avg)
        if not n:
            print(f"  {label}: no pairs")
            continue
        v = [x for vs in d_par.values() for x in vs]
        lo, hi = boot(d_par)
        line = f"  {label}: n={n} acc={sum(v)/len(v):.4f} parent[{lo:.4f},{hi:.4f}]"
        hv = [x for vs in hard_vals.values() for x in vs]
        if hv:
            hlo, hhi = boot(hard_vals)
            line += f"   HARD n={h} acc={sum(hv)/len(hv):.4f} [{hlo:.4f},{hhi:.4f}]"
        print(line)
    tasks = collections.Counter(m["task"] for m in meta.values())
    miss_n = sum(c for t, c in tasks.items() if t in MISSING_AT_JUDGE)
    print(f"  placeholder share of sample: {miss_n}/{sum(tasks.values())} "
          f"= {miss_n/max(sum(tasks.values()),1):.1%}")
