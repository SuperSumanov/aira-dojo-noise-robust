"""Fresh-process save/load checks in exact Accelerate, synthetic CPU DDP only."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import timedelta
import hashlib
import inspect
import json
import os
from pathlib import Path
import random
import socket
import time

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from accelerate import Accelerator, checkpointing
from accelerate.utils import InitProcessGroupKwargs, load as accelerate_load

from phase1 import global_local_accelerate_checkpoint_gate as gate
from phase1.global_local_accelerate_update_adapter import (
    backward_local_pair_mean, finish_non_deepspeed_update, planned_microbatch_context,
    rank_update_batches, runtime_binding, set_optimizer_learning_rate, update_learning_rate,
)
from phase1.global_local_batch_adapter import observe_batch, pack_batch
from phase1.global_local_partial_ddp_cpu_validation import Tiny, fixture, verify_consumption_prefix
from phase1.verify_global_local_execution_trace import BatchReceipt


BASE_COMMIT = "dca429b85507cfcd96b256f65e2df2ac15be7b9a"
CHECKPOINT_METHOD_SHA = {
    "Accelerator.save_state": "5a5c62cbfb58ea7742c9b6a5612457fa35ac7eae1d344a34d1ce9bb19e0b41d9",
    "Accelerator.load_state": "05e3e0446edda6ff1b9d268061ee6819677fed5a1478920270dc4384c23e22fd",
    "save_accelerator_state": "ea2719148572cb8d85b42e8d05c82a16136de3c424801cf5b316280b32e64330",
    "load_accelerator_state": "9db725a776fe6cd97a9c638584eee3b26930e4d2f5cfd5b180c9ed3504c9173c",
    "load": "668382579fd20ad2a632a683f8e923d2481d9370dfe3fe9c1b8ea5905e535753",
}


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def encoded_state(value):
    """Lossless typed encoding, independent of torch/pickle serialization bytes."""
    if isinstance(value, torch.Tensor):
        tensor = value.detach().cpu().contiguous()
        return ["tensor", str(tensor.dtype), list(tensor.shape), tensor.numpy().tobytes().hex()]
    if isinstance(value, np.ndarray):
        return ["numpy", value.dtype.str, list(value.shape), value.tobytes().hex()]
    if isinstance(value, dict):
        pairs = [[encoded_state(k), encoded_state(v)] for k, v in value.items()]
        return ["dict", sorted(pairs, key=lambda pair: json.dumps(pair[0], sort_keys=True))]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [encoded_state(v) for v in value]]
    if type(value) is float:
        return ["float", value.hex()]
    if value is None or type(value) in (int, str, bool):
        return [type(value).__name__, value]
    raise ValueError("unsupported_state_type:" + type(value).__name__)


def state_digests(model, optimizer):
    values = {
        "model": dict(model.state_dict()), "optimizer": optimizer.state_dict(),
        "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
        "torch_rng": torch.get_rng_state(),
    }
    return {k: json_digest(encoded_state(v)) for k, v in values.items()}


def checkpoint_runtime():
    objects = (Accelerator.save_state, Accelerator.load_state, checkpointing.save_accelerator_state,
               checkpointing.load_accelerator_state, accelerate_load)
    actual = {name: hashlib.sha256(inspect.getsource(obj).encode()).hexdigest()
              for name, obj in zip(CHECKPOINT_METHOD_SHA, objects)}
    file_sha = gate.sha(inspect.getsourcefile(checkpointing))
    if (actual != CHECKPOINT_METHOD_SHA
            or file_sha != "1e934b935bfa308e902dbfa38961b4c4c4021dc62c7047d9fe43494469e73be6"):
        raise ValueError("checkpoint_runtime_drift")
    return {"methods": actual, "checkpointing_file": file_sha}


def _worker(rank, world, arm, output, end_step, resume, receipt_sha, runtime_sha, sources_sha, port):
    os.environ.update({"RANK": str(rank), "LOCAL_RANK": str(rank), "WORLD_SIZE": str(world),
                       "MASTER_ADDR": "127.0.0.1", "MASTER_PORT": str(port),
                       "ACCELERATE_USE_CPU": "true", "OMP_NUM_THREADS": "1"})
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or os.environ.get("GLOO_SOCKET_IFNAME") != "lo":
        raise ValueError("cpu_loopback_environment_required")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    checkpoint_runtime()
    plan, pools, encoded, truth = fixture(world, arm)
    binding = {"scope": "synthetic-two-parameter-cpu-only", "base_commit": BASE_COMMIT,
               "world": world, "arm": arm, "seed": 6, "plan_sha256": plan.sha256,
               "input_sha256": plan.input_sha256, "runtime_sha256": runtime_sha,
               "sources_sha256": sources_sha}
    global_keys = {row.key for row in pools[0]}
    reads = []

    def target(key):
        if arm == "Ghash_to_L" and key in global_keys:
            raise ValueError("true_global_label_access_forbidden")
        reads.append(key)
        return truth[key]

    accelerator = Accelerator(cpu=True, mixed_precision="no",
                              gradient_accumulation_steps=plan.shape.accumulation,
                              kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=60))])
    if (accelerator.process_index != rank or accelerator.num_processes != world
            or str(accelerator.distributed_type) != "DistributedType.MULTI_CPU"
            or accelerator.project_configuration.automatic_checkpoint_naming):
        raise ValueError("unexpected_accelerate_topology")
    model = Tiny(True)
    if sum(p.numel() for p in model.parameters()) != 2:
        raise ValueError("synthetic_model_guard")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
    model, optimizer = accelerator.prepare(model, optimizer)
    # A resumed process starts with deliberately WRONG RNG, so load must restore it.
    initial_seed = (600 if resume is None else 9600) + rank
    random.seed(initial_seed)
    np.random.seed(initial_seed)
    torch.manual_seed(initial_seed)
    start_step = 0
    events = []
    saved = []
    load_check = None
    if resume is not None:
        source = Path(resume)
        start_step = int(source.name.split("-")[-1])
        gate.verify(source, binding, start_step, receipt_sha)
        previous = json.loads((source / f"observed_{rank}.json").read_text())
        before = state_digests(accelerator.unwrap_model(model), optimizer)
        accelerator.load_state(str(source), load_kwargs={"weights_only": True}, map_location="cpu")
        actual = state_digests(accelerator.unwrap_model(model), optimizer)
        gate.verify_restored(previous["state"], actual)
        if accelerator.step != 0 or not accelerator.sync_gradients:
            raise ValueError("restored_accelerate_boundary_mismatch")
        if any(before[key] == actual[key] for key in ("python_rng", "numpy_rng", "torch_rng")):
            raise ValueError("fresh_process_rng_negative_control_ineffective")
        events = previous["events"]
        load_check = {"all_components_restored_exactly": True, "preload_rng_all_different": True,
                      "source_manifest_sha256": receipt_sha, "start_step": start_step}
    output = Path(output)
    new_forwards = 0
    for step in range(start_step, end_step):
        batches = rank_update_batches(plan, rank, step)
        lr = update_learning_rate(plan, batches, "0.00001")
        set_optimizer_learning_rate(optimizer, lr)
        optimizer.zero_grad(set_to_none=True)
        for index, batch in enumerate(batches):
            packed = pack_batch(plan, batch, lambda c, a: encoded[(c, a)], target, pad_id=0)
            receipt = observe_batch(plan, batch, packed, target, pad_id=0)
            ids = torch.tensor(packed.input_ids)
            mask = torch.tensor(packed.attention_mask)
            signs = torch.tensor(packed.signs, dtype=torch.float64)
            sync = index == len(batches) - 1
            with planned_microbatch_context(accelerator, model, synchronize=sync):
                scores = model(ids, mask)
                count = len(batch.rows)
                loss = torch.nn.functional.softplus(-signs * (scores[:count] - scores[count:])).mean()
                backward_local_pair_mean(accelerator, loss, batch)
            observed = accelerator.unwrap_model(model).observed[-1]
            if tuple(zip(observed[:count], observed[count:])) != receipt.encoded_digests:
                raise ValueError("model_boundary_encoding_mismatch")
            event = asdict(receipt)
            event.update({"synchronize": sync, "learning_rate": lr})
            events.append(event)
            new_forwards += 1
        finish = finish_non_deepspeed_update(accelerator, model, optimizer, max_grad_norm=1.0)
        if finish["optimizer_step_skipped"]:
            raise ValueError("unexpected_optimizer_step_skip")
        completed = step + 1
        if completed not in (2, 3, 4):
            continue
        checkpoint = output / f"checkpoint-{completed}"
        partial = output / f"checkpoint-{completed}.partial"
        if rank == 0:
            if checkpoint.exists():
                raise ValueError("checkpoint_overwrite_forbidden")
            partial.mkdir(mode=0o700)
        accelerator.wait_for_everyone()
        before_save = state_digests(accelerator.unwrap_model(model), optimizer)
        accelerator.save_state(str(partial), safe_serialization=True)
        after_save = state_digests(accelerator.unwrap_model(model), optimizer)
        gate.verify_restored(before_save, after_save)
        gate.atomic_json(partial / f"observed_{rank}.json", {
            "rank": rank, "binding": binding, "completed_steps": completed,
            "state": after_save, "events": events,
        })
        accelerator.wait_for_everyone()
        if rank == 0:
            gate.seal(partial, binding, completed, accelerator.step)
            os.replace(partial, checkpoint)
        accelerator.wait_for_everyone()
        manifest_sha = gate.sha(checkpoint / "manifest.json")
        gate.verify(checkpoint, binding, completed, manifest_sha)
        saved.append({"step": completed, "manifest_sha256": manifest_sha})
    if torch.cuda.is_initialized():
        raise ValueError("unexpected_cuda_context")
    gathered = [None] * world
    dist.all_gather_object(gathered, {
        "rank": rank, "events": events, "new_forwards": new_forwards,
        "true_target_reads_this_process": len(reads), "load_check": load_check,
    })
    if rank == 0:
        receipts = []
        for state in gathered:
            for e in state["events"]:
                receipts.append(BatchReceipt(e["plan_sha256"], e["optimizer_step"], e["micro_step"],
                    e["rank"], tuple(e["pair_keys"]), tuple(tuple(x) for x in e["encoded_digests"]),
                    e["valid_tokens"], e["padded_slots"]))
        verify_consumption_prefix(plan, receipts, end_step)
        gate.atomic_json(output / "trajectory.json", {
            "binding": binding, "start_step": start_step, "end_step": end_step,
            "optimizer_updates": end_step - start_step, "saved": saved,
            "states": [{k: v for k, v in state.items() if k != "events"} for state in gathered],
            "new_forwards": sum(state["new_forwards"] for state in gathered),
        })
    accelerator.wait_for_everyone()
    dist.destroy_process_group()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(root):
    if (not root.is_absolute() or not root.is_relative_to(Path("/tmp")) or root.exists()
            or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
            or os.environ.get("GLOO_SOCKET_IFNAME") != "lo"):
        raise ValueError("new_private_tmp_cpu_run_required")
    root.mkdir(mode=0o700)
    started = time.monotonic()
    runtime = {"updates": runtime_binding(), "checkpoint": checkpoint_runtime()}
    names = (Path(__file__).name, "global_local_accelerate_checkpoint_gate.py",
             "global_local_accelerate_update_adapter.py", "global_local_partial_ddp_cpu_validation.py",
             "global_local_batch_adapter.py", "global_local_execution_plan.py",
             "global_local_token_budget_plan.py", "verify_global_local_token_budget_plan.py",
             "verify_global_local_execution_trace.py", "verify_global_local_accelerate_resume.py")
    sources = {name: gate.sha(Path(__file__).with_name(name)) for name in names}
    preflight = {
        "base_commit": BASE_COMMIT, "sources": sources, "runtime": runtime,
        "question": "Does exact Accelerate restore all CPU DDP state at partial/phase boundaries?",
        "worlds": [2, 4], "arms": ["G_to_L", "Ghash_to_L"], "seed": 6,
        "trajectories_per_world_arm": ["full", "prefix2", "resume2", "prefix3", "resume3"],
        "cuts": [2, 3], "save_calls_mirrored_in_full": True,
        "reference": "bitwise final state and exact event prefix; independently decoded framework files",
        "limits": {"seconds": 1200, "CPU_threads_per_rank": 1, "GPU": 0, "API": 0, "research_fits": 0},
        "scope": "synthetic-two-parameter-cpu-only", "fixed_peak_lr": "0.00001",
        "prospective_or_historical_data_read": False, "formal_protocol_modified": False,
        "runtime_installed_or_modified": False, "G0_modified_or_resubmitted": False,
        "checkpoint_selector_used": False, "power_failure_or_Zero3_bf16_claim": False,
    }
    gate.atomic_json(root / "preflight.json", preflight)
    trials = []
    for world in (2, 4):
        for arm in ("G_to_L", "Ghash_to_L"):
            for tag, end, cut in (("full", 4, None), ("prefix2", 2, None), ("resume2", 4, 2),
                                  ("prefix3", 3, None), ("resume3", 4, 3)):
                if time.monotonic() - started > 1200:
                    raise ValueError("CPU_budget_exceeded")
                name = f"w{world}-{arm}-{tag}"
                output = root / name
                output.mkdir(mode=0o700)
                source = None if cut is None else root / f"w{world}-{arm}-prefix{cut}" / f"checkpoint-{cut}"
                receipt_sha = None if source is None else gate.sha(source / "manifest.json")
                start = time.monotonic()
                mp.spawn(_worker, args=(world, arm, str(output), end,
                    None if source is None else str(source), receipt_sha,
                    json_digest(runtime), json_digest(sources), free_port()), nprocs=world, join=True)
                trial = json.loads((output / "trajectory.json").read_text())
                trials.append({"name": name, "world": world, "arm": arm, "seed": 6, "tag": tag,
                    "optimizer_updates": trial["optimizer_updates"], "new_forwards": trial["new_forwards"],
                    "wall_seconds_not_throughput_benchmark": time.monotonic() - start,
                    "trajectory_sha256": gate.sha(output / "trajectory.json")})
                print(json.dumps({"completed_trajectories": len(trials), "name": name}), flush=True)
    if sources != {name: gate.sha(Path(__file__).with_name(name)) for name in names}:
        raise ValueError("source_changed_during_run")
    report = {"status": "EXECUTION_COMPLETE_INDEPENDENT_VERIFICATION_REQUIRED",
              "base_commit": BASE_COMMIT, "preflight_sha256": gate.sha(root / "preflight.json"),
              "trials": trials, "distributed_trajectories": len(trials),
              "global_optimizer_updates": sum(t["optimizer_updates"] for t in trials),
              "all_rank_forward_calls": sum(t["new_forwards"] for t in trials),
              "research_model_fits": 0, "real_data_opened": False, "gpu_context_created": False,
              "API_calls": 0, "runtime": runtime, "sources": sources}
    gate.atomic_json(root / "summary.json", report)
    with (root / "runs.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(trials[0]))
        writer.writeheader()
        writer.writerows(trials)
    print(json.dumps({k: v for k, v in report.items() if k not in ("trials", "sources", "runtime")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
