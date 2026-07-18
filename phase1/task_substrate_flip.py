"""Make-or-break for direction (2): is substrate-magnitude score noise AMPLIFIED by search selection into
argmax flips / rerouting / true-quality regret on HIGH-headroom tasks -- or does it average out?

Test A (breadth): per high-Δ subset_50 task, perturb the (substrate-computed) score by eps*within-task-SD,
  measure argmax-flip rate and REGRET = true beat_ratio(unperturbed best) - beat_ratio(perturbed pick).
  Also the top-gap (best-2nd)/SD -- how separable the top solutions are (small gap => fragile => amplified).
Test B (mechanism): cactus tree (agent_runs, has val+children), per parent perturb children's val -> argmax
  child flip rate -> path-divergence ~ 1-(1-p)^L. This is the 'amplified by selection' claim.

Calibration: substrate noise ~ 1-9% of the metric (GPU/BF16/cuDNN lit). We report flip/regret vs eps in
within-task-SD units AND each task's SD as % of mean, so eps maps to a real substrate fraction.
"""
import os
import re
import ast
import json
import glob
from collections import defaultdict

import numpy as np

RNG = np.random.default_rng(0)
DRAWS = 400
EPS = [0.05, 0.1, 0.2, 0.4]
NUM = re.compile(r"[-+]?\d*\.?\d+")
HIDELTA = {"tabular-playground-series-dec-2021", "spooky-author-identification", "denoising-dirty-documents",
           "aerial-cactus-identification", "lmsys-chatbot-arena", "google-quest-challenge",
           "predict-volcanic-eruptions-ingv-oe", "aptos2019-blindness-detection", "leaf-classification"}


def parse_metric(m):
    if m is None:
        return None, None
    d = m if isinstance(m, dict) else None
    if d is None:
        try:
            d = ast.literal_eval(str(m))
        except Exception:
            d = None
    if isinstance(d, dict):
        v = d.get("value"); mx = d.get("maximize")
        return (float(v) if v is not None else None), (bool(mx) if mx is not None else None)
    mm = NUM.findall(str(m))
    return (float(mm[-1]) if mm else None), None


# ===================== Test A: breadth over high-Δ subset tasks =====================
print("=== TEST A: argmax-flip + regret vs substrate-noise eps (high-Δ tasks, subset_50) ===", flush=True)
by_task = defaultdict(list)
for r in json.load(open("/research/d7/spc/yzyang4/foreagent_slice/slice.json")):
    if r["task"] in HIDELTA and r.get("beat_ratio") is not None:
        s = -r["score"] if r["is_lower_better"] else r["score"]   # orient higher=better
        by_task[r["task"]].append((s, r["beat_ratio"]))

print(f"  {'task':38s} {'n':>3} {'SD/|mean|':>9} {'topgap/SD':>9} | " + "  ".join(f"eps={e}" for e in EPS), flush=True)
print(f"  {'':38s} {'':>3} {'':>9} {'':>9} |  (flip% , regret in beat_ratio)", flush=True)
poolflip = {e: [] for e in EPS}
poolreg = {e: [] for e in EPS}
for t, rows in sorted(by_task.items()):
    s = np.array([x[0] for x in rows], float); b = np.array([x[1] for x in rows], float)
    if len(s) < 8 or s.std() < 1e-12:
        continue
    SD = s.std()
    best = int(np.argmax(s)); bbest = b[best]
    order = np.argsort(-s)
    topgap = (s[order[0]] - s[order[1]]) / SD
    sdrel = SD / (abs(np.mean(s)) + 1e-9)
    cells = []
    for e in EPS:
        flips, regs = [], []
        for _ in range(DRAWS):
            sp = s + RNG.normal(0, e * SD, len(s))
            ip = int(np.argmax(sp))
            flips.append(ip != best); regs.append(bbest - b[ip])
        fr, rg = float(np.mean(flips)), float(np.mean(regs))
        poolflip[e].append(fr); poolreg[e].append(rg)
        cells.append(f"{fr*100:4.0f}%,{rg:+.3f}")
    print(f"  {t[:38]:38s} {len(s):>3} {sdrel:>9.3f} {topgap:>9.2f} | " + "  ".join(cells), flush=True)
print("\n  POOLED (mean over high-Δ tasks):", flush=True)
for e in EPS:
    print(f"    eps={e}: flip {np.mean(poolflip[e])*100:4.0f}%   regret {np.mean(poolreg[e]):+.3f} beat_ratio", flush=True)

# ===================== Test B: cactus tree rerouting (agent_runs) =====================
print("\n=== TEST B: tree rerouting on cactus (per-parent argmax-child flip vs eps) ===", flush=True)
ROOT = "/research/d7/spc/yzyang4/foreagent_agentruns"
decisions = []   # each = np.array of children val (oriented higher=better), >=2 entries
pathlens = []
for run in glob.glob(os.path.join(ROOT, "agent_runs", "*", "*")):
    if "aerial-cactus" not in run:
        continue
    jp = os.path.join(run, "logs", "journal.json")
    if not os.path.exists(jp):
        continue
    try:
        J = json.load(open(jp))
    except Exception:
        continue
    nodes = J.get("nodes") if isinstance(J, dict) else J
    n2p = J.get("node2parent", {}) if isinstance(J, dict) else {}
    if not nodes:
        continue
    byid = {str(n.get("id")): n for n in nodes}
    children = defaultdict(list)
    for n in nodes:
        if n.get("is_buggy"):
            continue
        val, mx = parse_metric(n.get("metric"))
        if val is None:
            continue
        par = n.get("parent") or n2p.get(str(n.get("id")))
        if par is None:
            continue
        v = val if (mx if mx is not None else True) else -val
        children[str(par)].append(v)
    for par, ch in children.items():
        if len(ch) >= 2:
            decisions.append(np.array(ch, float))
    pathlens.append(len([n for n in nodes if not n.get("is_buggy")]))

if decisions:
    allv = np.concatenate(decisions)
    SDv = allv.std() if allv.std() > 1e-12 else 1.0
    Lmed = int(np.median(pathlens)) if pathlens else 10
    print(f"  cactus: {len(decisions)} multi-child decisions, val-SD={SDv:.4f}, median nodes/run~{Lmed}", flush=True)
    for e in EPS:
        flips = []
        for ch in decisions:
            best = int(np.argmax(ch)); f = 0
            for _ in range(DRAWS):
                if int(np.argmax(ch + RNG.normal(0, e * SDv, len(ch)))) != best:
                    f += 1
            flips.append(f / DRAWS)
        p = float(np.mean(flips))
        pathdiv = 1 - (1 - p) ** max(Lmed, 1)
        print(f"    eps={e}: per-decision flip {p*100:4.0f}%  -> path-divergence over ~{Lmed} steps ~ {pathdiv*100:3.0f}%", flush=True)
else:
    print("  (no cactus multi-child decisions found in cache)", flush=True)

print("\n=== READ: GREEN(2) if at a realistic substrate eps (map via SD/|mean|; substrate~1-9% of metric) the", flush=True)
print("    flip%/regret is non-trivial AND path-divergence >> per-decision flip (amplification). RED if all tiny. ===", flush=True)
print("=== done ===", flush=True)
