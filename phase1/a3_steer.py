"""A3a — causal steering GATE: is the grade 'quality direction' (H1/A1) linearly STEERABLE, not just decodable?

Decodable != steerable. We add alpha*sigma*v_hat to Qwen's layer-21 residual stream (CAA-style) and measure
the causal effect on the model's OWN generated quality SCORE. The prompt is code-only (self-report masked)
so the model must judge from the code, giving steering a clean target. If steering toward the high-grade
direction raises the model's score, AND more than a norm-matched RANDOM direction does, the quality axis is
causally used by the model -> the heavy A3b (steer generation + evaluate) is worth its GPU-hours.
Controls: random direction (expect flat), code-length direction (specificity). All frozen, no finetuning.
"""
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.critics.qwen_backend import load_model, build_value_prompt, _chat, parse_score
from phase1.h1_ablation import mask_selfreport

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
STEER_HS = 21                       # hidden_states index steered (matches A1/H1 layer 21)
ALPHAS = [-3.0, -1.5, 0.0, 1.5, 3.0]
MAXNEW = 20
SEED = 0
OUT = "phase1/_a3a_scores.npz"


def _unit(v):
    n = np.linalg.norm(v)
    return v / (n if n > 1e-8 else 1.0)


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    rng = np.random.default_rng(SEED)
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    loglen = np.array([np.log(max(len(c.code or ""), 1)) for c in cards], float)
    mcards = [mask_selfreport(c) for c in cards]      # code-only judgment

    model, tok = load_model(MODEL, "4bit")
    Hd = model.config.hidden_size
    hook_layer = model.model.layers[STEER_HS - 1]     # its OUTPUT == hidden_states[STEER_HS]
    print(f"model H={Hd} layers={model.config.num_hidden_layers} hook=layers[{STEER_HS-1}] N={len(mcards)}", flush=True)

    # ---- per-card mean-pooled hidden at STEER_HS (one clean forward pass, no steering) ----
    def meanpool_hidden(cs):
        outs = []
        for i in range(0, len(cs), 2):
            chunk = [_chat(tok, build_value_prompt(c, max_code=4000)) for c in cs[i:i + 2]]
            enc = tok(chunk, return_tensors="pt", padding=True, truncation=True, max_length=2048).to(model.device)
            with torch.no_grad():
                out = model(**enc, output_hidden_states=True)
            hs = out.hidden_states[STEER_HS]
            mask = enc["attention_mask"].unsqueeze(-1).to(hs.dtype)
            mp = (hs * mask).sum(1) / mask.sum(1).clamp(min=1)
            outs.append(mp.float().cpu().numpy())
            del out, hs
            torch.cuda.empty_cache()
        return np.vstack(outs)

    print("collecting layer-21 mean-pooled hidden for steer directions ...", flush=True)
    Hmp = meanpool_hidden(mcards)

    def contrastive_dir(score):                        # per-task (top - bottom tercile), avg of units
        ds = []
        for t in np.unique(tasks):
            m = np.where(tasks == t)[0]; s = score[m]
            hi = m[s >= np.quantile(s, 2 / 3)]; lo = m[s <= np.quantile(s, 1 / 3)]
            if len(hi) and len(lo):
                ds.append(_unit(Hmp[hi].mean(0) - Hmp[lo].mean(0)))
        return _unit(np.mean(ds, axis=0))

    dirs = {"quality": contrastive_dir(y), "random": _unit(rng.standard_normal(Hd)),
            "length": contrastive_dir(loglen)}
    sigmas = {k: float(np.std(Hmp @ v)) for k, v in dirs.items()}
    print("sigmas:", {k: round(s, 3) for k, s in sigmas.items()},
          "cos(q,len)=", round(float(dirs["quality"] @ dirs["length"]), 3),
          "cos(q,rnd)=", round(float(dirs["quality"] @ dirs["random"]), 3), flush=True)

    # ---- steering hook on the layer output ----
    steer = {"vec": None}

    def hook(mod, inp, out):
        if steer["vec"] is None:
            return out
        if isinstance(out, tuple):
            return (out[0] + steer["vec"].to(out[0].dtype),) + tuple(out[1:])
        return out + steer["vec"].to(out.dtype)
    handle = hook_layer.register_forward_hook(hook)

    def gen_score(card):
        prompt = _chat(tok, build_value_prompt(card, max_code=4000))
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=MAXNEW, do_sample=False, pad_token_id=tok.pad_token_id)
        return parse_score(tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True))

    scores = {d: np.full((len(ALPHAS), len(mcards)), np.nan) for d in dirs}
    order = sorted(range(len(ALPHAS)), key=lambda i: abs(ALPHAS[i]))   # 0 first -> early sanity read
    for dname, v in dirs.items():
        vt = torch.tensor(v, device=model.device)
        for ai in order:
            a = ALPHAS[ai]
            steer["vec"] = None if a == 0.0 else (a * sigmas[dname]) * vt
            none_ct = 0
            for ci, c in enumerate(mcards):
                s = gen_score(c)
                if s is None:
                    none_ct += 1
                else:
                    scores[dname][ai, ci] = s
            print(f"  {dname:8s} a={a:+.1f}  mean={np.nanmean(scores[dname][ai]):.3f}  none={none_ct}/{len(mcards)}", flush=True)
        np.savez(OUT, **{k: scores[k] for k in scores}, alphas=np.array(ALPHAS))
    handle.remove()

    # ---- slopes + gate ----
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

    print("\n=== A3a dose-response (mean generated score vs alpha) ===", flush=True)
    for d in dirs:
        print(f"  {d:8s}: " + "  ".join(f"a{a:+.1f}={np.nanmean(scores[d][i]):.3f}" for i, a in enumerate(ALPHAS)), flush=True)

    sl = {d: slopes(scores[d]) for d in dirs}
    print("\n=== per-card slope d(score)/d(alpha), mean [95% CI] ===", flush=True)
    for d in dirs:
        m, lo, hi = boot_ci(sl[d]); print(f"  {d:8s}: {m:+.4f} [{lo:+.4f}, {hi:+.4f}]", flush=True)
    dqr = sl["quality"] - sl["random"]; mr, lor, hir = boot_ci(dqr)
    dql = sl["quality"] - sl["length"]; ml, lol, hil = boot_ci(dql)
    print(f"\n  quality - random slope: {mr:+.4f} [{lor:+.4f}, {hir:+.4f}]", flush=True)
    print(f"  quality - length slope: {ml:+.4f} [{lol:+.4f}, {hil:+.4f}]", flush=True)

    qm, qlo, qhi = boot_ci(sl["quality"])
    green = (qlo > 0 and lor > 0) or (qhi < 0 and hir < 0)   # significant + specific, either sign
    print(f"\n=== GATE: quality slope {qm:+.4f} [{qlo:+.4f}, {qhi:+.4f}]; quality-random {mr:+.4f} [{lor:+.4f}, {hir:+.4f}] ===", flush=True)
    print(f"=== GATE VERDICT: {'GREEN — causally steerable, A3b worth it' if green else 'RED — decodable but NOT linearly steerable, hold A3b'} ===", flush=True)
    print("=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
