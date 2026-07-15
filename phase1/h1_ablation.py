"""H1 ablation — rigorous representation-probing (advisor reframe + deep-research improvements).

On the SAME frozen Qwen2.5-Coder-7B representation (no finetuning), sweep:
  - LAYER: {4,7,14,21,28} of 28 (one forward pass gives all hidden_states, so this is ~free).
    Lit: mid layers often beat last (2606.21917 / 2502.02013 / 2510.02934).
  - PROBE: single-layer ridge vs MULTI-LAYER STACK (concat) ridge. Lit: stacking helps (2604.13386).
  - CONFOUND RESIDUALIZATION: remove the linear effect of code length/#lines from every feature dim
    (fit on train fold only), show the grade signal survives -> not a surface/length artifact.
    Lit: template 2606.14530 (AUC survives length residualization); warning 2606.02907 (probe
    decodability can be a pure surface artifact) -> this control is make-or-break for H1.
  - SELF-REPORT ABLATION: features from prompts with val_at_low/val_curve/parent_val masked
    (H1's core independence claim; our novelty vs OPENIA/2512.07404 which do binary unit-correctness).

Metrics: within-task 5-fold CV Spearman (intra, mean over tasks x 3 seeds) + leave-one-task-out (loto).
"""
import copy
import numpy as np

from phase1.cards import load_cards
from phase1.critics.base import Ridge
from phase1.dataset import labeled, tasks_of

MODEL = __import__("os").environ.get("H1_MODEL", "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct")
LAYERS = [int(x) for x in __import__("os").environ.get("H1_LAYERS", "4,7,14,21,28").split(",")]
LAM = 2.0
SEEDS = [0, 1, 2]
MAXCODE = 4000


def _spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() < 1e-9 or rb.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def mask_selfreport(c):
    m = copy.deepcopy(c)
    m.obs.val_at_low = None
    m.obs.val_curve = []
    m.lineage.parent_val = None
    return m


def extract_multilayer(cards, layers, max_code):
    """One forward pass -> per-layer [mean-pool, last-token] (2H) for each requested layer; +last entropy."""
    import torch
    from phase1.critics.qwen_backend import load_model, _chat, build_value_prompt
    model, tok = load_model(MODEL, "4bit")
    prompts = [_chat(tok, build_value_prompt(c, max_code=max_code)) for c in cards]
    per = {L: [] for L in layers}
    ents = []
    bs = 2
    for i in range(0, len(prompts), bs):
        enc = tok(prompts[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=2048).to(model.device)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
        m = enc["attention_mask"].unsqueeze(-1)
        idx = enc["attention_mask"].sum(1) - 1
        ar = torch.arange(enc["input_ids"].size(0))
        for L in layers:
            hs = out.hidden_states[L]
            mp = (hs * m.to(hs.dtype)).sum(1) / m.sum(1).clamp(min=1)
            per[L].append(torch.cat([mp.float(), hs[ar, idx].float()], -1).cpu().numpy())
        ll = out.logits[ar, idx].float(); lp = torch.log_softmax(ll, -1)
        ents.append((-(lp.exp() * lp).sum(-1)).cpu().numpy())
        del out; torch.cuda.empty_cache()
    ent = np.concatenate(ents)[:, None]
    return {L: np.vstack(per[L]) for L in layers}, ent


def _resid(Xtr, Xte, Ctr, Cte):
    C1tr = np.hstack([Ctr, np.ones((len(Ctr), 1))])
    beta, *_ = np.linalg.lstsq(C1tr, Xtr, rcond=None)
    C1te = np.hstack([Cte, np.ones((len(Cte), 1))])
    return Xtr - C1tr @ beta, Xte - C1te @ beta


def _fit_pred(Xtr, ytr, Xte, C=None, itr=None, ite=None):
    """Ridge via the DUAL form (N x N), identical solution to primal (X^T X+λI)^-1 X^T y but fast when
    D >> N — required for the ~35k-dim multi-layer stack. Standardize on train, optional confound resid."""
    if C is not None:
        Xtr, Xte = _resid(Xtr, Xte, C[itr], C[ite])
    mu = Xtr.mean(0); sd = Xtr.std(0); sd[sd < 1e-8] = 1.0
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    n = len(ytr)
    alpha = np.linalg.solve(Xtr @ Xtr.T + LAM * np.eye(n), ytr)   # (XX^T+λI)^-1 y
    return (Xte @ Xtr.T) @ alpha                                   # Xte X^T α


def intra(X, y, tasks, C=None, folds=5):
    vals = []
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        for s in SEEDS:
            order = np.random.default_rng(s).permutation(idx)
            pred = np.full(len(y), np.nan)
            for f in np.array_split(order, folds):
                tr = np.setdiff1d(idx, f)
                pred[f] = _fit_pred(X[tr], y[tr], X[f], C, tr, f)
            vals.append(_spear(pred[idx], y[idx]))
    return float(np.mean(vals)) if vals else float("nan")


def loto(X, y, tasks, C=None):
    vals = []
    for t in np.unique(tasks):
        te = np.where(tasks == t)[0]; tr = np.where(tasks != t)[0]
        if len(te) < 4:
            continue
        pred = _fit_pred(X[tr], y[tr], X[te], C, tr, te)
        vals.append(_spear(pred, y[te]))
    return float(np.mean(vals)) if vals else float("nan")


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available — resubmit on another node")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    C = np.array([[np.log1p(len(c.code or "")), np.log1p((c.code or "").count("\n"))] for c in cards], float)
    print(f"{len(cards)} cards, tasks={list(np.unique(tasks))}", flush=True)

    for cond, cds in [("normal", cards), ("ablated(self-report masked)", [mask_selfreport(c) for c in cards])]:
        print(f"\n===== condition: {cond} — extracting {len(LAYERS)}-layer frozen features =====", flush=True)
        feats, ent = extract_multilayer(cds, LAYERS, MAXCODE)
        print(f"{'probe':22s} {'intra':>8} {'loto':>8} | {'intra+resid':>12} {'loto+resid':>11}", flush=True)
        # per-layer single
        for L in LAYERS:
            X = np.hstack([feats[L], ent])
            print(f"layer {L:<3d} (ridge)      {intra(X,y,tasks):>8.3f} {loto(X,y,tasks):>8.3f} | "
                  f"{intra(X,y,tasks,C):>12.3f} {loto(X,y,tasks,C):>11.3f}", flush=True)
        # multi-layer stack (concat all swept layers)
        Xs = np.hstack([feats[L] for L in LAYERS] + [ent])
        print(f"stack {str(LAYERS):16s} {intra(Xs,y,tasks):>8.3f} {loto(Xs,y,tasks):>8.3f} | "
              f"{intra(Xs,y,tasks,C):>12.3f} {loto(Xs,y,tasks,C):>11.3f}", flush=True)
    # confound-only baseline (how much code length alone predicts the grade)
    print(f"\n=== confound-only baseline (ridge on [log len, log nlines] -> grade) ===", flush=True)
    print(f"intra {intra(C,y,tasks):.3f}  loto {loto(C,y,tasks):.3f}  (this is the 'is it just length?' floor)", flush=True)


if __name__ == "__main__":
    main()
