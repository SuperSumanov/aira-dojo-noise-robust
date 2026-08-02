"""RM pilot: Bradley-Terry preference model on MLE solution code (LoRA on a frozen small LLM).

Trains a scalar reward head over code; loss = -log sigmoid(r(better) - r(worse)), optionally
tau-weighted. Reports in-task and LOTO (leave-one-task-out) pairwise accuracy at several
training-set sizes N -> the RM-accuracy-vs-N curve (training pillar experiment #1).

Usage:
  python phase1/rm_train.py --pairs phase1/rm_pairs_v0.jsonl --cards phase1/cards_merged_20260727.jsonl \
      --model /research/.../qwen2.5-1.5b-instruct --sizes 500,2000,8000 --out phase1/rm_curve.csv
"""
from __future__ import annotations
import argparse, json, math, os, random, re, time
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
ap.add_argument("--task-cond", action="store_true", help="prepend competition id to the code")
ap.add_argument("--head-frac", type=float, default=0.25, help="head share when head+tail truncating")
ap.add_argument("--fewshot-ks", default="", help="LOTO few-shot: comma/semicolon K list, e.g. 0;10;50;200;1000")
ap.add_argument("--ft-lr", type=float, default=5e-5)
ap.add_argument("--ft-epochs", type=int, default=3)
ap.add_argument("--save-adapter", default="", help="dir to save the trained LoRA + head (for T3 serving)")
ap.add_argument("--ft-pairs", default="", help="second-stage fine-tune on ALL pairs in this file, then re-eval")
a = ap.parse_args()

random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)

code, ctask = {}, {}
for l in open(a.cards):
    d = json.loads(l)
    code[d["id"]] = (d.get("code") or "")[:40000]
    ctask[d["id"]] = (d.get("task") or {}).get("name", "")

pairs = [json.loads(l) for l in open(a.pairs)]
pairs = [p for p in pairs if p["better"] in code and p["worse"] in code]
print(f"[rm] pairs with code: {len(pairs)}")

ft_pool = []
if a.loto:
    train_pool = [p for p in pairs if p["task"] != a.loto]
    held = [p for p in pairs if p["task"] == a.loto]
    if a.fewshot_ks:
        hcards = sorted({c for p in held for c in (p["better"], p["worse"])})
        random.Random(a.seed).shuffle(hcards)
        ft_cards = set(hcards[: len(hcards) // 2])
        ev_cards = set(hcards[len(hcards) // 2 :])
        ft_pool = [p for p in held if p["better"] in ft_cards and p["worse"] in ft_cards]
        test_pool = [p for p in held if p["better"] in ev_cards and p["worse"] in ev_cards]
        print(f"[rm] few-shot card split: ft_cards={len(ft_cards)} ev_cards={len(ev_cards)} "
              f"ft_pairs={len(ft_pool)} eval_pairs={len(test_pool)}")
    else:
        test_pool = held
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
        base = AutoModel.from_pretrained(path, torch_dtype=torch.bfloat16)
        base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        base.enable_input_require_grads()
        self.backbone = get_peft_model(base, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)
    def forward(self, ids, mask):
        h = self.backbone(input_ids=ids, attention_mask=mask).last_hidden_state
        idx = mask.sum(1) - 1                                   # last non-pad token
        pooled = h[torch.arange(h.size(0), device=h.device), idx]
        return self.head(pooled).squeeze(-1).float()

def _fit(ids):
    """Head+tail truncation: keep the opening (imports/data) AND the tail (model def, training loop)."""
    if len(ids) <= a.max_len:
        return ids
    h = int(a.max_len * a.head_frac)
    return ids[:h] + ids[len(ids) - (a.max_len - h):]

def enc(texts):
    seqs = [_fit(tok(t, add_special_tokens=False)["input_ids"]) for t in texts]
    m = max(len(s_) for s_ in seqs)
    pad = tok.pad_token_id
    ids = torch.tensor([s_ + [pad] * (m - len(s_)) for s_ in seqs])
    mask = torch.tensor([[1] * len(s_) + [0] * (m - len(s_)) for s_ in seqs])
    return ids, mask

def _render(cid):
    if a.task_cond:
        return "# MLE-bench task: " + ctask.get(cid, "") + chr(10) + code[cid]
    return code[cid]


class PairDS(Dataset):
    def __init__(self, ps): self.ps = ps
    def __len__(self): return len(self.ps)
    def __getitem__(self, i):
        p = self.ps[i]
        w = 1.0
        if a.tau_weight and p.get("clears_tau") is False: w = 0.2
        return _render(p["better"]), _render(p["worse"]), w

def collate(batch):
    bs, ws, wt = zip(*batch)
    return enc(list(bs)), enc(list(ws)), torch.tensor(wt, dtype=torch.float)

@torch.no_grad()
def evaluate(model, ps, subsets=False):
    model.eval(); correct = 0; hits = []
    dl = DataLoader(PairDS(ps), batch_size=a.bs * 2, collate_fn=collate)
    for (bi, bm), (wi, wm), _ in dl:
        rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
        h = (rb > rw)
        correct += h.sum().item()
        if subsets or os.environ.get("RM_EVAL_BREAKDOWN"): hits.extend(h.tolist())
    acc = correct / max(len(ps), 1)
    if os.environ.get("RM_EVAL_BREAKDOWN") and hits:
        import collections as _c
        agg = _c.defaultdict(lambda: [0, 0])   # per-task-acc
        for h, p_ in zip(hits, ps):
            a_ = agg[p_["task"]]; a_[0] += int(h); a_[1] += 1
        for t_, (k_, n_) in sorted(agg.items()):
            print(f"[task-acc] {t_[:36]:36s} {k_}/{n_} = {k_/max(n_,1):.3f}", flush=True)
    if not subsets:
        return acc
    # split by whether the value ranking agrees with the "better right now" ranking
    ag = [h for h, p in zip(hits, ps) if p.get("agrees_with_quality") is True]
    dis = [h for h, p in zip(hits, ps) if p.get("agrees_with_quality") is False]
    subset_acc = {"agree_n": len(ag), "agree_acc": (sum(ag) / len(ag)) if ag else None,
                  "disagree_n": len(dis), "disagree_acc": (sum(dis) / len(dis)) if dis else None}
    return acc, subset_acc

rows = []
for N in [int(x) for x in re.split(r"[,;:]", a.sizes) if x.strip()]:
    if N > len(train_pool):
        print(f"[rm] skip N={N} (> pool {len(train_pool)})"); continue
    sub = train_pool[:N]
    _skip_base = (N == 0)   # TARGET-ONLY control: no cross-task pretraining
    model = RM(a.model).cuda()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    dl = [] if _skip_base else DataLoader(PairDS(sub), batch_size=a.bs, shuffle=True, collate_fn=collate, drop_last=True)
    t0 = time.time(); model.train(); step = 0
    for ep in range(0 if _skip_base else a.epochs):
        for (bi, bm), (wi, wm), w in dl:
            rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
            loss = -(w.cuda() * torch.nn.functional.logsigmoid(rb - rw)).mean() / a.accum
            loss.backward(); step += 1
            if step % a.accum == 0:
                opt.step(); opt.zero_grad()
    tr_probe = sub[:min(len(sub), 800)]
    tr_acc = evaluate(model, tr_probe)
    print(f"[fit] N={N} TRAIN acc={tr_acc:.4f} (n={len(tr_probe)})  <- high+low test = memorization; low+low = underfit", flush=True)
    _has_flag = any(p.get("agrees_with_quality") is not None for p in test_pool)
    if _has_flag:
        acc, sub = evaluate(model, test_pool, subsets=True)
        print(f"[sub] N={N} overall={acc:.4f} | agree n={sub['agree_n']} acc="
              f"{sub['agree_acc']:.4f} | DISAGREE n={sub['disagree_n']} acc={sub['disagree_acc']:.4f}"
              f"  (shortcut baseline would be 1.00 / 0.00)", flush=True)
    else:
        acc = evaluate(model, test_pool); sub = {}
    wall = round(time.time() - t0, 1)

    if a.fewshot_ks and ft_pool:
        import copy
        base_state = copy.deepcopy({k: v.detach().clone()
                                    for k, v in model.state_dict().items()})
        random.Random(a.seed + 1).shuffle(ft_pool)
        for K in [int(x) for x in re.split(r"[,;:]", a.fewshot_ks) if x.strip()]:
            if K == 0:
                print(f"[fs] N={N} K=0 acc={acc:.4f} (zero-shot baseline)", flush=True)
                rows.append({"N": N, "split": split_name + "|K=0", "acc": round(acc, 4),
                             "tau_weight": a.tau_weight, "model": os.path.basename(a.model),
                             "seed": a.seed, "wall_s": wall, "n_test": len(test_pool),
                             "max_len": a.max_len, "lr": a.lr, "task_cond": a.task_cond,
                             "head_frac": a.head_frac})
                continue
            if K > len(ft_pool):
                print(f"[fs] skip K={K} (ft_pool={len(ft_pool)})"); continue
            model.load_state_dict(base_state)
            fopt = torch.optim.AdamW([q for q in model.parameters() if q.requires_grad], lr=a.ft_lr)
            fdl = DataLoader(PairDS(ft_pool[:K]), batch_size=a.bs, shuffle=True, collate_fn=collate)
            model.train(); st_ = 0; tf = time.time()
            for _ in range(a.ft_epochs):
                for (bi, bm), (wi, wm), w in fdl:
                    rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
                    l = -(w.cuda() * torch.nn.functional.logsigmoid(rb - rw)).mean() / a.accum
                    l.backward(); st_ += 1
                    if st_ % a.accum == 0: fopt.step(); fopt.zero_grad()
            fopt.step(); fopt.zero_grad()
            fa = evaluate(model, test_pool)
            print(f"[fs] N={N} K={K} acc={fa:.4f} (zero-shot was {acc:.4f})", flush=True)
            rows.append({"N": N, "split": split_name + f"|K={K}", "acc": round(fa, 4),
                         "tau_weight": a.tau_weight, "model": os.path.basename(a.model),
                         "seed": a.seed, "wall_s": round(time.time() - tf, 1),
                         "n_test": len(test_pool), "max_len": a.max_len, "lr": a.ft_lr,
                         "task_cond": a.task_cond, "head_frac": a.head_frac})
            del fopt
        model.load_state_dict(base_state); del base_state
    print(f"[rm] N={N} {split_name} acc={acc:.4f} wall={wall}s", flush=True)
    rows.append({"N": N, "split": split_name, "acc": round(acc, 4), "tau_weight": a.tau_weight,
                 "model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,
                 "n_test": len(test_pool), "max_len": a.max_len, "lr": a.lr,
                 "task_cond": a.task_cond, "head_frac": a.head_frac, "train_acc": round(tr_acc, 4),
                 "disagree_acc": (sub or {}).get("disagree_acc"),
                 "agree_acc": (sub or {}).get("agree_acc")})
    if a.ft_pairs:
        ftp = [json.loads(l) for l in open(a.ft_pairs)]
        ftp = [p_ for p_ in ftp if p_["better"] in code and p_["worse"] in code]
        fopt = torch.optim.AdamW([q for q in model.parameters() if q.requires_grad], lr=a.ft_lr)
        fdl = DataLoader(PairDS(ftp), batch_size=a.bs, shuffle=True, collate_fn=collate)
        model.train(); st_ = 0
        for _ in range(a.ft_epochs):
            for (bi, bm), (wi, wm), w in fdl:
                rb = model(bi.cuda(), bm.cuda()); rw = model(wi.cuda(), wm.cuda())
                l_ = -(w.cuda() * torch.nn.functional.logsigmoid(rb - rw)).mean() / a.accum
                l_.backward(); st_ += 1
                if st_ % a.accum == 0: fopt.step(); fopt.zero_grad()
        fopt.step(); fopt.zero_grad()
        if _has_flag:
            fa, fsub = evaluate(model, test_pool, subsets=True)
        else:
            fa = evaluate(model, test_pool); fsub = {}
        print(f"[ft] after {len(ftp)}-pair fine-tune: acc={fa:.4f} (base was {acc:.4f})", flush=True)
        rows.append({"N": N, "split": split_name + f"|ft{len(ftp)}", "acc": round(fa, 4),
                     "tau_weight": a.tau_weight, "model": os.path.basename(a.model), "seed": a.seed,
                     "wall_s": 0.0, "n_test": len(test_pool), "max_len": a.max_len, "lr": a.ft_lr,
                     "task_cond": a.task_cond, "head_frac": a.head_frac,
                     "disagree_acc": (fsub or {}).get("disagree_acc"), "agree_acc": (fsub or {}).get("agree_acc")})
        del fopt

    if a.save_adapter:
        import os as _os
        d = _os.path.join(a.save_adapter, f"N{N}")
        _os.makedirs(d, exist_ok=True)
        model.backbone.save_pretrained(d)
        torch.save(model.head.state_dict(), _os.path.join(d, "head.pt"))
        json.dump({"base_model": a.model, "max_len": a.max_len, "task_cond": a.task_cond,
                   "head_frac": a.head_frac, "N": N, "split": split_name, "acc": acc,
                   "pairs": a.pairs}, open(_os.path.join(d, "rm_meta.json"), "w"), indent=1)
        print(f"[rm] saved adapter -> {d}", flush=True)
    del model, opt; torch.cuda.empty_cache()

import csv
if not rows:
    print("[rm] NO ROWS - every requested N exceeded the train pool; nothing written", flush=True)
    raise SystemExit(0)
new = not os.path.exists(a.out)
with open(a.out, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    if new: w.writeheader()
    for r in rows: w.writerow(r)
print(f"[rm] wrote {len(rows)} rows -> {a.out}")
