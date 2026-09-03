"""Bounded Gloo validation of variable terminal optimizer updates.

Uses synthetic integer tokens and a two-parameter CPU model only.  The source
counts are 128+48 G pairs and 128+81 L pairs, so the terminal remainders match
the real historical pools while no real data, model weights, GPU, or API is
used.  This is not Transformers Trainer, DeepSpeed, bf16, or an effect fit.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from phase1.global_local_batch_adapter import encoding_digest, observe_batch, pack_batch
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair
from phase1.global_local_token_budget_plan import build_plan
from phase1.verify_global_local_execution_trace import BatchReceipt
from phase1.verify_global_local_token_budget_plan import verify_plan


G_COUNT = 176  # 128 + the real G remainder 48
L_COUNT = 209  # 128 + the real L remainder 81
PEAK_LR = 0.02  # synthetic engineering check only, not the research LR


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(world, arm):
    if world not in (2, 4) or arm not in ("G_to_L", "Ghash_to_L"):
        raise ValueError("unsupported_synthetic_case")
    h = lambda value: hashlib.sha256(value.encode()).hexdigest()
    context = h("synthetic:partial-ddp-context")
    encoded = {}
    truth = {}
    pools = []
    for source, count in (("G", G_COUNT), ("L", L_COUNT)):
        rows = []
        for index in range(count):
            endpoints = []
            for side, length in enumerate((3, 5)):
                card_id = f"synthetic:partial-ddp:{source}:{index}:{side}"
                ids = tuple(
                    1 + ((index * 7 + side * 3 + position + (source == "L")) % 19)
                    for position in range(length)
                )
                encoded[(context, card_id)] = ids
                endpoints.append(Endpoint(card_id, length, encoding_digest(ids)))
            pair = Pair.canonical(source, *endpoints, context)
            truth[pair.key] = 1 if index % 2 else -1
            rows.append(pair)
        pools.append(tuple(rows))
    shape = BatchShape(world, 8, 8 if world == 2 else 4)
    value = build_plan(
        arm, *pools, seed=6, shape=shape,
        encoder=EncoderBinding(h("synthetic:integer-encoder"), h("synthetic:partial-ddp-serializer"), 8),
        protocol_sha256=h("synthetic:partial-ddp-not-research-protocol"),
    )
    verify_plan(value, *pools)
    if value.steps != 4 or [segment.pair_visits for segment in value.segments] != [G_COUNT, L_COUNT]:
        raise ValueError("unexpected_synthetic_plan_shape")
    return value, pools, encoded, truth


class Tiny(torch.nn.Module):
    def __init__(self, stochastic):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([0.17, -0.09], dtype=torch.float64))
        self.stochastic = stochastic
        self.dropout = torch.nn.Dropout(0.25 if stochastic else 0.0)
        self.observed = []

    def forward(self, ids, mask):
        self.observed.append(tuple(
            encoding_digest(values[:int(one_mask.sum())].tolist())
            for values, one_mask in zip(ids, mask)
        ))
        values = ids.double() * mask
        features = torch.stack((values.sum(1) / 50, values.square().sum(1) / 500), 1)
        if self.stochastic:
            features *= 0.8 + 0.2 * random.random()
            features *= torch.from_numpy(np.random.uniform(0.9, 1.1, size=tuple(features.shape)))
        return self.dropout(features) @ self.weight


def rng_state():
    numpy_state = np.random.get_state()
    return {
        "python": random.getstate(),
        "torch": torch.get_rng_state(),
        "numpy": (
            numpy_state[0], numpy_state[1].tolist(), numpy_state[2],
            numpy_state[3], numpy_state[4],
        ),
    }


def restore_rng(value):
    random.setstate(value["python"])
    torch.set_rng_state(value["torch"])
    numpy_state = value["numpy"]
    np.random.set_state((
        numpy_state[0], np.asarray(numpy_state[1], dtype=np.uint32),
        numpy_state[2], numpy_state[3], numpy_state[4],
    ))


def binding(value, rank, stochastic):
    return {
        "plan_sha256": value.sha256,
        "input_sha256": value.input_sha256,
        "world": value.shape.world_size,
        "rank": rank,
        "stochastic": stochastic,
        "script_sha256": sha(__file__),
        "torch": str(torch.__version__),
        "optimizer": "AdamW-weight-decay-zero",
        "synthetic_peak_lr": PEAK_LR,
        "lr_rule": "token-progress-from-plan",
        "seed": 6,
        "rank_rng_seed": 600 + rank,
    }


def atomic_torch_save(value, path):
    temporary = path.with_suffix(".partial")
    with temporary.open("xb") as handle:
        torch.save(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def verify_consumption_prefix(value, receipts, completed_steps):
    expected = {
        (batch.optimizer_step, batch.micro_step, batch.rank): batch
        for batch in value.batches if batch.optimizer_step < completed_steps
    }
    if len(receipts) != len(expected):
        raise ValueError("missing_or_extra_receipts")
    seen = set()
    last_per_rank = {}
    for receipt in receipts:
        address = (receipt.optimizer_step, receipt.micro_step, receipt.rank)
        if address not in expected or address in seen:
            raise ValueError("unknown_or_duplicate_receipt")
        if address[:2] <= last_per_rank.get(receipt.rank, (-1, -1)):
            raise ValueError("per_rank_order_mismatch")
        batch = expected[address]
        if (receipt.plan_sha256 != value.sha256
                or receipt.pair_keys != tuple(row.key for row in batch.rows)
                or receipt.encoded_digests != tuple(
                    (row.a.encoded_sha256, row.b.encoded_sha256) for row in batch.rows
                )
                or receipt.valid_tokens != batch.valid_tokens
                or receipt.padded_slots != batch.padded_slots):
            raise ValueError("consumption_receipt_mismatch")
        seen.add(address)
        last_per_rank[receipt.rank] = address[:2]
    if seen != set(expected):
        raise ValueError("incomplete_consumption")


def worker(rank, world, arm, stochastic, output, resume, end_step, rendezvous):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("cuda_visibility_mismatch")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    dist.init_process_group(
        "gloo", init_method="file://" + rendezvous, rank=rank,
        world_size=world, timeout=timedelta(seconds=60),
    )
    value, pools, encoded, truth = fixture(world, arm)
    global_keys = {row.key for row in pools[0]}
    target_reads = []

    def target(key):
        if arm == "Ghash_to_L" and key in global_keys:
            raise ValueError("true_global_label_access_forbidden")
        target_reads.append(key)
        return truth[key]

    model = Tiny(stochastic)
    ddp = torch.nn.parallel.DistributedDataParallel(model)
    optimizer = torch.optim.AdamW(ddp.parameters(), lr=PEAK_LR, weight_decay=0.0)
    random.seed(600 + rank)
    np.random.seed(600 + rank)
    torch.manual_seed(600 + rank)
    events = []
    start_step = 0
    if resume is not None:
        checkpoint = Path(resume) / f"rank-{rank}.pt"
        manifest = json.loads((Path(resume) / "manifest.json").read_text())
        if sha(checkpoint) != manifest["rank_files"][checkpoint.name]:
            raise ValueError("checkpoint_hash_mismatch")
        previous = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if previous["binding"] != binding(value, rank, stochastic) or previous["completed_steps"] != 2:
            raise ValueError("resume_binding_mismatch")
        model.load_state_dict(previous["model"])
        optimizer.load_state_dict(previous["optimizer"])
        restore_rng(previous["rng"])
        events = previous["events"]
        start_step = previous["completed_steps"]
    new_events = []
    output = Path(output)
    for step in range(start_step, end_step):
        optimizer.zero_grad(set_to_none=True)
        rank_batches = [
            batch for batch in value.batches
            if batch.optimizer_step == step and batch.rank == rank
        ]
        maximum_micro = max(batch.micro_step for batch in rank_batches)
        update_lr = PEAK_LR * (
            rank_batches[0].lr_scale_numerator / rank_batches[0].lr_scale_denominator
        )
        for group in optimizer.param_groups:
            group["lr"] = update_lr
        for batch in rank_batches:
            packed = pack_batch(value, batch, lambda context, card: encoded[(context, card)],
                                target, pad_id=0)
            receipt = observe_batch(value, batch, packed, target, pad_id=0)
            ids = torch.tensor(packed.input_ids)
            mask = torch.tensor(packed.attention_mask)
            synchronize = batch.micro_step == maximum_micro
            with nullcontext() if synchronize else ddp.no_sync():
                scores = ddp(ids, mask)
                count = len(batch.rows)
                signs = torch.tensor(packed.signs, dtype=torch.float64)
                mean_loss = torch.nn.functional.softplus(
                    -signs * (scores[:count] - scores[count:])
                ).mean()
                scale = batch.loss_mean_scale_numerator / batch.loss_mean_scale_denominator
                (mean_loss * scale).backward()
            observed = model.observed[-1]
            if tuple(zip(observed[:count], observed[count:])) != receipt.encoded_digests:
                raise ValueError("model_boundary_encoding_mismatch")
            event = asdict(receipt)
            event.update({
                "loss_mean_scale_numerator": batch.loss_mean_scale_numerator,
                "loss_mean_scale_denominator": batch.loss_mean_scale_denominator,
                "update_real_pairs": batch.update_real_pairs,
                "update_valid_tokens": batch.update_valid_tokens,
                "lr_scale_numerator": batch.lr_scale_numerator,
                "lr_scale_denominator": batch.lr_scale_denominator,
            })
            events.append(event)
            new_events.append(event)
        optimizer.step()
    if torch.cuda.is_initialized():
        raise ValueError("unexpected_cuda_context")
    state = {
        "binding": binding(value, rank, stochastic),
        "completed_steps": end_step,
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "rng": rng_state(),
        "events": events,
        "target_read_count_this_process": len(target_reads),
        "new_forward_calls": len(new_events),
    }
    atomic_torch_save(state, output / f"rank-{rank}.pt")
    gathered = [None] * world
    dist.all_gather_object(gathered, events)
    if rank == 0:
        receipts = []
        for rank_events in gathered:
            for event in rank_events:
                receipts.append(BatchReceipt(
                    event["plan_sha256"], event["optimizer_step"], event["micro_step"],
                    event["rank"], tuple(event["pair_keys"]),
                    tuple(tuple(pair) for pair in event["encoded_digests"]),
                    event["valid_tokens"], event["padded_slots"],
                ))
        verify_consumption_prefix(value, receipts, end_step)
        manifest = {
            "world": world,
            "arm": arm,
            "stochastic": stochastic,
            "completed_steps": end_step,
            "input_sha256": value.input_sha256,
            "plan_sha256": value.sha256,
            "rank_files": {
                f"rank-{one_rank}.pt": sha(output / f"rank-{one_rank}.pt")
                for one_rank in range(world)
            },
            "trace_verified": True,
            "process_resume": resume is not None,
            "optimizer_updates_global": end_step - start_step,
            "forward_calls_all_ranks": len(new_events) * world,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
    dist.barrier()
    dist.destroy_process_group()


def same_tree(left, right):
    if isinstance(left, torch.Tensor):
        return (isinstance(right, torch.Tensor) and left.dtype == right.dtype
                and left.shape == right.shape and torch.equal(left, right))
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_tree(left[key], right[key]) for key in left)
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(same_tree(a, b) for a, b in zip(left, right))
    return left == right


def states(root):
    manifest = json.loads((root / "manifest.json").read_text())
    expected = {f"rank-{rank}.pt" for rank in range(manifest["world"])}
    if manifest["world"] not in (2, 4) or set(manifest["rank_files"]) != expected:
        raise ValueError("rank_manifest_mismatch")
    for name, expected_sha in manifest["rank_files"].items():
        if sha(root / name) != expected_sha:
            raise ValueError("checkpoint_hash_mismatch")
    return [
        torch.load(root / f"rank-{rank}.pt", map_location="cpu", weights_only=True)
        for rank in range(manifest["world"])
    ]


def reference(world, arm):
    value, _, encoded, truth = fixture(world, arm)
    model = Tiny(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=0.0)
    for step in range(value.steps):
        optimizer.zero_grad(set_to_none=True)
        batches = [batch for batch in value.batches if batch.optimizer_step == step]
        rows = tuple(row for batch in batches for row in batch.rows)
        holder = type("CombinedBatch", (), {"rows": rows})()
        packed = pack_batch(value, holder, lambda context, card: encoded[(context, card)],
                            truth.__getitem__, pad_id=0)
        ids = torch.tensor(packed.input_ids)
        mask = torch.tensor(packed.attention_mask)
        scores = model(ids, mask)
        count = len(rows)
        signs = torch.tensor(packed.signs, dtype=torch.float64)
        loss = torch.nn.functional.softplus(
            -signs * (scores[:count] - scores[count:])
        ).mean()
        update_lr = PEAK_LR * (
            batches[0].lr_scale_numerator / batches[0].lr_scale_denominator
        )
        for group in optimizer.param_groups:
            group["lr"] = update_lr
        loss.backward()
        optimizer.step()
    return model.weight.detach()


def run(root):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or os.environ.get("GLOO_SOCKET_IFNAME") != "lo":
        raise ValueError("bounded_cpu_environment_required")
    if not root.is_relative_to(Path("/tmp")) or root.exists():
        raise ValueError("new_tmp_output_required")
    root.mkdir(mode=0o700)
    started = time.monotonic()
    trials = []
    reference_checks = []
    resume_cases = []

    def launch(world, arm, stochastic, tag, *, steps=4, resume=None):
        path = root / f"w{world}-{arm}-{tag}"
        path.mkdir(mode=0o700)
        rendezvous = str(path / "gloo-rendezvous")
        mp.spawn(
            worker,
            args=(world, arm, stochastic, str(path),
                  None if resume is None else str(resume), steps, rendezvous),
            nprocs=world,
            join=True,
        )
        manifest = json.loads((path / "manifest.json").read_text())
        trials.append(manifest)
        (root / "progress.json").write_text(json.dumps({
            "completed_distributed_trajectories": len(trials)
        }))
        return path

    for world in (2, 4):
        for arm in ("G_to_L", "Ghash_to_L"):
            deterministic = launch(world, arm, False, "deterministic")
            expected = reference(world, arm)
            for state in states(deterministic):
                torch.testing.assert_close(
                    state["model"]["weight"], expected, rtol=1e-12, atol=1e-12
                )
            reference_checks.append({
                "world": world,
                "arm": arm,
                "matches_full_update_reference": True,
                "G_terminal_pairs": 48,
                "L_terminal_pairs": 81,
            })
            full = launch(world, arm, True, "stochastic-full")
            prefix = launch(world, arm, True, "prefix", steps=2)
            resumed = launch(world, arm, True, "fresh-process-resume", resume=prefix)
            full_states = states(full)
            resumed_states = states(resumed)
            for left, right in zip(full_states, resumed_states):
                for key in ("binding", "completed_steps", "model", "optimizer", "rng", "events"):
                    if not same_tree(left[key], right[key]):
                        raise ValueError("resume_state_mismatch:" + key)
            for state in full_states[1:]:
                for key in ("model", "optimizer"):
                    if not same_tree(full_states[0][key], state[key]):
                        raise ValueError("rank_parameter_state_mismatch")
            resume_cases.append({
                "world": world,
                "arm": arm,
                "cut_after_G_phase_step": 2,
                "verified_ranks": world,
                "complete_state_bitwise_equal": True,
                "new_process_group": True,
            })
        true_states = states(root / f"w{world}-G_to_L-stochastic-full")
        hash_states = states(root / f"w{world}-Ghash_to_L-stochastic-full")
        for true_state, hash_state in zip(true_states, hash_states):
            for left, right in zip(true_state["events"], hash_state["events"]):
                ignored = {"plan_sha256"}
                if ({key: value for key, value in left.items() if key not in ignored}
                        != {key: value for key, value in right.items() if key not in ignored}):
                    raise ValueError("label_control_input_trace_mismatch")
    report = {
        "status": "PASS_SYNTHETIC_PARTIAL_DDP_GLOO_NOT_RESEARCH_FIT",
        "script_sha256": sha(__file__),
        "torch": torch.__version__,
        "seed": 6,
        "world_sizes": [2, 4],
        "synthetic_source_counts": {"G": G_COUNT, "L": L_COUNT},
        "matching_real_terminal_remainders": {"G": 48, "L": 81},
        "reference_checks": reference_checks,
        "resume_cases": resume_cases,
        "trials": trials,
        "distributed_trajectories": len(trials),
        "global_optimizer_updates": sum(row["optimizer_updates_global"] for row in trials),
        "all_rank_forward_calls": sum(row["forward_calls_all_ranks"] for row in trials),
        "G_and_Ghash_input_trace_identical": True,
        "partial_loss_normalization_matches_full_update_reference": True,
        "research_model_fits": 0,
        "real_data_opened": False,
        "gpu_context_created": False,
        "api_calls": 0,
        "loopback_gloo_communications": True,
        "real_HF_Trainer_DeepSpeed_bf16_verified": False,
        "power_failure_verified": False,
        "wall_seconds_not_throughput_benchmark": time.monotonic() - started,
    }
    (root / "summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        key: report[key] for key in (
            "status", "distributed_trajectories", "global_optimizer_updates",
            "all_rank_forward_calls",
        )
    }, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    run(parser.parse_args().output_root.resolve())

