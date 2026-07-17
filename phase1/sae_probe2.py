"""SAE prototype v2 -- fixes v1's two flaws: (1) real sparsity via a TopK SAE (exactly k active features
per token, the modern robust approach; no L1 tuning), (2) self-report-ablated (code-only) prompts so the
residual is pure code, not self-report leakage. Same question: can a sparse decomposition of the frozen
layer-21 representation isolate a few NAMEABLE directions carrying the grade residual the A1 checklist missed?
"""
import re
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _dual_ridge
from phase1.a1_mechanism import feats
from phase1.h1_ablation import mask_selfreport
from phase1.critics.qwen_backend import load_model, build_value_prompt, _chat

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
LAYER = 21
DICT = 1024
TOPK = 24
EPOCHS = 30
MAXCODE = 2000
MAXLEN = 1024


def residual_grade(cards, y, tasks):
    names = list(feats(cards[0].code).keys())
    H = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    r = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        m = np.where(tasks == t)[0]
        Ht = H[m]; mu = Ht.mean(0); sd = Ht.std(0); sd[sd < 1e-8] = 1.0
        Ht = np.column_stack([np.ones(len(m)), (Ht - mu) / sd])
        beta, *_ = np.linalg.lstsq(Ht, _z(y[m]), rcond=None)
        r[m] = _z(y[m]) - Ht @ beta
    return r


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA required")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    r = residual_grade(cards, y, tasks)
    mcards = [mask_selfreport(c) for c in cards]        # code-only

    model, tok = load_model(MODEL, "4bit"); dev = model.device
    print("extracting per-token layer-21 activations (code-only) ...", flush=True)
    acts, tok_card, ids_by_card = [], [], []
    for i, c in enumerate(mcards):
        enc = tok(_chat(tok, build_value_prompt(c, max_code=MAXCODE)), return_tensors="pt",
                  truncation=True, max_length=MAXLEN).to(dev)
        with torch.no_grad():
            h = model(**enc, output_hidden_states=True).hidden_states[LAYER][0].float().cpu().numpy()
        acts.append(h); tok_card.append(np.full(len(h), i)); ids_by_card.append(enc["input_ids"][0].cpu().numpy())
        if i % 60 == 0:
            torch.cuda.empty_cache(); print(f"  {i}/{len(cards)}", flush=True)
    A = np.concatenate(acts).astype(np.float32); tok_card = np.concatenate(tok_card); Hd = A.shape[1]
    bpre0 = A.mean(0); A = A - bpre0; A /= (np.sqrt((A ** 2).sum(1)).mean() + 1e-6)
    print(f"activations {A.shape}, training TopK SAE dict={DICT} k={TOPK} ...", flush=True)

    Wenc = torch.randn(Hd, DICT, device=dev) * 0.01
    Wdec = torch.randn(DICT, Hd, device=dev) * 0.01
    bpre = torch.zeros(Hd, device=dev)
    for p in (Wenc, Wdec, bpre):
        p.requires_grad_(True)
    opt = torch.optim.Adam([Wenc, Wdec, bpre], lr=1e-3)
    At = torch.tensor(A, device=dev); n = len(A); bs = 4096

    def encode(x):
        pre = (x - bpre) @ Wenc
        vals, idx = pre.topk(TOPK, dim=1)
        f = torch.zeros_like(pre)
        return f.scatter(1, idx, torch.relu(vals))
    for ep in range(EPOCHS):
        perm = torch.randperm(n, device=dev); tot = 0.0
        for j in range(0, n, bs):
            x = At[perm[j:j + bs]]
            f = encode(x); xhat = f @ Wdec + bpre
            loss = ((xhat - x) ** 2).mean()
            opt.zero_grad(); loss.backward()
            with torch.no_grad():
                Wdec.data /= (Wdec.data.norm(dim=1, keepdim=True) + 1e-8)
            opt.step(); tot += loss.item()
        if ep % 6 == 0 or ep == EPOCHS - 1:
            print(f"  epoch {ep} recon-loss {tot/(n//bs):.4f}", flush=True)

    with torch.no_grad():
        F = encode(At).cpu().numpy()
    Fc = np.zeros((len(cards), DICT))
    for i in range(len(cards)):
        m = tok_card == i
        if m.any():
            Fc[i] = F[m].max(0)
    live = (Fc > 1e-6).any(0)
    print(f"\nTopK SAE: {live.sum()}/{DICT} live features (k={TOPK}/token enforced)", flush=True)

    def oof(X, tgt):
        pred = np.full(len(y), np.nan)
        for t in np.unique(tasks):
            idx = np.where(tasks == t)[0]
            if len(idx) < 7:
                continue
            for f in np.array_split(np.random.default_rng(0).permutation(idx), 5):
                tr = np.setdiff1d(idx, f); pred[f] = _dual_ridge(X[tr], tgt[tr], X[f])
        return pred

    def pts(pred, tgt):
        v = [_spear(pred[tasks == t], tgt[tasks == t]) for t in np.unique(tasks)
             if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
        return float(np.mean(v)) if v else float("nan")
    Fl = Fc[:, live]
    print(f"  SAE-features -> grade    : {pts(oof(Fl, y), y):+.3f}   (dense probe ~0.29)", flush=True)
    print(f"  SAE-features -> RESIDUAL : {pts(oof(Fl, r), r):+.3f}   (dense residual ~0.20)", flush=True)

    corr = np.array([_spear(Fc[:, j], r) if live[j] else 0.0 for j in range(DICT)])
    top = np.argsort(-np.abs(corr))[:6]
    print("\n=== top residual-carrying features -- 2 max-activating code snippets each ===", flush=True)
    for j in top:
        order = np.argsort(-Fc[:, j])[:2]
        print(f"  feat {j:4d}  corr(resid) {corr[j]:+.3f}:", flush=True)
        for ci in order:
            m = np.where(tok_card == ci)[0]
            tpos = m[np.argmax(F[m, j])] - m[0]; ids = ids_by_card[ci]
            ctx = re.sub(r"\s+", " ", tok.decode(ids[max(0, tpos - 8):tpos + 8]))[:100]
            print(f"       [{cards[ci].task.name[:8]}] …{ctx}…", flush=True)
    np.savez("phase1/_sae2_out.npz", Fc=Fc, corr=corr, live=live, y=y, r=r, tasks=tasks)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
