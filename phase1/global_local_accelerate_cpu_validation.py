"""Bounded exact-Accelerate validation for planned partial updates.

Runs only synthetic integer inputs and a two-parameter CPU model.  The source
remainders 48 and 81 match the historical G/L pools, but no real record, model
weight, GPU, API, or outcome is read.  This validates Accelerate+DDP only; it
does not claim that ZeRO-3, bf16, or a research fit is ready.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket

import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from accelerate import Accelerator

from phase1.global_local_accelerate_update_adapter import (
    backward_local_pair_mean,
    finish_non_deepspeed_update,
    planned_microbatch_context,
    rank_update_batches,
    runtime_binding,
    set_optimizer_learning_rate,
    update_learning_rate,
)
from phase1.global_local_batch_adapter import observe_batch, pack_batch
from phase1.global_local_partial_ddp_cpu_validation import (
    Tiny,
    fixture,
    verify_consumption_prefix,
)
from phase1.verify_global_local_execution_trace import BatchReceipt


PEAK_LR_DECIMAL = "0.00001"
PEAK_LR = float(PEAK_LR_DECIMAL)


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _reference(world, arm):
    value, pools, encoded, truth = fixture(world, arm)
    global_keys = {row.key for row in pools[0]}

    def target(key):
        if arm == "Ghash_to_L" and key in global_keys:
            raise ValueError("independent_reference_read_true_global_label")
        return truth[key]

    model = Tiny(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=0.0)
    gradient_norms = []
    for step in range(value.steps):
        optimizer.zero_grad(set_to_none=True)
        batches = [batch for batch in value.batches if batch.optimizer_step == step]
        rows = tuple(row for batch in batches for row in batch.rows)
        holder = type("CombinedBatch", (), {"rows": rows})()
        packed = pack_batch(value, holder, lambda context, card: encoded[(context, card)], target, pad_id=0)
        ids = torch.tensor(packed.input_ids)
        mask = torch.tensor(packed.attention_mask)
        signs = torch.tensor(packed.signs, dtype=torch.float64)
        scores = model(ids, mask)
        count = len(rows)
        loss = torch.nn.functional.softplus(-signs * (scores[:count] - scores[count:])).mean()
        lr = (
            PEAK_LR
            * batches[0].lr_scale_numerator
            / batches[0].lr_scale_denominator
        )
        for group in optimizer.param_groups:
            group["lr"] = lr
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        gradient_norms.append(float(norm))
        optimizer.step()
    return model.weight.detach(), gradient_norms


def _worker(rank, world, arm, output, master_port):
    os.environ.update({
        "RANK": str(rank),
        "LOCAL_RANK": str(rank),
        "WORLD_SIZE": str(world),
        "MASTER_ADDR": "127.0.0.1",
        "MASTER_PORT": str(master_port),
        "GLOO_SOCKET_IFNAME": "lo",
        "ACCELERATE_USE_CPU": "true",
        "OMP_NUM_THREADS": "1",
    })
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("cuda_visibility_mismatch")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    value, pools, encoded, truth = fixture(world, arm)
    global_keys = {row.key for row in pools[0]}
    target_reads = []

    def target(key):
        if arm == "Ghash_to_L" and key in global_keys:
            raise ValueError("true_global_label_access_forbidden")
        target_reads.append(key)
        return truth[key]

    accelerator = Accelerator(
        cpu=True,
        mixed_precision="no",
        gradient_accumulation_steps=value.shape.accumulation,
    )
    if (
        accelerator.process_index != rank
        or accelerator.num_processes != world
        or str(accelerator.distributed_type).upper().endswith("DEEPSPEED")
    ):
        raise ValueError("unexpected_accelerate_process_topology")
    model = Tiny(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=0.0)
    model, optimizer = accelerator.prepare(model, optimizer)
    receipts = []
    sync_sequences = []
    update_records = []
    for step in range(value.steps):
        batches = rank_update_batches(value, rank, step)
        lr = update_learning_rate(value, batches, PEAK_LR_DECIMAL)
        set_optimizer_learning_rate(optimizer, lr)
        optimizer.zero_grad(set_to_none=True)
        sync_sequence = []
        scaled_loss_sum = 0.0
        for index, batch in enumerate(batches):
            synchronize = index == len(batches) - 1
            packed = pack_batch(
                value, batch, lambda context, card: encoded[(context, card)], target, pad_id=0
            )
            receipt = observe_batch(value, batch, packed, target, pad_id=0)
            ids = torch.tensor(packed.input_ids)
            mask = torch.tensor(packed.attention_mask)
            signs = torch.tensor(packed.signs, dtype=torch.float64)
            with planned_microbatch_context(accelerator, model, synchronize=synchronize):
                scores = model(ids, mask)
                count = len(batch.rows)
                mean_loss = torch.nn.functional.softplus(
                    -signs * (scores[:count] - scores[count:])
                ).mean()
                scaled_loss_sum += backward_local_pair_mean(accelerator, mean_loss, batch)
            sync_sequence.append(bool(accelerator.sync_gradients))
            observed = accelerator.unwrap_model(model).observed[-1]
            if tuple(zip(observed[:count], observed[count:])) != receipt.encoded_digests:
                raise ValueError("model_boundary_encoding_mismatch")
            receipts.append(receipt)
        finish = finish_non_deepspeed_update(
            accelerator, model, optimizer, max_grad_norm=1.0
        )
        if finish["optimizer_step_skipped"]:
            raise ValueError("unexpected_optimizer_step_skip")
        sync_sequences.append(sync_sequence)
        update_records.append({
            "optimizer_step": step,
            "microsteps": len(batches),
            "local_pair_counts": [len(batch.rows) for batch in batches],
            "learning_rate": lr,
            "scaled_local_loss_sum": scaled_loss_sum,
            "preclip_gradient_norm": finish["preclip_gradient_norm"],
            "step_owner": finish["owner"],
        })
    if torch.cuda.is_initialized():
        raise ValueError("unexpected_cuda_context")
    weight = accelerator.unwrap_model(model).weight.detach().cpu()
    event_rows = [asdict(receipt) for receipt in receipts]
    gathered = [None] * world
    dist.all_gather_object(gathered, {
        "rank": rank,
        "weight": weight.tolist(),
        "receipts": event_rows,
        "sync_sequences": sync_sequences,
        "updates": update_records,
        "true_target_reads": len(target_reads),
    })
    if rank == 0:
        global_receipts = []
        for state in gathered:
            for event in state["receipts"]:
                global_receipts.append(BatchReceipt(
                    event["plan_sha256"],
                    event["optimizer_step"],
                    event["micro_step"],
                    event["rank"],
                    tuple(event["pair_keys"]),
                    tuple(tuple(pair) for pair in event["encoded_digests"]),
                    event["valid_tokens"],
                    event["padded_slots"],
                ))
        verify_consumption_prefix(value, global_receipts, value.steps)
        reference_weight, reference_norms = _reference(world, arm)
        for state in gathered:
            torch.testing.assert_close(
                torch.tensor(state["weight"], dtype=torch.float64),
                reference_weight,
                rtol=1e-12,
                atol=1e-12,
            )
        manifest = {
            "world": world,
            "arm": arm,
            "plan_sha256": value.sha256,
            "input_sha256": value.input_sha256,
            "optimizer_updates": value.steps,
            "all_rank_forward_calls": sum(len(state["receipts"]) for state in gathered),
            "reference_weight": reference_weight.tolist(),
            "reference_preclip_gradient_norms": reference_norms,
            "states": gathered,
            "matches_independent_full_update_reference": True,
        }
        path = Path(output) / "manifest.json"
        path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    accelerator.wait_for_everyone()
    dist.destroy_process_group()


def _free_loopback_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


def run(root: Path):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("bounded_cpu_environment_required")
    if not root.is_relative_to(Path("/tmp")) or root.exists():
        raise ValueError("new_tmp_output_required")
    root.mkdir(mode=0o700)
    binding = runtime_binding()
    trials = []
    for world in (2, 4):
        for arm in ("G_to_L", "Ghash_to_L"):
            output = root / f"w{world}-{arm}"
            output.mkdir(mode=0o700)
            mp.spawn(
                _worker,
                args=(world, arm, str(output), _free_loopback_port()),
                nprocs=world,
                join=True,
            )
            manifest_path = output / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["manifest_sha256"] = sha(manifest_path)
            trials.append(manifest)
            (root / "progress.json").write_text(json.dumps({
                "completed_distributed_trajectories": len(trials)
            }) + "\n")
    for world in (2, 4):
        true = next(row for row in trials if row["world"] == world and row["arm"] == "G_to_L")
        hashed = next(row for row in trials if row["world"] == world and row["arm"] == "Ghash_to_L")
        for left, right in zip(true["states"], hashed["states"]):
            left_receipts = [{k: v for k, v in row.items() if k != "plan_sha256"} for row in left["receipts"]]
            right_receipts = [{k: v for k, v in row.items() if k != "plan_sha256"} for row in right["receipts"]]
            if left_receipts != right_receipts or left["sync_sequences"] != right["sync_sequences"]:
                raise ValueError("G_and_Ghash_accelerate_input_trace_mismatch")
    report = {
        "status": "PASS_SYNTHETIC_ACCELERATE_DDP_PARTIAL_UPDATES_NOT_RESEARCH_FIT",
        "script_sha256": sha(__file__),
        "adapter_sha256": sha(Path(__file__).with_name("global_local_accelerate_update_adapter.py")),
        "runtime_binding": binding,
        "world_sizes": [2, 4],
        "arms": ["G_to_L", "Ghash_to_L"],
        "matching_real_terminal_remainders": {"G": 48, "L": 81},
        "distributed_trajectories": len(trials),
        "global_optimizer_updates": sum(row["optimizer_updates"] for row in trials),
        "all_rank_forward_calls": sum(row["all_rank_forward_calls"] for row in trials),
        "trials": trials,
        "partial_loss_normalization_matches_full_update_reference": True,
        "G_and_Ghash_input_and_boundary_traces_identical": True,
        "trainer_default_loop_used": False,
        "real_HF_reward_model_DeepSpeed_Zero3_bf16_verified": False,
        "research_model_fits": 0,
        "real_data_opened": False,
        "gpu_context_created": False,
        "api_calls": 0,
    }
    (root / "summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = run(args.output)
    print(json.dumps({
        "status": value["status"],
        "distributed_trajectories": value["distributed_trajectories"],
        "global_optimizer_updates": value["global_optimizer_updates"],
        "all_rank_forward_calls": value["all_rank_forward_calls"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
