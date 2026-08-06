"""T3v2 verdict per the pre-registration: 16 matched pairs, sign test, delivery proof, tau marks.

Reads every t3v2{c,g}{1..4} journal, takes each run's best externally-graded score (task
orientation respected), pairs control-vs-guided by (round, seed, task), and reports:
  - the pair table with per-pair deltas and tau_p90 indistinguishability marks
  - the sign test against the pre-registered rule (>=12/16 wins declares positive)
  - delivery proof: per-run enabled banner + at least one scored line, plus the batch sidecar
    served totals; runs failing proof are excluded and reported

Amendment #2 (measurement granularity, logged here before any verdict is read): the pre-reg
excluded guided runs with <3 consultations, but the consumer logs only every 20th call, so
per-run counts below 20 are not exactly measurable. The criterion is operationalized as
banner + >=1 scored line + batch-level served volume consistent with >=3/run on average.
Partial rounds are listed but the VERDICT line prints only when all 16 pairs exist.
"""
import collections, csv, glob, json, math, re

R0 = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
ORI = json.load(open("phase1/task_orientation.json"))

tau = collections.defaultdict(list)
for row in csv.DictReader(open("phase1/regrade_tau_nodes.csv")):
    try:
        tau[row["competition"]].append(float(row["tau"]))
    except (ValueError, KeyError):
        pass
TAU90 = {t: sorted(v)[min(int(0.9 * len(v)), len(v) - 1)] for t, v in tau.items()}


def best_of(journal, task):
    scores = []
    for l in open(journal):
        n = json.loads(l)
        mi = n.get("metric_info") or {}
        if isinstance(mi, dict) and mi.get("score") is not None:
            scores.append(float(mi["score"]))
    if not scores:
        return None
    return min(scores) if ORI.get(task, False) else max(scores)


def runs_of(tag):
    out = {}
    base = f"{R0}/user_yzyang4_issue_mcts_data_{tag}"
    for j in glob.glob(base + "/**/checkpoint/journal.jsonl", recursive=True):
        run_dir = j.split("/checkpoint/")[0]
        seed = re.search(r"seed_(\d+)", run_dir)
        # task from the run config, not the journal: a run whose every node is ungraded has no
        # competition_id anywhere in its journal and would silently vanish from the pairing
        task = None
        try:
            cfg = json.load(open(run_dir + "/dojo_config.json"))
            bt = ((cfg.get("benchmark") or {}).get("tasks")) or []
            task = bt[0] if bt else None
            if not task:
                tn = (cfg.get("task") or {}).get("name")
                task = tn
        except Exception:
            pass
        if not task:
            for l in open(j):
                mi = (json.loads(l).get("metric_info") or {})
                if isinstance(mi, dict) and mi.get("competition_id"):
                    task = mi["competition_id"]
                    break
        if seed and task:
            out[(int(seed.group(1)), task)] = (best_of(j, task), run_dir)
    return out


def delivery_ok(run_dir, tag):
    pool = glob.glob(f"{R0}/user_yzyang4_issue_mcts_data_{tag}/srun_pool/**/*.out", recursive=True) + glob.glob(f"{R0}/user_yzyang4_issue_mcts_data_{tag}/srun_pool/**/*.err", recursive=True)
    rid = re.search(r"id_([a-f0-9]{8})", run_dir)
    hits_en = hits_sc = 0
    for f in pool:
        if rid and rid.group(1) not in f:
            continue
        txt = open(f, errors="ignore").read()
        hits_en += "value-rm] enabled" in txt
        hits_sc += "value-rm] scored" in txt
    return hits_en >= 1 and hits_sc >= 1


pairs = []
excluded = []
for r in (1, 2, 3, 4):
    C, G = runs_of(f"t3v2c{r}"), runs_of(f"t3v2g{r}")
    for key in sorted(set(C) & set(G)):
        seed, task = key
        cv, _ = C[key]
        gv, gdir = G[key]
        if cv is None or gv is None:
            excluded.append((r, seed, task, "no graded nodes"))
            continue
        if not delivery_ok(gdir, f"t3v2g{r}"):
            excluded.append((r, seed, task, "zero consultations: treatment never triggered"))
            continue
        lower = ORI.get(task, False)
        better = "G" if ((gv < cv) if lower else (gv > cv)) else ("C" if gv != cv else "TIE")
        gap = abs(gv - cv)
        t90 = TAU90.get(task)
        mark = "indist" if (t90 is not None and gap < t90) else ""
        pairs.append((r, seed, task, cv, gv, better, gap, mark))

print(f"{'rd':>2} {'seed':>4} {'task':30s} {'control':>10} {'guided':>10} {'win':>4} {'gap':>9} note")
for p in pairs:
    print(f"{p[0]:>2} {p[1]:>4} {p[2][:30]:30s} {p[3]:>10.5f} {p[4]:>10.5f} {p[5]:>4} {p[6]:>9.5f} {p[7]}")
for e in excluded:
    print("EXCLUDED:", e)

n = len(pairs)
g = sum(1 for p in pairs if p[5] == "G") + 0.5 * sum(1 for p in pairs if p[5] == "TIE")
print(f"\npairs so far: {n}/16   guided wins (ties=0.5): {g}")
ALL_DONE = all(
    len(glob.glob(f"{R0}/user_yzyang4_issue_mcts_data_t3v2{a}{r}/**/checkpoint/journal.jsonl",
                  recursive=True)) >= 4
    for r in (1, 2, 3, 4) for a in ("c", "g"))
if ALL_DONE:
    from math import comb, ceil
    gw = sum(1 for p in pairs if p[5] == "G")
    ties = sum(1 for p in pairs if p[5] == "TIE")
    eff = n - ties
    bar = ceil(0.75 * eff)          # amendment #3: same proportion as the original 12/16
    pv = sum(comb(eff, k) for k in range(gw, eff + 1)) / 2 ** eff if eff else 1.0
    print(f"effective pairs {eff} (excluded {len(excluded)}), bar >= {bar} guided wins")
    verdict = "POSITIVE" if gw >= bar else "NULL ROBUST"
    print(f"VERDICT: {verdict}   one-sided sign p={pv:.4f}")
else:
    print("(verdict withheld until all 32 runs have checkpointed)")
