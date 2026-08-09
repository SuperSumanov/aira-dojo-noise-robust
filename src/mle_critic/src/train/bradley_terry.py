"""Full fine-tuning for a pairwise Bradley–Terry reward model.

Single-GPU smoke test from the repository root:

  accelerate launch src/mle_critic/src/train/bradley_terry.py \
      --pairs P --cards C --max-len 2048 \
      --per-device-train-batch-size 1

Multi-GPU ZeRO-3 training:

  accelerate launch --config_file src/mle_critic/recipes/zero3.yaml \
      --num_processes 8 src/mle_critic/src/train/bradley_terry.py \
      --pairs P --cards C --max-len 8192 \
      --per-device-train-batch-size 2 --gradient-accumulation-steps 2
"""

from __future__ import annotations

from functools import partial
import random

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer, HfArgumentParser, Trainer

from src.mle_critic.src.evaluation.bradley_terry_evaluation import pair_accuracy_metrics
from src.mle_critic.src.train.config import BradleyTerryConfig
from src.mle_critic.src.train.dataset import (
    CardEncoder,
    PairDataset,
    load_training_pool,
    load_testing_pool,
    pair_collate,
    read_cards,
    read_pairs,
)


class BradleyTerryRewardModel(nn.Module):
    def __init__(self, model_name: str):
        super().__init__()
        model_kwargs = {"torch_dtype": torch.bfloat16}
        try:
            self.backbone = AutoModel.from_pretrained(
                model_name,
                attn_implementation="flash_attention_2",
                **model_kwargs,
            )
        except Exception:
            self.backbone = AutoModel.from_pretrained(model_name, **model_kwargs)
        self.backbone.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)

    def forward(self, input_ids=None, attention_mask=None, **kwargs):
        hidden_states = self.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
        ).last_hidden_state
        final_token_indices = attention_mask.sum(dim=1) - 1
        pooled_states = hidden_states[
            torch.arange(hidden_states.size(0), device=hidden_states.device),
            final_token_indices,
        ]
        return {"logits": self.head(pooled_states).squeeze(-1).float()}


class BradleyTerryTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        scores = model(**inputs)["logits"]
        pair_count = scores.size(0) // 2
        better_scores = scores[:pair_count]
        worse_scores = scores[pair_count:]
        margins = better_scores - worse_scores
        loss = -torch.nn.functional.logsigmoid(margins).mean()
        return (loss, {"logits": margins}) if return_outputs else loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):
        """Return score margins so Trainer can compute validation accuracy."""
        prepared_inputs = self._prepare_inputs(inputs)
        with torch.no_grad(), self.compute_loss_context_manager():
            scores = model(**prepared_inputs)["logits"]
            pair_count = scores.size(0) // 2
            margins = scores[:pair_count] - scores[pair_count:]
            loss = -torch.nn.functional.logsigmoid(margins).mean()
        if prediction_loss_only:
            return loss.detach(), None, None
        labels = torch.ones_like(margins)
        return loss.detach(), margins.detach(), labels


def main() -> None:
    parser = HfArgumentParser(BradleyTerryConfig)
    (config,) = parser.parse_args_into_dataclasses()

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)

    card_codes, card_tasks = read_cards(config.cards)
    pair_records = read_pairs(config.pairs, card_codes)
    training_pool, split_name = load_training_pool(
        pair_records,
        loto=config.loto,
        seed=config.seed,
    )
    testing_pool, _ = load_testing_pool(
        pair_records,
        loto=config.loto,
        seed=config.seed,
    )
    if len(training_pool) < 2:
        raise ValueError("training pool has fewer than two records; cannot create validation data")

    training_records = training_pool
    validation_records = testing_pool
    print(
        f"[rm-hf] split={split_name} total={len(training_pool)} "
        f"train={len(training_records)} validation={len(validation_records)}",
        flush=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(config.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    card_encoder = CardEncoder(
        code=card_codes,
        tasks=card_tasks,
        tokenizer=tokenizer,
        max_len=config.max_len,
        head_frac=config.head_frac,
        task_cond=config.task_cond,
        budget_cond=config.budget_cond,
        budget_pos=config.budget_pos,
    )
    model = BradleyTerryRewardModel(config.model)
    trainer = BradleyTerryTrainer(
        model=model,
        args=config,
        train_dataset=PairDataset(training_records, card_encoder),
        eval_dataset=PairDataset(validation_records, card_encoder),
        data_collator=partial(pair_collate, pad_token_id=tokenizer.pad_token_id),
        compute_metrics=pair_accuracy_metrics,
    )
    trainer.train()
    if trainer.is_world_process_zero():
        print(
            f"[rm-hf] training complete; best_validation_loss={trainer.state.best_metric} "
            f"best_checkpoint={trainer.state.best_model_checkpoint}",
            flush=True,
        )


if __name__ == "__main__":
    main()
