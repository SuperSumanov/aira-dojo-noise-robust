"""RM training, production version: HF Trainer + (optional) DeepSpeed ZeRO-3.

Pairwise Bradley-Terry reward model over MLE solution code. Aligned with rm_train.py semantics
(same pairs/cards files, same task-conditioning, same head+tail truncation, same split fields)
so numbers are directly comparable; adds: full/LoRA fine-tuning, bf16, grad clipping, cosine
schedule with warmup, gradient checkpointing, flash-attention-2, multi-GPU via deepspeed.

Single-GPU smoke (3090):
  python phase1/rm_train_hf.py --pairs P --cards C --sizes 2000 --max-len 2048 --lora

8xH200 full-precision full-context (from repo root):
  deepspeed --num_gpus 8 phase1/rm_train_hf.py --pairs P --cards C --sizes 24000 \
      --max-len 8192 --deepspeed phase1/ds_zero3_offload.json --bs 2 --accum 2
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import random
import re
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from transformers import AutoModel, AutoTokenizer, Trainer, TrainingArguments

ap = argparse.ArgumentParser()
ap.add_argument("--pairs", required=True)
ap.add_argument("--cards", required=True)
ap.add_argument("--sizes", default="8000")
ap.add_argument("--model", default="/research/d7/spc/yzyang4/external/models/qwen2.5-1.5b-instruct")
ap.add_argument("--max-len", type=int, default=8192)
ap.add_argument("--head-frac", type=float, default=0.25)
ap.add_argument("--task-cond", action="store_true", default=True)
ap.add_argument("--loto", default="")
ap.add_argument("--eval-cap", type=int, default=1500)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--bs", type=int, default=1, help="per-device batch of PAIRS")
ap.add_argument("--accum", type=int, default=16)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--lora", action="store_true", help="LoRA instead of full fine-tune")
ap.add_argument("--deepspeed", default=None)
ap.add_argument("--out", default="phase1/rm_curve_hf.csv")
ap.add_argument("--save-adapter", default="")
ap.add_argument("--local_rank", type=int, default=-1)  # injected by the deepspeed launcher
a = ap.parse_args()

random.seed(a.seed)
np.random.seed(a.seed)
torch.manual_seed(a.seed)

code, ctask = {}, {}
for l in open(a.cards):
    d = json.loads(l)
    code[d["id"]] = (d.get("code") or "")[:60000]
    ctask[d["id"]] = (d.get("task") or {}).get("name", "")

pairs = [json.loads(l) for l in open(a.pairs)]
pairs = [p for p in pairs if p["better"] in code and p["worse"] in code]
if a.loto:
    train_pool = [p for p in pairs if p["task"] != a.loto]
    test_pool = [p for p in pairs if p["task"] == a.loto]
    split_name = "loto:" + a.loto
else:
    train_pool = [p for p in pairs if p["intask_split"] == "train"]
    test_pool = [p for p in pairs if p["intask_split"] == "test"]
    split_name = "in-task"
rng = random.Random(a.seed)
rng.shuffle(train_pool)
rng.shuffle(test_pool)
test_pool = test_pool[:a.eval_cap]
print(f"[rm-hf] split={split_name} train_pool={len(train_pool)} test={len(test_pool)}", flush=True)

tok = AutoTokenizer.from_pretrained(a.model)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"


def render(cid):
    if a.task_cond:
        return "# MLE-bench task: " + ctask.get(cid, "") + "\n" + code[cid]
    return code[cid]


def fit(ids):
    if len(ids) <= a.max_len:
        return ids
    h = int(a.max_len * a.head_frac)
    return ids[:h] + ids[len(ids) - (a.max_len - h):]


class PairDS(Dataset):
    def __init__(self, ps):
        self.ps = ps

    def __len__(self):
        return len(self.ps)

    def __getitem__(self, i):
        p = self.ps[i]
        return {"b": fit(tok(render(p["better"]), add_special_tokens=False)["input_ids"]),
                "w": fit(tok(render(p["worse"]), add_special_tokens=False)["input_ids"])}


def collate(batch):
    seqs = [x["b"] for x in batch] + [x["w"] for x in batch]
    m = max(len(s) for s in seqs)
    pad = tok.pad_token_id
    ids = torch.tensor([s + [pad] * (m - len(s)) for s in seqs])
    mask = torch.tensor([[1] * len(s) + [0] * (m - len(s)) for s in seqs])
    return {"input_ids": ids, "attention_mask": mask}


class RM(nn.Module):
    def __init__(self, path):
        super().__init__()
        kw = dict(torch_dtype=torch.bfloat16)
        try:
            self.backbone = AutoModel.from_pretrained(path, attn_implementation="flash_attention_2", **kw)
        except Exception:
            self.backbone = AutoModel.from_pretrained(path, **kw)
        self.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        if a.lora:
            from peft import LoraConfig, get_peft_model
            self.backbone.enable_input_require_grads()
            self.backbone = get_peft_model(self.backbone, LoraConfig(
                r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
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
        loss = -torch.nn.functional.logsigmoid(rb - rw).mean()
        return (loss, out) if return_outputs else loss


@torch.no_grad()
def evaluate_pairs(model, ps, bs):
    model.eval()
    dev = next(model.parameters()).device
    ds = PairDS(ps)
    correct = 0
    for i in range(0, len(ps), bs):
        batch = collate([ds[j] for j in range(i, min(i + bs, len(ps)))])
        out = model(input_ids=batch["input_ids"].to(dev),
                    attention_mask=batch["attention_mask"].to(dev))["logits"]
        n = out.size(0) // 2
        correct += (out[:n] > out[n:]).sum().item()
    return correct / max(len(ps), 1)


rows = []
for N in [int(x) for x in re.split(r"[,;:]", a.sizes) if x.strip()]:
    sub = train_pool[:N]
    model = RM(a.model)
    targs = TrainingArguments(
        output_dir="/tmp/rmhf_" + str(os.getpid()) + "_" + str(N),
        per_device_train_batch_size=a.bs,
        gradient_accumulation_steps=a.accum, num_train_epochs=a.epochs, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_ratio=0.03, max_grad_norm=1.0, bf16=True,
        logging_steps=50, save_strategy="no", report_to=[], seed=a.seed,
        deepspeed=a.deepspeed, remove_unused_columns=False, dataloader_num_workers=2)
    tr = BTTrainer(model=model, args=targs, train_dataset=PairDS(sub), data_collator=collate)
    t0 = time.time()
    tr.train()
    if tr.is_world_process_zero():
        acc = evaluate_pairs(tr.model, test_pool, max(a.bs, 2))
        wall = round(time.time() - t0, 1)
        print(f"[rm-hf] N={N} {split_name} acc={acc:.4f} wall={wall}s", flush=True)
        rows.append({"N": N, "split": split_name, "acc": round(acc, 4),
                     "model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,
                     "n_test": len(test_pool), "max_len": a.max_len, "lr": a.lr,
                     "lora": a.lora, "trainer": "hf+ds" if a.deepspeed else "hf"})
        if a.save_adapter:
            dd = os.path.join(a.save_adapter, "N" + str(N))
            os.makedirs(dd, exist_ok=True)
            tr.model.backbone.save_pretrained(dd, safe_serialization=True)
            torch.save(tr.model.head.state_dict(), os.path.join(dd, "head.pt"))
    del model, tr
    torch.cuda.empty_cache()

if rows:
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[rm-hf] wrote {len(rows)} rows -> {a.out}")
