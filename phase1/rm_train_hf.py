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
ap.add_argument("--eval-stratify", action="store_true",
                help="equal share of the eval budget per task, not proportional")
ap.add_argument("--eval-min-task", type=int, default=60,
                help="skip tasks with fewer held-out pairs than this")
ap.add_argument("--eval-len-control", type=float, default=0.0,
                help="also report accuracy on pairs whose code lengths are within this ratio (e.g. 0.15); 0 disables")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--bs", type=int, default=1, help="per-device batch of PAIRS")
ap.add_argument("--accum", type=int, default=16)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--lora", action="store_true", help="LoRA instead of full fine-tune")
ap.add_argument("--deepspeed", default=None)
ap.add_argument("--out", default="phase1/rm_curve_hf.csv")
ap.add_argument("--flip-eval", default="", help="budget-flip eval file (paired lo/hi budgets)")
ap.add_argument("--save-adapter", default="")
ap.add_argument("--budget-cond", action="store_true", help="expose remaining budget to the model")
ap.add_argument("--budget-pos", default="head", choices=["head", "tail"],
                help="where the budget line goes; tail puts it next to the pooled token")
ap.add_argument("--local_rank", type=int, default=-1)  # injected by the deepspeed launcher
a = ap.parse_args()

NL = chr(10)
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
_seen = set()
_uniq = []
for _p in test_pool:
    _k = (_p["better"], _p["worse"], _p.get("budget"))
    if _k in _seen:
        continue
    _seen.add(_k)
    _uniq.append(_p)
if len(_uniq) != len(test_pool):
    print("[rm-hf] deduped test pool: " + str(len(test_pool)) + " -> " + str(len(_uniq)) +
          " (oversampled train-side records leaking into a LOTO test set)", flush=True)
test_pool = _uniq
if a.eval_stratify:
    _bt = {}
    for _p in test_pool:
        _bt.setdefault(_p["task"], []).append(_p)
    _tasks = [t for t in sorted(_bt) if len(_bt[t]) >= a.eval_min_task]
    _per = max(a.eval_cap // max(len(_tasks), 1), a.eval_min_task)
    test_pool = [p for t in _tasks for p in _bt[t][:_per]]
    print("[rm-hf] stratified eval over " + str(len(_tasks)) + " tasks, <=" +
          str(_per) + " pairs each", flush=True)
else:
    test_pool = test_pool[:a.eval_cap]
print(f"[rm-hf] split={split_name} train_pool={len(train_pool)} test={len(test_pool)}", flush=True)

tok = AutoTokenizer.from_pretrained(a.model)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"


def budget_line(budget):
    return ("# remaining budget: unlimited" + NL if budget == 0
            else "# remaining budget: " + str(budget) + " steps" + NL)


def render(cid, budget=None):
    head = ""
    if a.task_cond:
        head += "# MLE-bench task: " + ctask.get(cid, "") + NL
    if budget is not None and a.budget_pos == "head":
        head += budget_line(budget)
    return head + code[cid]


def fit(ids, suffix=None):
    """Truncate, then append the suffix -- so a tail-placed budget survives truncation."""
    room = a.max_len - (len(suffix) if suffix else 0)
    if len(ids) > room:
        h = int(room * a.head_frac)
        ids = ids[:h] + ids[len(ids) - (room - h):]
    return ids + (suffix or [])


class PairDS(Dataset):
    def __init__(self, ps):
        self.ps = ps

    def __len__(self):
        return len(self.ps)

    def __getitem__(self, i):
        p = self.ps[i]
        bd = p.get("budget") if a.budget_cond else None
        sfx = (tok(NL + budget_line(bd), add_special_tokens=False)["input_ids"]
               if bd is not None and a.budget_pos == "tail" else None)
        return {"b": fit(tok(render(p["better"], bd), add_special_tokens=False)["input_ids"], sfx),
                "w": fit(tok(render(p["worse"], bd), add_special_tokens=False)["input_ids"], sfx)}


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
def evaluate_pairs(model, ps, bs, breakdown=True):
    model.eval()
    dev = next(model.parameters()).device
    ds = PairDS(ps)
    correct = 0
    hits = []
    for i in range(0, len(ps), bs):
        batch = collate([ds[j] for j in range(i, min(i + bs, len(ps)))])
        out = model(input_ids=batch["input_ids"].to(dev),
                    attention_mask=batch["attention_mask"].to(dev))["logits"]
        n = out.size(0) // 2
        h = (out[:n] > out[n:])
        correct += h.sum().item()
        hits.extend(h.tolist())
    if breakdown:
        import collections as _c
        agg = _c.defaultdict(lambda: [0, 0])
        for h, p_ in zip(hits, ps):
            keys = [p_["task"]]
            if "budget" in p_:
                keys.append("BUDGET=" + str(p_["budget"]))
                if p_.get("flips_vs_b1"):
                    keys.append("FLIPS@B" + str(p_["budget"]))
            for k_ in keys:
                a_ = agg[k_]; a_[0] += int(h); a_[1] += 1
        for t_, (k_, n_) in sorted(agg.items()):
            print(f"[task-acc] {t_[:40]:40s} {k_}/{n_} = {k_/max(n_,1):.3f}", flush=True)
    return correct / max(len(ps), 1)


@torch.no_grad()
def flip_eval(model, path, bs):
    """Same pair, two budgets. On flip pairs a budget-blind model is exactly 0.500."""
    recs = [json.loads(l) for l in open(path)]
    recs = [r for r in recs if r["x"] in code and r["y"] in code]
    if not recs:
        return {}
    model.eval()
    dev = next(model.parameters()).device
    want = sorted({(r[k], r[b]) for r in recs for k in ("x", "y")
                   for b in ("budget_lo", "budget_hi")})
    score = {}
    for i in range(0, len(want), bs):
        chunk = want[i:i + bs]
        seqs = []
        for c, b in chunk:
            bb = b if a.budget_cond else None
            sfx = (tok(NL + budget_line(bb), add_special_tokens=False)["input_ids"]
                   if bb is not None and a.budget_pos == "tail" else None)
            seqs.append(fit(tok(render(c, bb), add_special_tokens=False)["input_ids"], sfx))
        m = max(len(x) for x in seqs)
        ids = torch.tensor([x + [tok.pad_token_id] * (m - len(x)) for x in seqs]).to(dev)
        msk = torch.tensor([[1] * len(x) + [0] * (m - len(x)) for x in seqs]).to(dev)
        out = model(input_ids=ids, attention_mask=msk)["logits"].tolist()
        for k, v in zip(chunk, out):
            score[k] = v
    agg = {}
    gaps = sorted({r["budget_hi"] for r in recs})
    combos = [(k, g) for k in ("flip", "control") for g in gaps]
    for kind, gap in combos:
        rs = [r for r in recs if r["kind"] == kind and r["budget_hi"] == gap]
        if not rs:
            continue
        lo_ok = hi_ok = moved = sw_right = 0
        for r in rs:
            pl = r["x"] if score[(r["x"], r["budget_lo"])] > score[(r["y"], r["budget_lo"])] else r["y"]
            ph = r["x"] if score[(r["x"], r["budget_hi"])] > score[(r["y"], r["budget_hi"])] else r["y"]
            lo_ok += pl == r["better_lo"]
            hi_ok += ph == r["better_hi"]
            if pl != ph:
                moved += 1
                # a switch is right when it tracks the label change on both sides
                sw_right += (pl == r["better_lo"] and ph == r["better_hi"])
        n_ = len(rs)
        agg[kind + str(gap)] = {"n": n_, "acc_lo": lo_ok / n_, "acc_hi": hi_ok / n_,
                                "acc_mean": (lo_ok + hi_ok) / (2 * n_), "moved": moved / n_,
                                "n_switch": moved, "switch_acc": (sw_right / moved) if moved else None}
        per = {}
        for r in rs:
            pl = r["x"] if score[(r["x"], r["budget_lo"])] > score[(r["y"], r["budget_lo"])] else r["y"]
            ph = r["x"] if score[(r["x"], r["budget_hi"])] > score[(r["y"], r["budget_hi"])] else r["y"]
            e = per.setdefault(r["task"], [0, 0])
            e[0] += (pl == r["better_lo"]) + (ph == r["better_hi"]); e[1] += 2
        for t_ in sorted(per):
            k_, m_ = per[t_]
            print("[flip-task] " + kind + " K" + str(gap) + " " + t_[:40] + " " + str(k_) + "/" + str(m_) +
                  " = " + format(k_ / max(m_, 1), ".3f"), flush=True)
        print("[flip-eval] " + kind + " K1->K" + str(gap) + " n=" + str(n_) +
              " acc@lo=" + format(lo_ok / n_, ".4f") + " acc@hi=" + format(hi_ok / n_, ".4f") +
              " mean=" + format((lo_ok + hi_ok) / (2 * n_), ".4f") +
              " model_switched=" + format(moved / n_, ".4f") +
              (" switch_acc=" + format(sw_right / moved, ".3f") + " of " + str(moved)
               if moved else ""), flush=True)
    for g in gaps:
        f_, c_ = agg.get("flip" + str(g)), agg.get("control" + str(g))
        if f_ and c_ and c_["moved"] > 0:
            sel = f_["moved"] / c_["moved"]
            f_["selectivity"] = sel
            print("[flip-sel] K1->K" + str(g) + " switches on flip pairs vs controls: " +
                  str(f_["n_switch"]) + " vs " + str(c_["n_switch"]) +
                  " = " + format(sel, ".2f") + "x", flush=True)
    return agg


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
        acc_len = None
        if a.eval_len_control > 0:
            def _close(p):
                x, y = len(code.get(p["better"], "")), len(code.get(p["worse"], ""))
                m = max(x, y)
                return m > 0 and abs(x - y) / m <= a.eval_len_control
            sub = [p for p in test_pool if _close(p)]
            if len(sub) >= 100:
                acc_len = evaluate_pairs(tr.model, sub, max(a.bs, 2), breakdown=False)
                print("[len-ctrl] n=" + str(len(sub)) + " (" +
                      str(len(sub) * 100 // max(len(test_pool), 1)) + "% of eval) acc=" +
                      format(acc_len, ".4f"), flush=True)
            else:
                print("[len-ctrl] only " + str(len(sub)) + " pairs within the length ratio; skipped", flush=True)
        wall = round(time.time() - t0, 1)
        print(f"[rm-hf] N={N} {split_name} acc={acc:.4f} wall={wall}s", flush=True)
        row = {"N": N, "split": split_name, "acc": round(acc, 4),
                     "model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,
                     "n_test": len(test_pool), "max_len": a.max_len, "lr": a.lr,
                     "lora": a.lora, "budget_cond": a.budget_cond, "budget_pos": a.budget_pos,
               "pairs_file": os.path.basename(a.pairs),
               "acc_len_ctrl": acc_len, "stratified": a.eval_stratify,
                     "trainer": "hf+ds" if a.deepspeed else "hf"}
        if a.flip_eval:
            fe = flip_eval(tr.model, a.flip_eval, max(a.bs, 2) * 2)
            for kind, d_ in fe.items():
                for k_, v_ in d_.items():
                    row[kind + "_" + k_] = round(v_, 4) if isinstance(v_, float) else v_
        rows.append(row)
        if a.save_adapter:
            dd = os.path.join(a.save_adapter, "N" + str(N))
            os.makedirs(dd, exist_ok=True)
            try:
                import deepspeed
                _gather = deepspeed.zero.GatheredParameters(
                    list(tr.model.backbone.parameters()), modifier_rank=0)
            except ImportError:
                import contextlib
                _gather = contextlib.nullcontext()
            with _gather:
                tr.model.backbone.save_pretrained(dd, safe_serialization=True)
            torch.save({k: v.detach().float().cpu().clone()
                        for k, v in tr.model.head.state_dict().items()},
                       os.path.join(dd, "head.pt"))
            from safetensors import safe_open
            _saved = 0
            for _fn in os.listdir(dd):
                if _fn.endswith(".safetensors"):
                    with safe_open(os.path.join(dd, _fn), framework="pt") as _sf:
                        for _k in _sf.keys():
                            _saved += _sf.get_slice(_k).get_shape()[0] if False else 1
            _live = sum(1 for _ in tr.model.backbone.state_dict())
            print(f"[save-verify] tensors saved={_saved} live={_live}", flush=True)
            if _saved < _live:
                raise RuntimeError(f"checkpoint incomplete: {_saved}/{_live} tensors")
            # rm_server.py boots from this file; a checkpoint without it is unusable
            json.dump({"base_model": a.model, "max_len": a.max_len,
                       "head_frac": a.head_frac, "task_cond": a.task_cond,
                       "lora": a.lora, "pairs": a.pairs, "N": N, "seed": a.seed,
                       "acc": round(acc, 4), "budget_cond": a.budget_cond},
                      open(os.path.join(dd, "rm_meta.json"), "w"))
    del model, tr
    torch.cuda.empty_cache()

if rows:
    # a header written by an older trainer version must not receive rows with more
    # columns -- DictWriter would silently write ragged lines. Diverge to _s2 instead.
    if os.path.exists(a.out):
        with open(a.out) as _f:
            _hdr = _f.readline().strip().split(",")
        if _hdr != list(rows[0].keys()):
            a.out = a.out.replace(".csv", "_s2.csv")
            print("[rm-hf] header mismatch with existing csv; writing to " + a.out, flush=True)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[rm-hf] wrote {len(rows)} rows -> {a.out}")
