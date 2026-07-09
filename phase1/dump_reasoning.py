"""Dump reasoning critic raw predictions on spaceship intra -> diagnose degeneracy."""
import numpy as np, torch
from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.critics.qwen_train import ReasoningTrainer
from phase1.critics.qwen_backend import _chat, build_value_prompt, parse_score
from phase1.eval import metrics as M

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
sp = [c for c in cards if c.task.name == "spaceship-titanic"]
rng = np.random.default_rng(42); idx = rng.permutation(len(sp)); ntr = int(len(sp) * 0.6)
train = [sp[i] for i in idx[:ntr]]; test = [sp[i] for i in idx[ntr:]]
print(f"spaceship intra: {len(train)} train {len(test)} test", flush=True)
tr = ReasoningTrainer(MODEL).fit(train)
preds = []; nfail = 0; samp = []
tr.model.eval()
with torch.no_grad():
    for c in test:
        p = _chat(tr.tok, build_value_prompt(c, for_reasoning=True))
        enc = tr.tok(p, return_tensors="pt", truncation=True, max_length=tr.prompt_len).to(tr.model.device)
        g = tr.model.generate(**enc, max_new_tokens=200, do_sample=False, pad_token_id=tr.tok.pad_token_id)
        txt = tr.tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        s = parse_score(txt)
        nfail += (s is None)
        preds.append(0.5 if s is None else s)
        samp.append((float(c.y), s, txt))
preds = np.array(preds); ys = np.array([c.y for c in test])
print(f"PRED mean={preds.mean():.3f} std={preds.std():.3f} min={preds.min():.3f} max={preds.max():.3f} "
      f"n_unique={len(np.unique(np.round(preds,3)))}/{len(preds)}", flush=True)
print(f"PARSE_FAIL={nfail}/{len(test)} (fail->0.5 constant)", flush=True)
print(f"SPEARMAN={M.compute_all(ys, preds)['spearman']:+.3f}", flush=True)
print("=== 8 SAMPLES (y_true | pred | gen_text[:220]) ===", flush=True)
for y, s, txt in samp[:8]:
    print(f"y={y:.3f} pred={s} :: {txt[:220]!r}", flush=True)
