"""RM training, production version: HF Trainer + (optional) DeepSpeed ZeRO-3.

Pairwise Bradley-Terry reward model over MLE solution code. Aligned with rm_train.py semantics
(same pairs/cards files, same task-conditioning, same head+tail truncation, same split fields)
so numbers are directly comparable; adds: full/LoRA fine-tuning, bf16, grad clipping, cosine
schedule with warmup, gradient checkpointing, flash-attention-2, multi-GPU via deepspeed.

Single-GPU smoke (3090, from the repository root):
  python -m src.mle_critic.src.train.reward_model --pairs P --cards C \
      --sizes 2000 --max-len 2048 --lora

8xH200 full-precision full-context (from repo root):
  deepspeed --num_gpus 8 src/mle_critic/src/train/reward_model.py \
      --pairs P --cards C --sizes 24000 --max-len 8192 \
      --deepspeed src/mle_critic/src/train/ds_zero3_offload.json --bs 2 --accum 2
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

from src.mle_critic.evaluation.reward_model_evaluation import (
    evaluate_budget_flips,
    evaluate_pairs,
    pair_accuracy_metrics,
)

ap = argparse.ArgumentParser()
ap.add_argument("--pairs", required=True)
ap.add_argument("--cards", required=True)
ap.add_argument("--sizes", default="8000")
ap.add_argument("--model", default=os.environ.get("MLE_CRITIC_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"))
ap.add_argument("--max-len", type=int, default=8192)
ap.add_argument("--head-frac", type=float, default=0.25)
ap.add_argument("--task-cond", action="store_true", default=True)
ap.add_argument("--loto", default="")
ap.add_argument("--eval-cap", type=int, default=1500)
ap.add_argument("--eval-steps", type=int, default=20,
                help="validate and consider a checkpoint every N optimizer steps")
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
ap.add_argument("--out", default="outputs/mle_critic/rm_curve_hf.csv")
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
    code[d["id"]] = (d.get("code") or "")
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
print(
    f"[rm-hf] split={split_name} train_pool={len(train_pool)} test={len(test_pool)}",
    flush=True,
)

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


def encode_card(cid, budget=None):
    """Render and tokenize one card using the configured task/budget conditioning."""
    conditioned_budget = budget if a.budget_cond else None
    suffix = (
        tok(NL + budget_line(conditioned_budget), add_special_tokens=False)["input_ids"]
        if conditioned_budget is not None and a.budget_pos == "tail"
        else None
    )
    token_ids = tok(render(cid, conditioned_budget), add_special_tokens=False)["input_ids"]
    return fit(token_ids, suffix)


class PairDS(Dataset):
    def __init__(self, ps):
        self.ps = ps

    def __len__(self):
        return len(self.ps)

    def __getitem__(self, i):
        p = self.ps[i]
        return {
            "b": encode_card(p["better"], p.get("budget")),
            "w": encode_card(p["worse"], p.get("budget")),
        }


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


rows = []
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
    targs = TrainingArguments(
        output_dir=f"{a.out}/rmhf_" + str(os.getpid()) + "_" + str(N),
        per_device_train_batch_size=a.bs,
        per_device_eval_batch_size=a.bs,
        gradient_accumulation_steps=a.accum, num_train_epochs=a.epochs, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_ratio=0.03, max_grad_norm=1.0, bf16=True,
        logging_steps=1, eval_strategy="steps", eval_steps=a.eval_steps,
        save_strategy="best",
        load_best_model_at_end=True, metric_for_best_model="eval_loss",
        greater_is_better=False, save_total_limit=1, report_to=["wandb"], seed=a.seed,
        deepspeed=a.deepspeed, remove_unused_columns=False, dataloader_num_workers=2)
    tr = BTTrainer(
        model=model,
        args=targs,
        train_dataset=PairDS(training_subset),
        eval_dataset=PairDS(validation_pool),
        data_collator=collate,
        compute_metrics=pair_accuracy_metrics,
    )
    t0 = time.time()
    tr.train()
    # ZeRO-3 forward passes are collective. Every rank evaluates the same records;
    # only rank zero prints breakdowns and persists the resulting metrics.
    is_main_process = tr.is_world_process_zero()
    evaluation_model = tr.model_wrapped
    evaluation_batch_size = max(a.bs, 2)
    acc = evaluate_pairs(
        evaluation_model,
        test_pool,
        evaluation_batch_size,
        encode_card,
        tok.pad_token_id,
        breakdown=is_main_process,
    )
    acc_len = None
    if a.eval_len_control > 0:
        def _close(p):
            x, y = len(code.get(p["better"], "")), len(code.get(p["worse"], ""))
            m = max(x, y)
            return m > 0 and abs(x - y) / m <= a.eval_len_control
        length_control_pairs = [p for p in test_pool if _close(p)]
        if len(length_control_pairs) >= 100:
            acc_len = evaluate_pairs(
                evaluation_model,
                length_control_pairs,
                evaluation_batch_size,
                encode_card,
                tok.pad_token_id,
                breakdown=False,
            )
            if is_main_process:
                print("[len-ctrl] n=" + str(len(length_control_pairs)) + " (" +
                      str(len(length_control_pairs) * 100 // max(len(test_pool), 1)) + "% of eval) acc=" +
                      format(acc_len, ".4f"), flush=True)
        elif is_main_process:
            print("[len-ctrl] only " + str(len(length_control_pairs)) +
                  " pairs within the length ratio; skipped", flush=True)
    fe = None
    if a.flip_eval:
        fe = evaluate_budget_flips(
            evaluation_model,
            a.flip_eval,
            evaluation_batch_size * 2,
            encode_card,
            tok.pad_token_id,
            code,
            verbose=is_main_process,
        )
    if is_main_process:
        wall = round(time.time() - t0, 1)
        print(f"[rm-hf] N={N} {split_name} acc={acc:.4f} wall={wall}s", flush=True)
        row = {"N": N, "split": split_name, "acc": round(acc, 4),
                     "n_train_actual": len(training_subset),
                     "n_validation": len(validation_pool),
                     "best_validation_loss": tr.state.best_metric,
                     "best_checkpoint": tr.state.best_model_checkpoint,
                     "model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,
                     "n_test": len(test_pool), "max_len": a.max_len, "lr": a.lr,
                     "lora": a.lora, "budget_cond": a.budget_cond, "budget_pos": a.budget_pos,
               "pairs_file": os.path.basename(a.pairs),
               "acc_len_ctrl": acc_len, "stratified": a.eval_stratify,
                     "trainer": "hf+ds" if a.deepspeed else "hf"}
        if fe is not None:
            for kind, d_ in fe.items():
                for k_, v_ in d_.items():
                    row[kind + "_" + k_] = round(v_, 4) if isinstance(v_, float) else v_
        rows.append(row)
        if a.save_adapter:
            dd = os.path.join(a.save_adapter, "N" + str(N))
            os.makedirs(dd, exist_ok=True)
            tr.model.backbone.save_pretrained(dd, safe_serialization=True)
            torch.save(tr.model.head.state_dict(), os.path.join(dd, "head.pt"))
            # reward_model_server.py boots from this file; without it the export is unusable
            json.dump({"base_model": a.model, "max_len": a.max_len,
                       "head_frac": a.head_frac, "task_cond": a.task_cond,
                       "lora": a.lora, "pairs": a.pairs, "N": N, "seed": a.seed,
                       "n_train_actual": len(training_subset),
                       "n_validation": len(validation_pool),
                       "best_validation_loss": tr.state.best_metric,
                       "best_checkpoint": tr.state.best_model_checkpoint,
                       "acc": round(acc, 4), "budget_cond": a.budget_cond,
                       "budget_pos": a.budget_pos},
                      open(os.path.join(dd, "rm_meta.json"), "w"))
    del evaluation_model, model, tr
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
    out_parent = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(out_parent, exist_ok=True)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[rm-hf] wrote {len(rows)} rows -> {a.out}")
