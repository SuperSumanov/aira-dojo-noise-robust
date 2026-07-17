"""SAE prototype -- can a sparse decomposition of the frozen layer-21 representation isolate a few
NAMEABLE directions that carry the 0.20 grade residual the hand-feature checklist (A1) missed?

Pipeline (single GPU, frozen model, no finetune):
  1. extract PER-TOKEN layer-21 activations over the 289 cards' value-prompts (enough samples for an SAE,
     unlike 289 pooled vectors).
  2. train a small L1 sparse autoencoder (dict=1024) on those token activations.
  3. per-card feature = max activation over the card's tokens -> (289, 1024) sparse feature matrix.
  4. checks: (a) do SAE features predict grade as well as the dense probe? (b) does a SPARSE handful
     capture the RESIDUAL grade (grade beyond A1 hand-features)? (c) interpret the top residual features
     by their max-activating code tokens -- are they nameable?
"""
import re
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _dual_ridge
from phase1.a1_mechanism import feats
from phase1.critics.qwen_backend import load_model, build_value_prompt, _chat

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
LAYER = 21
DICT = 1024
L1 = 2e-3
EPOCHS = 20
MAXCODE = 2000
MAXLEN = 1024


def residual_grade(cards, y, tasks):
    names = list(feats(cards[0].code).keys())
    H = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    r = np.full(len(y), np.nan)
    for t in np.unique(tasks):                          # residualize grade on hand-features within task
        m = np.where(tasks == t)[0]
        Ht = H[m]; mu = Ht.mean(0); sd = Ht.std(0); sd[sd < 1e-8] = 1.0
        Ht = np.column_stack([np.ones(len(m)), (Ht - mu) / sd])
        beta, *_ = np.linalg.lstsq(Ht, _z(y[m]), rcond=None)
        r[m] = _z(y[m]) - Ht @ beta
    return r


def main():
    import torch
    import torch.nn as nn
    if not torch.cuda.is_available():
        raise SystemExit("CUDA required")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    r = residual_grade(cards, y, tasks)

    model, tok = load_model(MODEL, "4bit")
    dev = model.device
    print("extracting per-token layer-21 activations ...", flush=True)
    acts, tok_card, ids_by_card = [], [], []
    for i, c in enumerate(cards):
        prompt = _chat(tok, build_value_prompt(c, max_code=MAXCODE))
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=MAXLEN).to(dev)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
        h = out.hidden_states[LAYER][0].float().cpu().numpy()      # (T, H)
        acts.append(h); tok_card.append(np.full(len(h), i)); ids_by_card.append(enc["input_ids"][0].cpu().numpy())
        del out
        if i % 60 == 0:
            torch.cuda.empty_cache()
            print(f"  {i}/{len(cards)}", flush=True)
    A = np.concatenate(acts).astype(np.float32)          # (Ntok, H)
    tok_card = np.concatenate(tok_card)
    Hd = A.shape[1]
    mu = A.mean(0); A = A - mu
    scale = np.sqrt((A ** 2).sum(1)).mean()
    A = A / (scale + 1e-6)
    print(f"activations {A.shape}, training SAE dict={DICT} L1={L1} ...", flush=True)

    # ---- SAE ----
    Wenc = nn.Parameter(torch.randn(Hd, DICT, device=dev) * 0.01)
    Wdec = nn.Parameter(torch.randn(DICT, Hd, device=dev) * 0.01)
    bpre = nn.Parameter(torch.zeros(Hd, device=dev))
    opt = torch.optim.Adam([Wenc, Wdec, bpre], lr=1e-3)
    At = torch.tensor(A, device=dev)
    n = len(A); bs = 4096
    for ep in range(EPOCHS):
        perm = torch.randperm(n, device=dev)
        tot = 0.0
        for j in range(0, n, bs):
            idx = perm[j:j + bs]; x = At[idx]
            f = torch.relu((x - bpre) @ Wenc)
            xhat = f @ Wdec + bpre
            loss = ((xhat - x) ** 2).mean() + L1 * f.abs().mean()
            opt.zero_grad(); loss.backward()
            with torch.no_grad():                          # unit-norm decoder rows
                Wdec.data /= (Wdec.data.norm(dim=1, keepdim=True) + 1e-8)
            opt.step(); tot += loss.item()
        if ep % 4 == 0 or ep == EPOCHS - 1:
            with torch.no_grad():
                f = torch.relu((At - bpre) @ Wenc)
                spars = (f > 1e-5).float().sum(1).mean().item()
            print(f"  epoch {ep} loss {tot/(n//bs):.4f}  avg active feats/token {spars:.1f}", flush=True)

    # ---- per-card features (max over tokens) ----
    with torch.no_grad():
        F = torch.relu((At - bpre) @ Wenc).cpu().numpy()     # (Ntok, DICT)
    Fc = np.zeros((len(cards), DICT))
    for i in range(len(cards)):
        m = tok_card == i
        if m.any():
            Fc[i] = F[m].max(0)
    live = (Fc > 1e-5).any(0)
    print(f"\nSAE: {live.sum()}/{DICT} live features across cards", flush=True)

    # ---- (a) do SAE features predict grade? ----
    def oof(X, target):
        pred = np.full(len(y), np.nan)
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < 7:
                continue
            for f in np.array_split(np.random.default_rng(0).permutation(idx), 5):
                tr = np.setdiff1d(idx, f)
                pred[f] = _dual_ridge(X[tr], target[tr], X[f])
        return pred
    def pts(pred, target):
        v = [_spear(pred[tasks == t], target[tasks == t]) for t in np.unique(tasks)
             if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
        return float(np.mean(v)) if v else float("nan")
    Fl = Fc[:, live]
    print(f"  SAE-features -> grade   (per-task 5-fold): {pts(oof(Fl, y), y):+.3f}   (dense probe ~0.29)", flush=True)
    print(f"  SAE-features -> RESIDUAL (beyond checklist): {pts(oof(Fl, r), r):+.3f}   (dense residual ~0.20)", flush=True)

    # ---- (b) which few features carry the residual? ----
    corr = np.array([_spear(Fc[:, j], r) if live[j] else 0.0 for j in range(DICT)])
    top = np.argsort(-np.abs(corr))[:6]
    print("\n=== top residual-carrying SAE features (interpret by max-activating code) ===", flush=True)
    for j in top:
        ci = int(np.argmax([Fc[i, j] for i in range(len(cards))]))
        # find the max-activating token position within that card
        m = np.where(tok_card == ci)[0]
        tpos = m[np.argmax(F[m, j])] - m[0]
        ids = ids_by_card[ci]
        lo, hi = max(0, tpos - 8), min(len(ids), tpos + 8)
        ctx = tok.decode(ids[lo:hi]).replace("\n", " ")
        ctx = re.sub(r"\s+", " ", ctx)[:110]
        print(f"  feat {j:4d}  corr(resid) {corr[j]:+.3f}  top card={cards[ci].task.name[:8]}  ctx: …{ctx}…", flush=True)

    np.savez("phase1/_sae_out.npz", Fc=Fc, corr=corr, live=live, y=y, r=r, tasks=tasks)
    print("\nsaved phase1/_sae_out.npz\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
