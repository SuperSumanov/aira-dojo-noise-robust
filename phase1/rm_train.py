"""RM pilot: Bradley-Terry preference model on MLE solution code (LoRA on a frozen small LLM).

Trains a scalar reward head over code; loss = -log sigmoid(r(better) - r(worse)), optionally
tau-weighted. Reports in-task and LOTO (leave-one-task-out) pairwise accuracy at several
training-set sizes N -> the RM-accuracy-vs-N curve (training pillar experiment #1).

Usage:
  python phase1/rm_train.py --pairs phase1/rm_pairs_v0.jsonl --cards phase1/cards_merged_20260727.jsonl \
      --model /research/.../qwen2.5-1.5b-instruct --sizes 500,2000,8000 --out phase1/rm_curve.csv
"""
from __future__ import annotations
import argparse, json, math, os, random, time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

ap = argparse.ArgumentParser()
ap.add_argument("--pairs", default="phase1/rm_pairs_v0.jsonl")
ap.add_argument("--cards", default="phase1/cards_merged_20260727.jsonl")
ap.add_argument("--model", default="/research/d7/spc/yzyang4/external/models/qwen2.5-1.5b-instruct")
ap.add_argument("--sizes", default="500,2000,8000")
ap.add_argument("--out", default="phase1/rm_curve.csv")
ap.add_argument("--max-len", type=int, default=1024)
ap.add_argument("--bs", type=int, default=2)
ap.add_argument("--accum", type=int, default=8)
ap.add_argument("--lr", type=float, default=1e-4)
ap.add_argument("--epochs", type=int, default=1)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--tau-weight", action="store_true", help="weight pairs by tau-clearance")
ap.add_argument("--loto", default="", help="hold out this task (LOTO fold); default = in-task split")
ap.add_argument("--eval-cap", type=int, default=1500)
a = ap.parse_args()

random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)

code = {}
for l in open(a.cards):
    d = json.loads(l)
    code[d["id"]] = (d.get("code") or "")[:8000]

pairs = [json.loads(l) for l in open(a.pairs)]
pairs = [p for p in pairs if p["better"] in code and p["worse"] in code]
print(f"[rm] pairs with code: {len(pairs)}")

if a.loto:
    train_pool = [p for p in pairs if p["task"] != a.loto]
    test_pool = [p for p in pairs if p["task"] == a.loto]
    split_name = f"loto:{a.loto}"
else:
    train_pool = [p for p in pairs if p["intask_split"] == "train"]
    test_pool = [p for p in pairs if p["intask_split"] == "test"]
    split_name = "in-task"
random.shuffle(train_pool); random.shuffle(test_pool)
test_pool = test_pool[:a.eval_cap]
print(f"[rm] split={split_name} train_pool={len(train_pool)} test={len(test_pool)}")

from transformers import AutoModel, AutoTokenizer
from peft import LoraConfig, get_peft_model

tok = AutoTokenizer.from_pretrained(a.model)
if tok.pad_token is None: tok.pad_token = tok.eos_token
tok.padding_side = "right"   # last-token pooling depends on this

class RM(nn.Module):
    def __init__(self, path):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(path, torch_dtype=torch.bfloat16)
        self.backbone = get_peft_model(self.backbone, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)
    def forward(self, ids, mask):
        h = self.backbone(input_ids=ids, attention_mask=mask).last_hidden_state
        idx = mask.sum(1) - 1                                   # last non-pad token
        pooled = h[torch.arange(h.size(0), device=h.device), idx]
        return self.head(pooled).squeeze(-1).float()

def enc(texts):
    b = tok(texts, truncation=True, max_length=a.max_len, padding=True, return_tensors="pt")
    return b["input_ids"], b["attention_mask"]

class PairDS(Dataset):
    def __init__(self, ps): self.ps = ps
    def __len__(self): return len(self.ps)
    def __getitem__(self, i):
        p = self.ps[i]
        w = 1.0
        if a.tau_weight and p.get("clears_tau") is False: w = 0.2
        return code[p["better"]], code[p["worse"]], w

def collate(batch):
    bs, ws, wt = zip(*batch)
    return enc(list(bs)), enc(list(ws)), torch.tensor(wt, dtype=torch.float)

@torch.no_grad()
def evaluate(model, ps):
    model.eval(); correct = 0
    dl = DataLoader(PairDS(ps), batch_size=a.bs * 2, collate_fn=collate)
    for (bi, bm), (wi, wm), _ in dl:
        rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
        correct += (rb > rw).sum().item()
    return correct / max(len(ps), 1)

rows = []
for N in [int(x) for x in a.sizes.split(",")]:
    if N > len(train_pool):
        print(f"[rm] skip N={N} (> pool {len(train_pool)})"); continue
    sub = train_pool[:N]
    model = RM(a.model).cuda()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    dl = DataLoader(PairDS(sub), batch_size=a.bs, shuffle=True, collate_fn=collate, drop_last=True)
    t0 = time.time(); model.train(); step = 0
    for ep in range(a.epochs):
        for (bi, bm), (wi, wm), w in dl:
            rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
            loss = -(w.cuda() * torch.nn.functional.logsigmoid(rb - rw)).mean() / a.accum
            loss.backward(); step += 1
            if step % a.accum == 0:
                opt.step(); opt.zero_grad()
    acc = evaluate(model, test_pool)
    wall = round(time.time() - t0, 1)
    print(f"[rm] N={N} {split_name} acc={acc:.4f} wall={wall}s", flush=True)
    rows.append({"N": N, "split": split_name, "acc": round(acc, 4), "tau_weight": a.tau_weight,
                 "model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,
                 "n_test": len(test_pool), "max_len": a.max_len, "lr": a.lr})
    del model, opt; torch.cuda.empty_cache()

import csv
new = not os.path.exists(a.out)
with open(a.out, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    if new: w.writeheader()
    for r in rows: w.writerow(r)
print(f"[rm] wrote {len(rows)} rows -> {a.out}")
