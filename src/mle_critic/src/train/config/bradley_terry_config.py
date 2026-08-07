"""Hugging Face TrainingArguments for Bradley–Terry reward-model training."""

from __future__ import annotations

from dataclasses import dataclass, field
import os

from transformers import TrainingArguments


@dataclass
class BradleyTerryConfig(TrainingArguments):
    """All CLI arguments used by bradley_terry.py.

    The inherited TrainingArguments fields are intentionally used for batch size,
    accumulation, learning rate, epochs, evaluation, saving, and distributed setup.
    """

    pairs: str = field(default="", metadata={"help": "pair JSONL file"})
    cards: str = field(default="", metadata={"help": "cards JSONL file"})
    sizes: str = field(default="8000", metadata={"help": "comma/colon/semicolon-separated train caps"})
    model: str = field(
        default_factory=lambda: os.environ.get("MLE_CRITIC_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
        metadata={"help": "backbone model"},
    )
    max_len: int = field(default=8192, metadata={"help": "maximum input length"})
    head_frac: float = field(default=0.25, metadata={"help": "fraction retained from the input head"})
    task_cond: bool = field(default=True, metadata={"help": "prepend the MLE-bench task name"})
    loto: str = field(default="", metadata={"help": "leave this task out of the training pool"})
    eval_steps: int = field(default=20, metadata={"help": "evaluation interval in optimizer steps"})
    budget_cond: bool = field(default=False, metadata={"help": "include the remaining budget"})
    budget_pos: str = field(default="head", metadata={"help": "budget position: head or tail"})

    # Training defaults specific to this objective. These remain overridable by
    # the standard TrainingArguments CLI flags.
    output_dir: str = field(default="outputs/mle_critic/rmhf")
    per_device_train_batch_size: int = field(default=1)
    per_device_eval_batch_size: int = field(default=1)
    gradient_accumulation_steps: int = field(default=16)
    learning_rate: float = field(default=1e-5)
    num_train_epochs: float = field(default=1.0)
    lr_scheduler_type: str = field(default="cosine")
    warmup_ratio: float = field(default=0.03)
    max_grad_norm: float = field(default=1.0)
    bf16: bool = field(default=True)
    logging_steps: float = field(default=1)
    eval_strategy: str = field(default="steps")
    save_strategy: str = field(default="best")
    load_best_model_at_end: bool = field(default=False)
    metric_for_best_model: str = field(default="eval_loss")
    greater_is_better: bool = field(default=False)
    save_total_limit: int = field(default=1)
    report_to: list[str] = field(default_factory=lambda: ["wandb"])
    remove_unused_columns: bool = field(default=False)
    save_only_model: bool = field(default=True)
    dataloader_num_workers: int = field(default=2)

    def __post_init__(self):
        super().__post_init__()
        if not self.pairs:
            raise ValueError("--pairs is required")
        if not self.cards:
            raise ValueError("--cards is required")
        if self.budget_pos not in {"head", "tail"}:
            raise ValueError("--budget-pos must be head or tail")
