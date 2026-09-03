"""Bounded single-process CPU Trainer prototype; NOT a research training entry.

Only synthetic IDs, <=128 pairs and <=4096 model parameters are accepted.
No CLI or real-data reader. Never modifies the pending G0 source/runtime.
Checkpoint loading is restricted to explicit, hash-bound complete checkpoints;
this is integrity checking, not trust/authenticity for third-party checkpoints.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
import transformers
from transformers import Trainer

from phase1.global_local_execution_plan import PlanError, digest_records
from phase1.global_local_batch_adapter import PackedBatch, observe_batch, pack_batch
from phase1.verify_global_local_execution_trace import BatchReceipt, verify_plan, verify_prefix


RUNTIME_VERSIONS = {"torch": "2.11.0+cu128", "transformers": "5.12.1", "accelerate": "1.14.0"}
TRAINER_SHA256 = "c1a56423fcfcf9cfec6847467ffb2e2c8a9a9e8cc1836b82c87ed0c81e504be0"
CHECKPOINT_FILES = ("model.safetensors", "optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json")


def runtime_binding():
    import accelerate
    import inspect
    versions = {"torch": torch.__version__, "transformers": transformers.__version__, "accelerate": accelerate.__version__}
    if versions != RUNTIME_VERSIONS:
        raise PlanError("unvalidated_runtime_version")
    digest = hashlib.sha256(Path(inspect.getfile(Trainer)).read_bytes()).hexdigest()
    if digest != TRAINER_SHA256:
        raise PlanError("unvalidated_trainer_source")
    return dict(versions, trainer_sha256=digest)


class _Rows(Dataset):
    def __init__(self, plan):
        self.locations = tuple((i, j) for i, b in enumerate(plan.batches) for j in range(len(b.rows)))

    def __len__(self):
        return len(self.locations)

    def __getitem__(self, index):
        return self.locations[index]


class _FixedBatches:
    def __init__(self, plan):
        self.width = plan.shape.pairs_per_rank
        self.count = len(plan.batches)

    def __len__(self):
        return self.count

    def __iter__(self):
        for i in range(self.count):
            yield list(range(i * self.width, (i + 1) * self.width))


def _decode_receipt(data):
    return BatchReceipt(data["plan_sha256"], data["optimizer_step"], data["micro_step"], data["rank"],
                        tuple(data["pair_keys"]), tuple(tuple(x) for x in data["encoded_digests"]),
                        data["valid_tokens"], data["padded_slots"])


class CPUPlannedTrainer(Trainer):
    def __init__(self, *, plan, pools, encoding_provider, true_sign, pad_id=0, **kwargs):
        self.runtime = runtime_binding()
        verify_plan(plan, *pools)
        args, model = kwargs["args"], kwargs["model"]
        if (not args.use_cpu or args.world_size != 1 or plan.shape.world_size != 1
                or torch.cuda.is_initialized() or args.bf16 or args.fp16
                or args.deepspeed or args.fsdp or args.dataloader_num_workers != 0
                or args.remove_unused_columns or args.ignore_data_skip
                or args.load_best_model_at_end or args.save_only_model
                or args.push_to_hub or args.report_to or args.torch_compile
                or str(args.eval_strategy) not in ("no", "IntervalStrategy.NO")):
            raise PlanError("unsupported_cpu_prototype_configuration")
        if (args.max_steps != plan.steps or args.gradient_accumulation_steps != plan.shape.accumulation
                or args.per_device_train_batch_size != plan.shape.pairs_per_rank):
            raise PlanError("trainer_plan_shape_mismatch")
        if (plan.encoder.max_len > 64 or sum(len(b.rows) for b in plan.batches) > 128
                or sum(p.numel() for p in model.parameters()) > 4096
                or any(p.device.type != "cpu" for p in model.parameters())
                or any(not e.card_id.startswith("synthetic:") for b in plan.batches for r in b.rows for e in (r.a, r.b))):
            raise PlanError("synthetic_cpu_scope_exceeded")
        if any(k in kwargs for k in ("train_dataset", "eval_dataset", "data_collator", "compute_loss_func", "optimizers")):
            raise PlanError("unsupported_custom_data_or_loss")
        self.plan, self.encoding_provider, self.true_sign, self.pad_id = plan, encoding_provider, true_sign, pad_id
        self.receipts = []
        self.resume_checked = False
        self._used = False
        super().__init__(train_dataset=_Rows(plan), **kwargs)
        # compute_loss is a per-pair mean; Trainer must divide by accumulation.
        self.model_accepts_loss_kwargs = False
        self.contract_sha256 = digest_records([self._current_contract()])

    def _current_contract(self):
        return {
            "plan_sha256": self.plan.sha256, "pad_id": self.pad_id, "runtime": self.runtime,
            "model_schema": [(k, list(v.shape), str(v.dtype)) for k, v in self.model.state_dict().items()],
            "model_code_sha256": hashlib.sha256(inspect.getsource(type(self.model)).encode()).hexdigest(),
            "model_config": self.model.cpu_validation_config,
            "adapter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "args": {k: v for k, v in self.args.to_dict().items() if k not in ("output_dir", "logging_dir", "run_name")},
        }

    def _collate_locations(self, locations):
        indexes = {i for i, _ in locations}
        if len(indexes) != 1 or tuple(j for _, j in locations) != tuple(range(self.plan.shape.pairs_per_rank)):
            raise PlanError("reshuffled_or_partial_loader_batch")
        index = locations[0][0]
        packed = pack_batch(self.plan, self.plan.batches[index], self.encoding_provider, self.true_sign, pad_id=self.pad_id)
        return {"input_ids": torch.tensor(packed.input_ids, dtype=torch.long),
                "attention_mask": torch.tensor(packed.attention_mask, dtype=torch.long),
                "target_sign": torch.tensor(packed.signs, dtype=torch.long), "_gl_batch_index": index}

    def get_train_dataloader(self):
        # No accelerator.prepare(data_loader): plan is already fully assigned.
        # This class forbids distributed use until its separate validation exists.
        generator = torch.Generator(device="cpu").manual_seed(self.plan.seed)
        return DataLoader(self.train_dataset, batch_sampler=_FixedBatches(self.plan),
                          collate_fn=self._collate_locations, num_workers=0,
                          pin_memory=False, generator=generator)

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        if set(inputs) != {"input_ids", "attention_mask", "target_sign", "_gl_batch_index"}:
            raise PlanError("consumer_columns_changed")
        index = inputs["_gl_batch_index"]
        if type(index) is not int or index != len(self.receipts) or not 0 <= index < len(self.plan.batches):
            raise PlanError("actual_consumer_order_mismatch")
        batch = self.plan.batches[index]
        if self.state.global_step != batch.optimizer_step:
            raise PlanError("consumer_optimizer_boundary_mismatch")
        tensors = [inputs[k] for k in ("input_ids", "attention_mask", "target_sign")]
        if any(t.device.type != "cpu" or t.dtype != torch.long for t in tensors):
            raise PlanError("consumer_tensor_type_mismatch")
        ids, mask, signs = tensors
        packed = PackedBatch(tuple(tuple(x) for x in ids.tolist()), tuple(tuple(x) for x in mask.tolist()), tuple(signs.tolist()))
        event = observe_batch(self.plan, batch, packed, self.true_sign, pad_id=self.pad_id)
        scores = model(input_ids=ids, attention_mask=mask)["logits"]
        n = len(batch.rows)
        if scores.shape != (2 * n,) or not torch.isfinite(scores).all():
            raise PlanError("invalid_synthetic_scores")
        margins = scores[:n] - scores[n:]
        loss = torch.nn.functional.softplus(-signs * margins).mean()
        if not torch.isfinite(loss):
            raise PlanError("nonfinite_synthetic_loss")
        self.receipts.append(event)
        return (loss, {"logits": margins}) if return_outputs else loss

    def _save_checkpoint(self, model, trial):
        verify_prefix(self.plan, self.receipts, completed_steps=self.state.global_step)
        super()._save_checkpoint(model, trial)
        folder = Path(self._get_output_dir(trial)) / f"checkpoint-{self.state.global_step}"
        hashes = self._checkpoint_hashes(folder)
        receipt = {"contract_sha256": self.contract_sha256, "completed_steps": self.state.global_step,
                   "files": hashes, "consumption": [asdict(r) for r in self.receipts]}
        # File writes are small synthetic run artifacts, not source modifications.
        with (folder / "gl_cpu_resume_receipt.json").open("x", encoding="utf-8") as f:
            json.dump(receipt, f, sort_keys=True, allow_nan=False)
            f.write("\n")

    @staticmethod
    def _checkpoint_hashes(folder):
        if folder.is_symlink() or not folder.is_dir():
            raise PlanError("invalid_checkpoint_directory")
        hashes = {}
        for name in CHECKPOINT_FILES:
            p = folder / name
            if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size < 8 * 1024 * 1024:
                raise PlanError("incomplete_or_oversized_cpu_checkpoint")
            hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        return hashes

    def _check_resume(self, checkpoint):
        folder = Path(checkpoint)
        p = folder / "gl_cpu_resume_receipt.json"
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 1024 * 1024:
            raise PlanError("missing_resume_receipt")
        data = json.loads(p.read_text(encoding="utf-8"))
        if data["contract_sha256"] != self.contract_sha256:
            raise PlanError("resume_training_contract_drift")
        if data["files"] != self._checkpoint_hashes(folder):
            raise PlanError("checkpoint_file_hash_mismatch")
        receipts = [_decode_receipt(x) for x in data["consumption"]]
        step = data["completed_steps"]
        verify_prefix(self.plan, receipts, completed_steps=step)
        state = json.loads((folder / "trainer_state.json").read_text())
        if state["global_step"] != step or not 0 < step < self.plan.steps:
            raise PlanError("invalid_resume_training_step")
        self.receipts = receipts
        self.resume_checked = True

    def train(self, *args, resume_from_checkpoint=None, **kwargs):
        if self._used or args or kwargs:
            raise PlanError("prototype_one_train_call_only")
        if digest_records([self._current_contract()]) != self.contract_sha256 or self.model_accepts_loss_kwargs:
            raise PlanError("configuration_changed_after_construction")
        if resume_from_checkpoint is not None:
            if not isinstance(resume_from_checkpoint, (str, Path)):
                raise PlanError("explicit_checkpoint_path_required")
            self._check_resume(resume_from_checkpoint)
        self._used = True
        result = super().train(resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint is not None else None)
        verify_prefix(self.plan, self.receipts, completed_steps=self.state.global_step)
        if torch.cuda.is_initialized():
            raise PlanError("unexpected_cuda_context")
        return result
