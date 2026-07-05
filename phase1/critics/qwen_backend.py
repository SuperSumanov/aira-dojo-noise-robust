"""Shared real-Qwen backend: load (4bit/AWQ), build value prompts, extract frozen features, and
generate+parse a scalar. Used by the zeroshot & probe critics directly; the QLoRA critics
(scalar/reasoning) reuse the prompt builder + parser and add training in qwen_train.py.

torch/transformers are imported LAZILY inside functions so the mock smoke never needs them.
Models are cached per (path, quant) so a sweep loads each backbone once.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional

import numpy as np

from ..cards import Card

_MODELS: Dict[str, object] = {}
_DEFAULT_7B = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"


def load_model(path: str, quant: str = "4bit"):
    """Load + cache (model, tokenizer). quant='4bit' (bnb NF4) or 'awq' (pre-quantized) or 'bf16'."""
    key = f"{path}::{quant}"
    if key in _MODELS:
        return _MODELS[key]
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(path)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    kw = dict(device_map="auto")
    if quant == "4bit":
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True)
    elif quant == "awq":
        pass  # AWQ weights carry their own config
    else:
        kw["torch_dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(path, **kw).eval()
    _MODELS[key] = (model, tok)
    return model, tok


# ---------------------------------------------------------------------------
# Prompt: turn a card (label-hidden) into a value-estimation prompt.
# ---------------------------------------------------------------------------
_SYS = ("You are an expert ML engineer estimating how good a candidate solution to a Kaggle-style "
        "task will score. You are given the task, the candidate's code, and cheap early signals. "
        "Estimate the final medal-normalized score in [0,1] (0=poor, 1=gold-level).")


def build_value_prompt(card: Card, for_reasoning: bool = False) -> str:
    v = card.view()
    tk, o, ln = v["task"], v["obs"], v["lineage"]
    code = (v["code"] or "")[:4000]
    parts = [
        f"# Task\n{tk.get('name','?')} ({tk.get('type','?')}, metric={tk.get('metric','?')}, "
        f"higher_is_better={tk.get('higher_is_better')})",
        f"# Cheap signals\nself_reported_val={o.get('val_at_low')}  runtime_s={o.get('runtime_s')}  "
        f"error={o.get('error')}\nval_curve={o.get('val_curve')}",
        f"# Lineage\nop={ln.get('op')} depth={ln.get('depth')} parent_val={ln.get('parent_val')}",
        f"# Candidate code (truncated)\n```python\n{code}\n```",
    ]
    if for_reasoning:
        parts.append("# Instructions\nBriefly analyze (2-4 sentences) whether the cheap signal is "
                      "trustworthy and how the code/lineage affect the true score, then output the "
                      "final line exactly as `predicted_final_score: <float in [0,1]>`.")
    else:
        parts.append("# Output\nReply with ONLY one line: `SCORE: <float in [0,1]>`")
    return "\n\n".join(parts)


def _chat(tok, user: str) -> str:
    msgs = [{"role": "system", "content": _SYS}, {"role": "user", "content": user}]
    return tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)


_NUM = re.compile(r"[-+]?\d*\.?\d+")


def parse_score(text: str) -> Optional[float]:
    """Pull the score: prefer the value after SCORE:/predicted_final_score:, else last number in [0,1]."""
    m = re.search(r"(?:predicted_final_score|SCORE)\s*[:=]\s*([-+]?\d*\.?\d+)", text, re.I)
    cand = m.group(1) if m else None
    if cand is None:
        nums = _NUM.findall(text)
        cand = nums[-1] if nums else None
    if cand is None:
        return None
    try:
        return float(min(1.0, max(0.0, float(cand))))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Frozen-feature extraction (for the probe critic).
# ---------------------------------------------------------------------------
def extract_features(cards: List[Card], path: str = _DEFAULT_7B, quant: str = "4bit",
                     layer: int = -1, max_len: int = 2048, batch_size: int = 2) -> np.ndarray:
    """Frozen features per card: [mean-pooled hidden, last-token hidden, last-token entropy].
    Deterministic (eval, no sampling). Returns (N, 2H+1). Memory-careful: entropy is computed on the
    LAST token only (avoids materializing a full (B,T,vocab) softmax) + small batch + cache clearing."""
    import torch
    model, tok = load_model(path, quant)
    prompts = [_chat(tok, build_value_prompt(c)) for c in cards]
    feats = []
    for i in range(0, len(prompts), batch_size):
        chunk = prompts[i:i + batch_size]
        enc = tok(chunk, return_tensors="pt", padding=True, truncation=True, max_length=max_len).to(model.device)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
        hs = out.hidden_states[layer]                      # (B,T,H)
        mask = enc["attention_mask"].unsqueeze(-1).to(hs.dtype)
        mean_pool = (hs * mask).sum(1) / mask.sum(1).clamp(min=1)
        idx = enc["attention_mask"].sum(1) - 1             # last real token
        ar = torch.arange(hs.size(0))
        last = hs[ar, idx]
        last_logits = out.logits[ar, idx].float()          # (B,vocab) only -> cheap entropy
        lp = torch.log_softmax(last_logits, dim=-1)
        ent = -(lp.exp() * lp).sum(-1)                     # (B,)
        f = torch.cat([mean_pool.float(), last.float(), ent.unsqueeze(-1)], dim=-1)
        feats.append(f.cpu().numpy())
        del out, hs, last_logits, lp
        torch.cuda.empty_cache()
    return np.vstack(feats)


# ---------------------------------------------------------------------------
# Zero-shot generation (for the zeroshot critic).
# ---------------------------------------------------------------------------
def generate_scores(cards: List[Card], path: str, quant: str = "4bit",
                    for_reasoning: bool = False, max_new_tokens: int = 256) -> List[Optional[float]]:
    """Single forward per card (greedy), parse the scalar. No multi-sample voting."""
    import torch
    model, tok = load_model(path, quant)
    out_scores = []
    for c in cards:
        prompt = _chat(tok, build_value_prompt(c, for_reasoning=for_reasoning))
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                  pad_token_id=tok.pad_token_id)
        txt = tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        out_scores.append(parse_score(txt))
    return out_scores
