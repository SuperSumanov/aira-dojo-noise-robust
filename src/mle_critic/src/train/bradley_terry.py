"""RM training, production version: HF Trainer + (optional) DeepSpeed ZeRO-3.

Pairwise Bradley-Terry reward model over MLE solution code. Aligned with rm_train.py semantics
(same pairs/cards files, same task-conditioning, same head+tail truncation, same split fields)
so numbers are directly comparable; adds: full fine-tuning, bf16, grad clipping, cosine
schedule with warmup, gradient checkpointing, flash-attention-2, multi-GPU via Accelerate.

Single-GPU smoke (3090, from the repository root):
  accelerate launch src/mle_critic/src/train/bradley_terry.py --pairs P --cards C \
      --sizes 2000 --max-len 2048 --per-device-train-batch-size 1

8xH200 full-precision full-context (from repo root):
  accelerate launch --config_file src/mle_critic/recipes/zero3.yaml --num_processes 8 \
      src/mle_critic/src/train/bradley_terry.py \
      --pairs P --cards C --sizes 24000 --max-len 8192 \
      --per-device-train-batch-size 2 --gradient-accumulation-steps 2
"""
from __future__ import annotations
import copy
from functools import partial
import os
import random
import re

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer, HfArgumentParser, Trainer

from src.mle_critic.src.evaluation.bradley_terry_evaluation import pair_accuracy_metrics
from src.mle_critic.src.train.dataset import (
    CardEncoder,
    PairDataset,
    load_training_pool,
    pair_collate,
    read_cards,
    read_pairs,
)

from src.mle_critic.src.train.config import BradleyTerryConfig

parser = HfArgumentParser(BradleyTerryConfig)
(a,) = parser.parse_args_into_dataclasses()

random.seed(a.seed)
np.random.seed(a.seed)
torch.manual_seed(a.seed)

code, ctask = read_cards(a.cards)
pairs = read_pairs(a.pairs, code)
train_pool, split_name = load_training_pool(pairs, loto=a.loto, seed=a.seed)
print(
    f"[rm-hf] split={split_name} train_pool={len(train_pool)}",
    flush=True,
)

tok = AutoTokenizer.from_pretrained(a.model)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"


encoder = CardEncoder(
    code=code,
    tasks=ctask,
    tokenizer=tok,
    max_len=a.max_len,
    head_frac=a.head_frac,
    task_cond=a.task_cond,
    budget_cond=a.budget_cond,
    budget_pos=a.budget_pos,
)


class RM(nn.Module):
    def __init__(self, path):
        super().__init__()
        kw = dict(torch_dtype=torch.bfloat16)
        try:
            self.backbone = AutoModel.from_pretrained(path, attn_implementation="flash_attention_2", **kw)
        except Exception:
            self.backbone = AutoModel.from_pretrained(path, **kw)
        self.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)

    def forward(self, input_ids=None, attention_mask=None, **kw):
        h = self.backbone(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        idx = attention_mask.sum(1) - 1
        pooled = h[torch.arange(h.size(0), device=h.device), idx]
        return {"logits": self.head(pooled).squeeze(-1).float()}


class BTTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kw):
        out = model(**inputs)["logits"]
        n = out.size(0) // 2
        rb, rw = out[:n], out[n:]
        margins = rb - rw
        loss = -torch.nn.functional.logsigmoid(margins).mean()
        return (loss, {"logits": margins}) if return_outputs else loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):
        """Return pair margins so Trainer can compute validation accuracy."""
        inputs = self._prepare_inputs(inputs)
        with torch.no_grad(), self.compute_loss_context_manager():
            logits = model(**inputs)["logits"]
            n = logits.size(0) // 2
            margins = logits[:n] - logits[n:]
            loss = -torch.nn.functional.logsigmoid(margins).mean()
        if prediction_loss_only:
            return loss.detach(), None, None
        labels = torch.ones_like(margins)
        return loss.detach(), margins.detach(), labels


for N in [int(x) for x in re.split(r"[,;:]", a.sizes) if x.strip()]:
    sized_pool = train_pool[:N]
    if len(sized_pool) < 2:
        raise ValueError(f"N={N} resolves to fewer than two records; cannot make an 80/20 split")
    validation_size = max(1, int(len(sized_pool) * 0.1))
    training_subset = sized_pool[:-validation_size]
    validation_pool = sized_pool[-validation_size:]
    print(
        f"[rm-hf] N={N} actual={len(sized_pool)} -> "
        f"train={len(training_subset)} validation={len(validation_pool)}",
        flush=True,
    )
    model = RM(a.model)
    targs = copy.copy(a)
    targs.output_dir = f"outputs/mle_critic/rmhf_{os.getpid()}_{N}"
    tr = BTTrainer(
        model=model,
        args=targs,
        train_dataset=PairDataset(training_subset, encoder),
        eval_dataset=PairDataset(validation_pool, encoder),
        data_collator=partial(pair_collate, pad_token_id=tok.pad_token_id),
        compute_metrics=pair_accuracy_metrics,
    )
    tr.train()
    if tr.is_world_process_zero():
        print(f"[rm-hf] N={N} training complete; best_validation_loss={tr.state.best_metric} "
              f"best_checkpoint={tr.state.best_model_checkpoint}", flush=True)
    del model, tr
    torch.cuda.empty_cache()
