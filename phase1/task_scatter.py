"""(sigma, Delta) task scatter -- the make-or-break gate for the anti-fragile eval-as-object direction.
Do our REACHABLE tasks have the high-headroom (Delta) AND affordable quadrant that eval/substrate-noise
effects need? If only EXPENSIVE tasks have headroom (the MF-Stage0 ghost), the direction needs re-scoping.

Per task, offline from existing data:
  Delta (headroom) = IQR of beat_ratio (leaderboard-percentile, cross-task comparable) among the agent's
                     solutions -> spread the search navigates. High = room for selection/noise to matter.
  sigma (eval-noise) = 1 - Spearman(self-report val, external true grade) -> noisiness of the search signal.
  afford = task-type class (cheap-tabular / moderate-nlp / expensive-img-audio).
Sources: our 289 (val+grade), FOREAGENT subset_50 (beat_ratio, 26 tasks), FOREAGENT agent_runs (val+grade+beat).
"""
import os
import re
import ast
import json
import glob
from collections import defaultdict

import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled

NUM = re.compile(r"[-+]?\d*\.?\d+")


def pf(s):
    if not s:
        return None
    m = NUM.findall(str(s))
    return float(m[-1]) if m else None


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
    return pf(m), None


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b)); a, b = a[m], b[m]
    if len(a) < 8:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() < 1e-9 or rb.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def iqr(x):
    x = np.asarray([v for v in x if v is not None], float); x = x[~np.isnan(x)]
    return float(np.percentile(x, 75) - np.percentile(x, 25)) if len(x) >= 4 else float("nan")


def afford(task):
    t = task.lower()
    if any(k in t for k in ["aptos", "dog-breed", "leaf-class", "plant-path", "iceberg", "tgs-salt",
                            "cactus", "histopath", "birds", "volcanic", "whale", "speech", "mlsp"]):
        return "EXPENSIVE(img/audio)"
    if any(k in t for k in ["tabular", "spaceship", "nomad", "taxi", "pizza", "ventilator", "insult",
                            "transparent", "pawpularity"]):
        return "CHEAP(tabular)"
    return "MODERATE(nlp)"


def main():
    T = defaultdict(lambda: {"beat": [], "val": [], "true": []})

    # our 289
    for c in labeled(load_cards("phase1/cards_real_mm.jsonl")):
        h = c.task.higher_is_better
        T[c.task.name]["true"].append(c.y if h else -c.y)
        vv = c.obs.val_at_low
        T[c.task.name]["val"].append((vv if h else -vv) if vv is not None else np.nan)

    # FOREAGENT subset_50 (beat_ratio only)
    try:
        for r in json.load(open("/research/d7/spc/yzyang4/foreagent_slice/slice.json")):
            if r.get("beat_ratio") is not None:
                T[r["task"]]["beat"].append(r["beat_ratio"])
    except Exception as e:
        print("subset load err:", e, flush=True)

    # FOREAGENT agent_runs journals (val + true + beat)
    ROOT = "/research/d7/spc/yzyang4/foreagent_agentruns"
    for run in glob.glob(os.path.join(ROOT, "agent_runs", "*", "*")):
        if os.path.basename(os.path.dirname(run)).startswith("__"):
            continue
        jp = os.path.join(run, "logs", "journal.json")
        if not os.path.exists(jp):
            continue
        try:
            J = json.load(open(jp))
        except Exception:
            continue
        nodes = J.get("nodes") if isinstance(J, dict) else J
        if not nodes:
            continue
        evl = {}; task = None
        for ef in glob.glob(os.path.join(run, "logs", "all_nodes", "*", "eval_output.json")):
            short = os.path.basename(os.path.dirname(ef)).replace("node_", "")
            try:
                ev = json.load(open(ef))
            except Exception:
                continue
            sc = ev.get("score")
            if sc is None or not ev.get("valid_submission", False):
                continue
            evl[short] = (float(sc), bool(ev.get("is_lower_better", False)), ev.get("beat_ratio"))
            task = ev.get("competition_id", task)
        if not evl or task is None:
            continue
        for n in nodes:
            if n.get("is_buggy"):
                continue
            cs = evl.get(str(n.get("id"))[:8])
            if cs is None:
                continue
            val, mx = parse_metric(n.get("metric"))
            if val is None:
                continue
            vmax = mx if mx is not None else (not cs[1])
            T[task]["val"].append(val if vmax else -val)
            T[task]["true"].append(-cs[0] if cs[1] else cs[0])
            if cs[2] is not None:
                T[task]["beat"].append(cs[2])

    rows = []
    for t, d in T.items():
        nb = len([x for x in d["beat"] if x is not None])
        nt = len(d["true"])
        dlt = iqr(d["beat"]) if nb >= 4 else float("nan")
        medb = float(np.nanmedian([x for x in d["beat"] if x is not None])) if nb >= 1 else float("nan")
        sig = (1 - spear(d["val"], d["true"])) if (nt >= 8 and np.sum(~np.isnan(np.asarray(d["val"], float))) >= 8) else float("nan")
        rows.append((t, max(nb, nt), dlt, medb, sig, afford(t)))

    print(f"\n{'task':40s} {'n':>4} {'Δ=beatIQR':>10} {'medBeat':>8} {'σ=1-Sp(v,y)':>12}  afford", flush=True)
    for t, n, dlt, medb, sig, af in sorted(rows, key=lambda r: -(r[2] if not np.isnan(r[2]) else -9)):
        ds = f"{dlt:>10.3f}" if not np.isnan(dlt) else f"{'--':>10}"
        ms = f"{medb:>8.3f}" if not np.isnan(medb) else f"{'--':>8}"
        ss = f"{sig:>12.3f}" if not np.isnan(sig) else f"{'--':>12}"
        print(f"  {t[:38]:38s} {n:>4} {ds} {ms} {ss}  {af}", flush=True)

    # verdict
    HI = 0.15
    cheap = [(t, dlt) for t, n, dlt, medb, sig, af in rows if af.startswith("CHEAP") and not np.isnan(dlt)]
    cheap_hi = [t for t, dlt in cheap if dlt > HI]
    exp_hi = [t for t, n, dlt, medb, sig, af in rows if af.startswith("EXPENSIVE") and not np.isnan(dlt) and dlt > HI]
    print("\n=== VERDICT (Δ=beat_ratio IQR; HI threshold 0.15) ===", flush=True)
    print(f"  CHEAP tasks measured: {[(t, round(d,2)) for t,d in cheap]}", flush=True)
    print(f"  CHEAP with Δ>{HI}: {cheap_hi}", flush=True)
    print(f"  EXPENSIVE with Δ>{HI}: {exp_hi}", flush=True)
    if cheap_hi:
        print(f"  GREEN: affordable high-headroom tasks EXIST {cheap_hi} -> the direction is runnable on cheap tasks.", flush=True)
    elif exp_hi:
        print(f"  AMBER: headroom lives in EXPENSIVE tasks {exp_hi}; cheap tasks are low-Δ (MF-Stage0 ghost confirmed)"
              " -> re-scope tasks (find affordable high-Δ, or budget for the expensive ones) before GPU.", flush=True)
    else:
        print("  RED: no task shows meaningful headroom Δ in reach -> eval/substrate-noise effects can't be large; rethink.", flush=True)
    print("\n=== done ===", flush=True)


if __name__ == "__main__":
    main()
