"""Actual Trainer consumption/checkpoint tests using a two-parameter CPU toy.

No pretrained model, real data, GPU, API, or research fit. Does perform and count
synthetic optimizer updates. Tiny checkpoints are kept in a NEW output directory.
The synthetic LR/optimizer below are test settings, not a frozen-v2 amendment.
"""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from pathlib import Path
import random
import shutil
import socket

import numpy as np
import torch
from transformers import TrainerCallback, TrainingArguments, set_seed
from safetensors.torch import load_file

from phase1.global_local_execution_plan import PlanError, digest_records
from phase1.global_local_batch_adapter import PackedBatch, encoding_digest, synthetic_fixture
from phase1.global_local_trainer_adapter import CPUPlannedTrainer, CHECKPOINT_FILES, runtime_binding
from phase1.verify_global_local_execution_trace import verify_prefix


class ToyScorer(torch.nn.Module):
    """Two scalar parameters, random perturbations exercise all three RNGs."""
    def __init__(self, stochastic=False):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([0.17, -0.09], dtype=torch.float64))
        self.cpu_validation_config = {"stochastic": stochastic, "dropout": 0.25 if stochastic else 0.0}
        self.dropout = torch.nn.Dropout(self.cpu_validation_config["dropout"])
        self.observed = []

    def forward(self, input_ids, attention_mask):
        self.observed.append((input_ids.detach().clone(), attention_mask.detach().clone()))
        x = input_ids.to(torch.float64) * attention_mask
        features = torch.stack((x.sum(1) / 50, x.square().sum(1) / 500), 1)
        if self.cpu_validation_config["stochastic"]:
            features = features * (0.8 + 0.2 * random.random())
            features = features * torch.from_numpy(np.random.uniform(0.9, 1.1, size=tuple(features.shape)))
        return {"logits": self.dropout(features) @ self.weight}


class StopAt(TrainerCallback):
    def __init__(self, step):
        self.step = step

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step == self.step:
            control.should_training_stop = True
            control.should_save = True
        return control


def args_for(root, plan):
    return TrainingArguments(output_dir=str(root), use_cpu=True, report_to=[],
        per_device_train_batch_size=plan.shape.pairs_per_rank,
        gradient_accumulation_steps=plan.shape.accumulation, max_steps=plan.steps,
        learning_rate=0.02, weight_decay=0.0, max_grad_norm=0.0,
        lr_scheduler_type="linear", warmup_steps=0, seed=plan.seed, data_seed=plan.seed,
        optim="adamw_torch", save_strategy="steps", save_steps=1, save_only_model=False,
        eval_strategy="no", logging_strategy="no", disable_tqdm=True,
        remove_unused_columns=False, dataloader_num_workers=0, dataloader_pin_memory=False,
        load_best_model_at_end=False, ignore_data_skip=False)


def trainer_for(root, arm="G_to_L", seed=6, stochastic=False, cut=None, accumulation=2, pairs_per_rank=2, learning_rate=0.02):
    plan, pools, encoded, truth = synthetic_fixture(arm, seed, accumulation=accumulation, pairs_per_rank=pairs_per_rank)
    set_seed(seed)
    model = ToyScorer(stochastic)
    forbidden = {r.key for r in pools[0]} if arm == "Ghash_to_L" else set()
    reads = []
    def target(key):
        if key in forbidden:
            raise AssertionError("hash-global read true global label")
        reads.append(key)
        return truth[key]
    args = args_for(root, plan)
    args.learning_rate = learning_rate
    trainer = CPUPlannedTrainer(model=model, args=args, plan=plan, pools=pools,
        encoding_provider=lambda context, name: encoded[(context, name)], true_sign=target,
        callbacks=[] if cut is None else [StopAt(cut)])
    return trainer


def tree_equal(a, b):
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and np.array_equal(a, b)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(tree_equal(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(tree_equal(x, y) for x, y in zip(a, b))
    return a == b


def checkpoint_state(root, step):
    p = Path(root) / f"checkpoint-{step}"
    # Only our freshly created, integrity-checked toy files; never third-party pickle.
    from transformers.trainer import safe_globals
    with safe_globals():
        rng = torch.load(p / "rng_state.pth", map_location="cpu", weights_only=True)
    return {"model": load_file(p / "model.safetensors"),
            "optimizer": torch.load(p / "optimizer.pt", map_location="cpu", weights_only=True),
            "scheduler": torch.load(p / "scheduler.pt", map_location="cpu", weights_only=True), "rng": rng}


def check_forward_observations(trainer, offset=0):
    events = trainer.receipts[offset:]
    assert len(trainer.model.observed) == len(events)
    for (ids, mask), receipt in zip(trainer.model.observed, events):
        count = len(receipt.pair_keys)
        actual = [encoding_digest(row[:int(m.sum())].tolist()) for row, m in zip(ids, mask)]
        assert tuple(zip(actual[:count], actual[count:])) == receipt.encoded_digests
        assert int(mask.sum()) == receipt.valid_tokens and ids.numel() == receipt.padded_slots
    verify_prefix(trainer.plan, trainer.receipts, completed_steps=trainer.state.global_step)


def run_validation(root):
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert not torch.cuda.is_initialized()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    root = root.resolve()
    root.mkdir(mode=0o700, exist_ok=False)
    rows, failures = [], []
    calls = updates = consumed = 0
    def execute(trainer, name, resume=None):
        nonlocal calls, updates, consumed
        before = len(trainer.receipts)
        trainer.train(resume_from_checkpoint=resume)
        actual_start = before
        if resume is not None:
            old = json.loads((Path(resume) / "gl_cpu_resume_receipt.json").read_text())
            actual_start = len(old["consumption"])
        check_forward_observations(trainer, actual_start)
        n = len(trainer.receipts) - actual_start
        calls += 1
        updates += n // trainer.plan.shape.accumulation
        consumed += n
        rows.append({"case": name, "seed": trainer.plan.seed, "arm": trainer.plan.arm,
                     "new_microbatches_observed": n, "final_step": trainer.state.global_step,
                     "new_optimizer_updates": n // trainer.plan.shape.accumulation,
                     "plan_sha256": trainer.plan.sha256, "resume": resume is not None,
                     "consumption_verified": True})

    # Seeded phase consumption and real/hash input identity at the model boundary.
    for seed in (6, 7, 8):
        pair = []
        for arm in ("G_to_L", "Ghash_to_L"):
            name = f"consume-{arm}-{seed}"
            trainer = trainer_for(root / name, arm, seed)
            execute(trainer, name)
            pair.append(trainer)
        assert pair[0].plan.input_sha256 == pair[1].plan.input_sha256
        assert all(torch.equal(a, b) for x, y in zip(pair[0].model.observed, pair[1].model.observed) for a, b in zip(x, y))
    for arm in ("L1", "Lbudget", "Gbudget"):
        execute(trainer_for(root / arm, arm), arm)

    # Exercise actual stateful optimizer + Python/NumPy/torch dropout RNG restore.
    resume_cases = []
    for arm in ("G_to_L", "Ghash_to_L"):
        full_root = root / f"resume-full-{arm}"
        full = trainer_for(full_root, arm, stochastic=True)
        execute(full, f"resume-full-{arm}")
        expected = checkpoint_state(full_root, full.plan.steps)
        for cut in (1, 2, 3):
            first_root = root / f"interrupted-{arm}-{cut}"
            first = trainer_for(first_root, arm, stochastic=True, cut=cut)
            execute(first, f"interrupted-{arm}-{cut}")
            assert first.state.global_step == cut
            checkpoint = first_root / f"checkpoint-{cut}"
            second_root = root / f"resumed-{arm}-{cut}"
            second = trainer_for(second_root, arm, stochastic=True)
            execute(second, f"resumed-{arm}-{cut}", resume=checkpoint)
            observed = checkpoint_state(second_root, second.plan.steps)
            comparisons = {k: tree_equal(expected[k], observed[k]) for k in expected}
            assert all(comparisons.values()), comparisons
            assert tuple(full.receipts) == tuple(second.receipts)
            joined = first.model.observed + second.model.observed
            assert len(joined) == len(full.model.observed)
            assert all(torch.equal(a, b) for x, y in zip(joined, full.model.observed) for a, b in zip(x, y))
            resume_cases.append({"arm": arm, "seed": 6, "cut_step": cut,
                                 "all_state_bitwise_equal": comparisons, "forward_inputs_equal": True})

    # Independent full-effective-batch updates versus Trainer microbatch means.
    grad = trainer_for(root / "gradient-accumulation", accumulation=2, pairs_per_rank=2)
    execute(grad, "gradient-accumulation")
    reference = ToyScorer(False)
    optimizer = torch.optim.AdamW(reference.parameters(), lr=0.02, weight_decay=0, eps=1e-8)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda s: max(0.0, 1 - s / grad.plan.steps))
    plan, pools, encoded, truth = synthetic_fixture()
    from phase1.global_local_execution_plan import targets
    for step in range(plan.steps):
        raw = [r for b in plan.batches if b.optimizer_step == step for r in b.rows]
        ids = [encoded[(r.context_sha256, getattr(r, side).card_id)] for side in ("a", "b") for r in raw]
        width = max(map(len, ids))
        tensors = torch.tensor([x + (0,) * (width-len(x)) for x in ids])
        masks = torch.tensor([[1]*len(x)+[0]*(width-len(x)) for x in ids])
        scores = reference(tensors, masks)["logits"]
        signs = torch.tensor([truth[r.key] for r in raw])
        loss = torch.nn.functional.softplus(-signs*(scores[:len(raw)]-scores[len(raw):])).mean()
        loss.backward(); optimizer.step(); scheduler.step(); optimizer.zero_grad()
    torch.testing.assert_close(grad.model.weight, reference.weight, rtol=1e-12, atol=1e-12)
    assert grad.lr_scheduler.state_dict()["last_epoch"] == scheduler.state_dict()["last_epoch"]

    # Tampering is rejected BEFORE Trainer can deserialize or consume anything.
    original = root / "interrupted-G_to_L-2/checkpoint-2"
    for name in CHECKPOINT_FILES:
        target = root / ("tamper-" + name.replace(".", "-"))
        shutil.copytree(original, target)
        with (target / name).open("ab") as f:
            f.write(b"synthetic-corruption")
        blocked = trainer_for(root / ("blocked-" + name.replace(".", "-")), stochastic=True)
        try:
            blocked.train(resume_from_checkpoint=target)
        except PlanError as exc:
            assert str(exc) == "checkpoint_file_hash_mismatch"
            assert not blocked.model.observed
            failures.append({"case": "corrupt_" + name, "expected_rejection": str(exc)})
        else:
            raise AssertionError("corrupt checkpoint accepted")
    for kind in ("arm", "seed", "stochastic", "accumulation", "learning_rate"):
        changes = {"arm": "Ghash_to_L"} if kind == "arm" else {"seed": 7} if kind == "seed" else {}
        blocked = trainer_for(root / ("drift-" + kind), stochastic=kind != "stochastic", **changes)
        if kind == "accumulation":
            blocked = trainer_for(root / "drift-accumulation-shape", stochastic=True, accumulation=1, pairs_per_rank=4)
        if kind == "learning_rate":
            blocked = trainer_for(root / "drift-learning-rate-config", stochastic=True, learning_rate=0.01)
        try:
            blocked.train(resume_from_checkpoint=original)
        except PlanError as exc:
            assert str(exc) == "resume_training_contract_drift"
            assert not blocked.model.observed
            failures.append({"case": "drift_" + kind, "expected_rejection": str(exc)})
        else:
            raise AssertionError("changed training contract accepted")
    mutated = trainer_for(root / "mutated-after-init", stochastic=True)
    mutated.args.learning_rate *= 2
    try:
        mutated.train(resume_from_checkpoint=original)
    except PlanError as exc:
        assert str(exc) == "configuration_changed_after_construction"
        assert not mutated.model.observed
        failures.append({"case": "post_constructor_mutation", "expected_rejection": str(exc)})
    else:
        raise AssertionError("post-construction mutation accepted")
    for name in ("optimizer.pt", "scheduler.pt", "rng_state.pth"):
        target = root / ("missing-" + name.replace(".", "-"))
        shutil.copytree(original, target)
        (target / name).rename(target / (name + ".withheld"))
        blocked = trainer_for(root / ("blocked-missing-" + name.replace(".", "-")), stochastic=True)
        try:
            blocked.train(resume_from_checkpoint=target)
        except PlanError as exc:
            assert str(exc) == "incomplete_or_oversized_cpu_checkpoint"
            assert not blocked.model.observed
            failures.append({"case": "missing_" + name, "expected_rejection": str(exc)})
        else:
            raise AssertionError("missing state accepted")
    # Positive sensitivity controls: corrupting each restored RNG stream must
    # change final weights. Same output would mean the RNG test was vacuous.
    correct = checkpoint_state(root / "resume-full-G_to_L", 4)
    for rng in ("python", "numpy", "torch"):
        name = "rng-sensitivity-" + rng
        broken = trainer_for(root / name, stochastic=True)
        normal_load = broken._load_rng_state
        def corrupt_rng(checkpoint, stream=rng, load=normal_load):
            load(checkpoint)
            if stream == "python": random.random()
            elif stream == "numpy": np.random.random()
            else: torch.rand(1)
        broken._load_rng_state = corrupt_rng
        execute(broken, name, resume=original)
        wrong = checkpoint_state(root / name, 4)
        assert not tree_equal(correct["model"], wrong["model"]), "RNG sensitivity canary was vacuous"
        failures.append({"case": name, "expected_parameter_divergence_detected": True})
    assert not torch.cuda.is_initialized()
    source = Path(__file__).resolve().parent
    files = ("global_local_execution_plan.py", "verify_global_local_execution_trace.py", "global_local_batch_adapter.py",
             "global_local_trainer_adapter.py", "global_local_trainer_cpu_validation.py")
    result = {"status": "SYNTHETIC_SINGLE_PROCESS_CPU_TRAINER_VALIDATION_PASS", "runtime": runtime_binding(),
              "source_sha256": {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in files},
              "synthetic_trainer_trajectories": calls, "synthetic_trainer_optimizer_updates": updates,
              "independent_reference_optimizer_updates": plan.steps,
              "actual_toy_forward_microbatches": consumed, "cases": rows, "resume_cases": resume_cases,
              "negative_controls": failures, "gradient_accumulation_matches_full_batch": True,
              "gradient_rtol_atol": 1e-12, "two_parameter_toy_only": True,
              "gpu_context_created": False, "gpu_jobs_submitted": 0, "research_model_fits": 0,
              "real_data_files_opened": 0, "pretrained_models_loaded": 0,
              "distributed_zero3_resume_validated": False, "frozen_v2_protocol_modified": False,
              "real_tokenizer_serialization_validated": False, "formal_training_authorized": False,
              "output_root": str(root)}
    with (root / "receipt.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    # No network after imports. Any unexpected socket use makes the test fail.
    def no_network(*args, **kwargs):
        raise RuntimeError("network prohibited in CPU unit validation")
    socket.socket = no_network
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = run_validation(args.output_root)
    finally:
        # Only small synthetic/framework logs; preserve failures, never data values.
        if args.output_root.is_dir():
            with (args.output_root / "validation.log").open("x", encoding="utf-8") as f:
                f.write(log.getvalue())
    print(json.dumps(result, sort_keys=True))
