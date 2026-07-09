"""QLoRA training on a 3090 for the scalar critic (reasoning SFT lives in the same file, added next).

scalar: Qwen2.5-Coder-7B in 4bit + LoRA adapters + a scalar regression head on the last-token hidden
state. Loss = MSE(y_norm) + a pairwise ranking hinge over the micro-batch (so it orders candidates,
not just fits magnitudes). Small batch + grad-accum + gradient checkpointing to fit 24GB.

torch/peft/transformers imported lazily so the mock path never needs them.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card
from .qwen_backend import _chat, build_value_prompt


class ScalarTrainer:
    def __init__(self, model_path: str, r: int = 16, alpha: int = 32, lr: float = 1e-4,
                 epochs: int = 4, accum: int = 8, max_len: int = 768, lam_rank: float = 0.5,
                 seed: int = 0):
        self.model_path = model_path
        self.r, self.alpha, self.lr = r, alpha, lr
        self.epochs, self.accum, self.max_len = epochs, accum, max_len
        self.lam_rank, self.seed = lam_rank, seed
        self.model = self.head = self.tok = None

    def _build(self):
        import torch
        import torch.nn as nn
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        tok = AutoTokenizer.from_pretrained(self.model_path)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
        base = AutoModelForCausalLM.from_pretrained(self.model_path, quantization_config=bnb,
                                                    device_map="auto")
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        lora = LoraConfig(r=self.r, lora_alpha=self.alpha, lora_dropout=0.05, bias="none",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                          task_type="FEATURE_EXTRACTION")
        model = get_peft_model(base, lora)
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        H = model.config.hidden_size
        head = nn.Linear(H, 1).to(model.device)  # keep fp32; cast hidden -> fp32 at the head
        self.model, self.head, self.tok = model, head, tok
        return torch

    def _forward_pred(self, torch, cards: List[Card]):
        """last-token hidden -> scalar head -> pred (differentiable). One card at a time (bs=1)."""
        preds = []
        for c in cards:
            enc = self.tok(_chat(self.tok, build_value_prompt(c)), return_tensors="pt",
                           truncation=True, max_length=self.max_len).to(self.model.device)
            out = self.model(**enc, output_hidden_states=True)
            h = out.hidden_states[-1][0, -1]          # (H,)
            preds.append(self.head(h.float()).squeeze())
        return torch.stack(preds)

    def fit(self, cards: List[Card]) -> "ScalarTrainer":
        cards = [c for c in cards if c.y is not None]
        if not cards:
            return self
        torch = self._build()
        y = torch.tensor([c.y for c in cards], dtype=torch.float32, device=self.model.device)
        params = [p for p in self.model.parameters() if p.requires_grad] + list(self.head.parameters())
        opt = torch.optim.AdamW(params, lr=self.lr)
        n = len(cards)
        for ep in range(self.epochs):
            perm = np.random.default_rng(self.seed + ep).permutation(n)
            opt.zero_grad()
            for step, i in enumerate(perm):
                c = cards[i]
                enc = self.tok(_chat(self.tok, build_value_prompt(c)), return_tensors="pt",
                               truncation=True, max_length=self.max_len).to(self.model.device)
                out = self.model(**enc, output_hidden_states=True)
                h = out.hidden_states[-1][0, -1]
                pred = self.head(h.float()).squeeze()
                loss = (pred - y[i]) ** 2
                # cheap pairwise: compare with a random other card's cached target sign
                if self.lam_rank > 0 and step > 0:
                    j = int(perm[step - 1])
                    with torch.no_grad():
                        pj = self._pred_cache
                    if (y[i] - y[j]) != 0:
                        margin = torch.sign(y[i] - y[j]) * (pred - pj)
                        loss = loss + self.lam_rank * torch.clamp(0.1 - margin, min=0)
                self._pred_cache = pred.detach()
                (loss / self.accum).backward()
                if (step + 1) % self.accum == 0 or step == n - 1:
                    opt.step()
                    opt.zero_grad()
        self.model.eval()
        return self

    def predict(self, cards: List[Card]) -> np.ndarray:
        import torch
        self.model.eval()
        out = []
        with torch.no_grad():
            for c in cards:
                enc = self.tok(_chat(self.tok, build_value_prompt(c)), return_tensors="pt",
                               truncation=True, max_length=self.max_len).to(self.model.device)
                o = self.model(**enc, output_hidden_states=True)
                h = o.hidden_states[-1][0, -1]
                out.append(float(self.head(h.float()).squeeze().float().cpu()))
        return np.array(out, float)


def _sft_ids(tok, prompt: str, target: str, max_len: int, device):
    """input_ids + labels where prompt tokens are masked (-100); only target tokens carry loss."""
    import torch
    from .qwen_backend import _chat
    p_ids = tok(_chat(tok, prompt), add_special_tokens=False)["input_ids"]
    t_ids = tok(target + tok.eos_token, add_special_tokens=False)["input_ids"]
    ids = (p_ids + t_ids)[:max_len]
    labels = ([-100] * len(p_ids) + t_ids)[:max_len]
    return {"input_ids": torch.tensor([ids], device=device),
            "attention_mask": torch.ones(1, len(ids), dtype=torch.long, device=device),
            "labels": torch.tensor([labels], device=device)}


class ReasoningTrainer:
    """QLoRA SFT for the reasoning critic. A frozen teacher writes an ANALYSIS for a card whose TRUE
    y is known; digits are stripped from the analysis (no leaking the teacher's guess) and the true
    y_norm is appended as `predicted_final_score: <y>`. The 7B is SFT'd to reason->score; predict =
    single greedy forward + parse. Teacher defaults to the same 7B (self-distillation) until 14B is
    downloaded."""

    def __init__(self, model_path: str, teacher_path: str = None, r: int = 16, alpha: int = 32,
                 lr: float = 1e-4, epochs: int = 3, accum: int = 8, max_len: int = 1024,
                 prompt_len: int = 768, seed: int = 0):
        self.model_path = model_path
        self.teacher_path = teacher_path or model_path
        self.r, self.alpha, self.lr = r, alpha, lr
        self.epochs, self.accum, self.max_len, self.seed = epochs, accum, max_len, seed
        self.prompt_len = prompt_len   # card prompt truncation (match scalar's context; SFT seq = max_len holds prompt+target)
        self.model = self.tok = None

    def _make_sft(self, cards):
        import re
        import torch
        from .qwen_backend import load_model, _chat, build_value_prompt
        model, tok = load_model(self.teacher_path, "4bit")
        data = []
        for c in cards:
            p = _chat(tok, build_value_prompt(c, for_reasoning=True, max_code=1200))
            enc = tok(p, return_tensors="pt", truncation=True, max_length=self.prompt_len).to(model.device)
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=256, do_sample=False, pad_token_id=tok.pad_token_id)
            txt = tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
            analysis = re.split(r"predicted_final_score", txt, flags=re.I)[0].strip()
            analysis = re.sub(r"[-+]?\d*\.?\d+", "#", analysis)[:1200]        # strip digits
            target = f"{analysis}\npredicted_final_score: {c.y:.3f}"
            data.append((build_value_prompt(c, for_reasoning=True), target))
        return data, tok

    def fit(self, cards):
        cards = [c for c in cards if c.y is not None]
        if not cards:
            return self
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        data, tok = self._make_sft(cards)
        import gc
        from .qwen_backend import _MODELS
        _MODELS.clear(); gc.collect(); torch.cuda.empty_cache()   # free teacher before loading trainable 7B
        print(f"[reasoning] VRAM after freeing teacher: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
        base = AutoModelForCausalLM.from_pretrained(self.model_path, quantization_config=bnb, device_map="auto")
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        lora = LoraConfig(r=self.r, lora_alpha=self.alpha, lora_dropout=0.05, bias="none",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM")
        model = get_peft_model(base, lora)
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=self.lr)
        n = len(data)
        for ep in range(self.epochs):
            perm = np.random.default_rng(self.seed + ep).permutation(n)
            opt.zero_grad()
            for step, i in enumerate(perm):
                prompt, target = data[i]
                b = _sft_ids(tok, prompt, target, self.max_len, model.device)
                T = int((b["labels"][0] != -100).sum())
                if T < 1:
                    continue
                # logits_to_keep: only materialize the target-region logits. The full-seq (prompt)
                # logits over the 152k vocab are what OOM'd SFT; prompt labels are all -100 anyway,
                # so compute CE manually on just the last T positions.
                import torch.nn.functional as Fnn
                out = model(input_ids=b["input_ids"], attention_mask=b["attention_mask"],
                            logits_to_keep=T + 1)
                lg = out.logits[:, :-1, :].reshape(-1, out.logits.size(-1)).float()
                loss = Fnn.cross_entropy(lg, b["labels"][0, -T:])
                (loss / self.accum).backward()
                if (step + 1) % self.accum == 0 or step == n - 1:
                    opt.step(); opt.zero_grad()
        model.eval()
        self.model, self.tok = model, tok
        return self

    def predict(self, cards):
        import torch
        from .qwen_backend import _chat, build_value_prompt, parse_score
        self.model.eval()
        out = []
        with torch.no_grad():
            for c in cards:
                p = _chat(self.tok, build_value_prompt(c, for_reasoning=True, max_code=1200))
                enc = self.tok(p, return_tensors="pt", truncation=True, max_length=self.prompt_len).to(self.model.device)
                g = self.model.generate(**enc, max_new_tokens=200, do_sample=False, pad_token_id=self.tok.pad_token_id)
                txt = self.tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                s = parse_score(txt)
                out.append(0.5 if s is None else s)
        return np.array(out, float)
