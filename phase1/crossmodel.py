"""Make-or-break, PART 1 — cross-MODEL replication on MLE data.
Q: does 'frozen rep DECODES the true grade but is NOT usable over the free self-report for SELECTION'
   hold across model FAMILIES, or is it a Qwen artifact? Run once per model via H1_MODEL (GPU, 4bit).
Self-contained; reads phase1/cards_cur.jsonl. Prints a per-model verdict.
Same task (SELECTION), same free baseline (self-report val score) across models -> controls those confounds.
"""
import os
import json
import numpy as np

MODEL = os.environ["H1_MODEL"]
name = os.path.basename(MODEL.rstrip("/"))
from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.h1_ablation import extract_multilayer, mask_selfreport
from phase1.b1_detector import _spear, _dual_ridge

NL = json.load(open(os.path.join(MODEL, "config.json")))["num_hidden_layers"]
LAYERS = sorted(set(min(NL - 1, max(1, int(round(NL * f)))) for f in (0.5, 0.65, 0.75, 0.85)))
print(f"=== MODEL={name} n_layers={NL} probe_layers(rel-depth)={LAYERS} ===", flush=True)

cards = labeled(load_cards("phase1/cards_cur.jsonl"))
y = np.array([c.y for c in cards], float)
tasks = np.array([c.task.name for c in cards])
vraw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else np.nan) for c in cards])
v = np.full(len(cards), np.nan)  # self-report, sign-corrected so higher=better
for t in np.unique(tasks):
    m = tasks == t
    h = next(c for c in cards if c.task.name == t).task.higher_is_better
    v[m] = vraw[m] if h else -vraw[m]
print(f"N={len(cards)} tasks={ {t: int((tasks==t).sum()) for t in np.unique(tasks)} }", flush=True)

print("extracting (code-only, self-report-masked)...", flush=True)
fA, eA = extract_multilayer([mask_selfreport(c) for c in cards], LAYERS, 4000)


def loto(X):  # cross-task DECODABILITY
    sp = []
    for t in np.unique(tasks):
        te = tasks == t
        if te.sum() < 8:
            continue
        sp.append(_spear(_dual_ridge(X[~te], y[~te], X[te]), y[te]))
    return float(np.mean(sp))


def probe_intra(X):  # per-task probe SELECTION ability (honest 50/50 CV, 20 resamples)
    out = {}
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < 25:
            continue
        vv = []
        for r in range(20):
            p = np.random.default_rng(r).permutation(idx)
            k = len(p) // 2
            vv.append(_spear(_dual_ridge(X[p[:k]], y[p[:k]], X[p[k:]]), y[p[k:]]))
        out[t] = float(np.mean(vv))
    return out


sr = {}  # free self-report SELECTION ability (the bar to beat)
for t in np.unique(tasks):
    m = tasks == t
    if m.sum() < 25:
        continue
    ok = m & ~np.isnan(v)
    sr[t] = _spear(v[ok], y[ok]) if ok.sum() > 5 else float("nan")

best = None
print(f"{'layer':>6} {'LOTOdec':>8}  per-task: probe_intra vs self-report (usable=probe>sr)", flush=True)
for L in LAYERS:
    X = np.hstack([fA[L], eA])
    dec = loto(X)
    pr = probe_intra(X)
    beats = sum(1 for t in pr if pr[t] > sr.get(t, 9))
    ln = "  ".join(f"{t[:8]}:pr{pr[t]:+.2f}/sr{sr.get(t, float('nan')):+.2f}" for t in sorted(pr))
    print(f"{L:>6} {dec:>+8.3f}  {ln}  [probe>sr {beats}/{len(pr)}]", flush=True)
    if best is None or dec > best[1]:
        best = (L, dec, beats, len(pr))

L, dec, beats, nt = best
holds = dec > 0.05 and beats == 0
print(f"\n=== {name}: best-decode layer {L} LOTO-decodability={dec:+.3f}; probe beats self-report {beats}/{nt} tasks", flush=True)
print(f"=== DISSOCIATION {'HOLDS' if holds else 'DIFFERS'} for {name} "
      f"(decodable={dec > 0.05}, not-usable-over-selfreport={beats == 0}) ===", flush=True)
