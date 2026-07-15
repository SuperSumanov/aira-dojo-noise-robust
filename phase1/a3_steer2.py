"""A3a-v2 — same causal-steering gate, but with a SENSITIVE readout (v1's greedy score was quantized to 7
buckets and anti-correlated with grade, so it could not resolve a steering effect).

Sensitive behavioral readout: teacher-force the assistant to have written `SCORE: 0.` and read the model's
next-token distribution over the digit tokens {0..9}; soft_score = E[digit]/10 (continuous in [0,1)). One
forward pass per (card,dir,alpha), no generation. Steer layer-21 residual with alpha*sigma*v_hat (CAA).
Question unchanged: does steering the QUALITY direction move the model's (soft) score MORE than a random
direction? GREEN -> behaviorally usable/steerable -> A3b worth it. Controls: random, code-length.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.critics.qwen_backend import load_model, build_value_prompt, _chat
from phase1.h1_ablation import mask_selfreport

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
STEER_HS = 21
ALPHAS = [-3.0, -1.5, 0.0, 1.5, 3.0]
SEED = 0
OUT = "phase1/_a3a2_scores.npz"


def _unit(v):
    n = np.linalg.norm(v)
    return v / (n if n > 1e-8 else 1.0)


def _sp(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    rng = np.random.default_rng(SEED)
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    loglen = np.array([np.log(max(len(c.code or ""), 1)) for c in cards], float)
    mcards = [mask_selfreport(c) for c in cards]

    model, tok = load_model(MODEL, "4bit")
    Hd = model.config.hidden_size
    hook_layer = model.model.layers[STEER_HS - 1]
    digit_ids = [tok.convert_tokens_to_ids(d) for d in "0123456789"]
    print(f"H={Hd} hook=layers[{STEER_HS-1}] digit_ids={digit_ids}", flush=True)
    assert all(i is not None and i >= 0 for i in digit_ids), "bad digit token ids"
    digits = torch.arange(10, device=model.device).float()
    dtok = torch.tensor(digit_ids, device=model.device)

    def meanpool_hidden(cs):
        outs = []
        for i in range(0, len(cs), 2):
            chunk = [_chat(tok, build_value_prompt(c, max_code=4000)) for c in cs[i:i + 2]]
            enc = tok(chunk, return_tensors="pt", padding=True, truncation=True, max_length=2048).to(model.device)
            with torch.no_grad():
                out = model(**enc, output_hidden_states=True)
            hs = out.hidden_states[STEER_HS]
            mask = enc["attention_mask"].unsqueeze(-1).to(hs.dtype)
            outs.append(((hs * mask).sum(1) / mask.sum(1).clamp(min=1)).float().cpu().numpy())
            del out, hs; torch.cuda.empty_cache()
        return np.vstack(outs)

    print("collecting layer-21 mean-pooled hidden ...", flush=True)
    Hmp = meanpool_hidden(mcards)

    def contrastive_dir(score):
        ds = []
        for t in np.unique(tasks):
            m = np.where(tasks == t)[0]; s = score[m]
            hi = m[s >= np.quantile(s, 2 / 3)]; lo = m[s <= np.quantile(s, 1 / 3)]
            if len(hi) and len(lo):
                ds.append(_unit(Hmp[hi].mean(0) - Hmp[lo].mean(0)))
        return _unit(np.mean(ds, axis=0))

    dirs = {"quality": contrastive_dir(y), "random": _unit(rng.standard_normal(Hd)), "length": contrastive_dir(loglen)}
    sigmas = {k: float(np.std(Hmp @ v)) for k, v in dirs.items()}
    print("sigmas:", {k: round(s, 3) for k, s in sigmas.items()},
          "cos(q,len)=", round(float(dirs["quality"] @ dirs["length"]), 3), flush=True)

    steer = {"vec": None}

    def hook(mod, inp, out):
        if steer["vec"] is None:
            return out
        if isinstance(out, tuple):
            return (out[0] + steer["vec"].to(out[0].dtype),) + tuple(out[1:])
        return out + steer["vec"].to(out.dtype)
    handle = hook_layer.register_forward_hook(hook)

    def soft_score(card):
        prompt = _chat(tok, build_value_prompt(card, max_code=4000)) + "SCORE: 0."
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
        with torch.no_grad():
            out = model(**enc)
        p = torch.softmax(out.logits[0, -1, dtok].float(), dim=-1)
        return float((p * digits).sum() / 10.0)

    scores = {d: np.full((len(ALPHAS), len(mcards)), np.nan) for d in dirs}
    order = sorted(range(len(ALPHAS)), key=lambda i: abs(ALPHAS[i]))
    for dname, v in dirs.items():
        vt = torch.tensor(v, device=model.device)
        for ai in order:
            a = ALPHAS[ai]
            steer["vec"] = None if a == 0.0 else (a * sigmas[dname]) * vt
            scores[dname][ai] = [soft_score(c) for c in mcards]
            print(f"  {dname:8s} a={a:+.1f}  mean={np.nanmean(scores[dname][ai]):.4f} std={np.nanstd(scores[dname][ai]):.4f}", flush=True)
        np.savez(OUT, **scores, alphas=np.array(ALPHAS))
    handle.remove()

    i0 = order[0]
    print(f"\ncorr(soft baseline, true grade y) = {_sp(scores['quality'][i0], y):+.3f}  "
          f"(sanity: continuous readout, {len(np.unique(np.round(scores['quality'][i0],4)))} unique vals)", flush=True)

    A = np.array(ALPHAS)

    def slopes(mat):
        out = np.full(mat.shape[1], np.nan)
        for j in range(mat.shape[1]):
            yv = mat[:, j]; ok = ~np.isnan(yv)
            if ok.sum() >= 3 and np.std(A[ok]) > 0:
                out[j] = np.polyfit(A[ok], yv[ok], 1)[0]
        return out

    def boot_ci(x, B=2000):
        x = x[~np.isnan(x)]
        if len(x) < 3:
            return (float("nan"),) * 3
        bs = [np.mean(rng.choice(x, len(x), replace=True)) for _ in range(B)]
        return float(np.mean(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    print("\n=== A3a-v2 dose-response (mean soft score vs alpha) ===", flush=True)
    for d in dirs:
        print(f"  {d:8s}: " + "  ".join(f"a{a:+.1f}={np.nanmean(scores[d][i]):.4f}" for i, a in enumerate(ALPHAS)), flush=True)

    sl = {d: slopes(scores[d]) for d in dirs}
    print("\n=== per-card slope d(soft)/d(alpha), mean [95% CI] ===", flush=True)
    for d in dirs:
        m, lo, hi = boot_ci(sl[d]); print(f"  {d:8s}: {m:+.5f} [{lo:+.5f}, {hi:+.5f}]", flush=True)
    dqr = sl["quality"] - sl["random"]; mr, lor, hir = boot_ci(dqr)
    print(f"\n  quality - random slope: {mr:+.5f} [{lor:+.5f}, {hir:+.5f}]", flush=True)

    qm, qlo, qhi = boot_ci(sl["quality"])
    green = (qlo > 0 and lor > 0) or (qhi < 0 and hir < 0)
    print(f"\n=== GATE(v2 sensitive): quality slope {qm:+.5f} [{qlo:+.5f},{qhi:+.5f}]; quality-random {mr:+.5f} [{lor:+.5f},{hir:+.5f}] ===", flush=True)
    print(f"=== GATE VERDICT: {'GREEN — behaviorally steerable, A3b worth it' if green else 'RED — decodable but NOT steerable (sensitive readout confirms), hold A3b'} ===", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
