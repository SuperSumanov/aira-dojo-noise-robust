"""Independent read-only decoder/verifier; does not import the harness or adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    import numpy as np
    import torch
    if isinstance(value, torch.Tensor):
        return ["tensor", str(value.dtype), list(value.shape), value.detach().cpu().contiguous().numpy().tobytes().hex()]
    if isinstance(value, np.ndarray):
        return ["numpy", value.dtype.str, list(value.shape), value.tobytes().hex()]
    if isinstance(value, dict):
        entries = [[encode(k), encode(v)] for k, v in value.items()]
        entries.sort(key=lambda entry: json.dumps(entry[0], sort_keys=True))
        return ["dict", entries]
    if type(value) in (tuple, list):
        return [type(value).__name__, [encode(v) for v in value]]
    if type(value) is float:
        return ["float", value.hex()]
    if value is None or type(value) in (str, bool, int):
        return [type(value).__name__, value]
    raise ValueError("unknown_state_type")


def digest(value):
    raw = json.dumps(encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def decode_checkpoint(root, expected_sha, world, arm, step, *, binary):
    path = root / "manifest.json"
    if root.is_symlink() or path.is_symlink() or sha(path) != expected_sha:
        raise ValueError("checkpoint_manifest_mismatch")
    manifest = json.loads(path.read_text())
    names = {"model.safetensors", "optimizer.bin"} | {f"random_states_{r}.pkl" for r in range(world)} | {
        f"observed_{r}.json" for r in range(world)}
    binding = manifest["binding"]
    if (binding["world"] != world or binding["arm"] != arm or binding["scope"] != "synthetic-two-parameter-cpu-only"
            or manifest["completed_steps"] != step or manifest["accelerator_internal_step"] != 0
            or set(manifest["files"]) != names):
        raise ValueError("checkpoint_binding_or_inventory_mismatch")
    # A receipt-only export deliberately has no model/optimizer/RNG files.
    required = names if binary else {f"observed_{r}.json" for r in range(world)}
    if {p.name for p in root.iterdir()} != required | {"manifest.json"}:
        raise ValueError("checkpoint_directory_inventory_mismatch")
    for name in required:
        file = root / name
        receipt = manifest["files"][name]
        if (file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= 1024 * 1024
                or file.stat().st_size != receipt["bytes"] or sha(file) != receipt["sha256"]):
            raise ValueError("checkpoint_file_mismatch")
    records = [json.loads((root / f"observed_{r}.json").read_text()) for r in range(world)]
    if binary:
        import numpy as np
        import torch
        from safetensors.torch import load_file
        model = dict(load_file(str(root / "model.safetensors"), device="cpu"))
        optimizer = torch.load(root / "optimizer.bin", map_location="cpu", weights_only=True)
        if list(model) != ["weight"] or model["weight"].shape != (2,):
            raise ValueError("not_two_parameter_synthetic_model")
        from numpy.core.multiarray import _reconstruct
        allow = [_reconstruct, np.ndarray, np.dtype, type(np.dtype("uint32"))]
        for rank, observed in enumerate(records):
            with torch.serialization.safe_globals(allow):
                rng = torch.load(root / f"random_states_{rank}.pkl", map_location="cpu", weights_only=True)
            if set(rng) != {"step", "random_state", "numpy_random_seed", "torch_manual_seed"} or rng["step"] != 0:
                raise ValueError("unexpected_saved_rng_scope")
            decoded = {"model": digest(model), "optimizer": digest(optimizer),
                       "python_rng": digest(rng["random_state"]), "numpy_rng": digest(rng["numpy_random_seed"]),
                       "torch_rng": digest(rng["torch_manual_seed"])}
            if decoded != observed["state"]:
                raise ValueError("framework_checkpoint_disagrees_with_observation")
    for rank, observed in enumerate(records):
        if observed["rank"] != rank or observed["binding"] != binding or observed["completed_steps"] != step:
            raise ValueError("rank_binding_mismatch")
        expected_address = [(s, m, rank) for s in range(step)
                            for m in range(({2: [8, 3, 8, 6], 4: [4, 2, 4, 3]}[world])[s])]
        if [(e["optimizer_step"], e["micro_step"], e["rank"]) for e in observed["events"]] != expected_address:
            raise ValueError("event_order_or_count_mismatch")
        for event in observed["events"]:
            s, m = event["optimizer_step"], event["micro_step"]
            micros = ({2: [8, 3, 8, 6], 4: [4, 2, 4, 3]}[world])[s]
            if event["synchronize"] is not (m == micros - 1) or event["learning_rate"] != 1e-5:
                raise ValueError("event_sync_or_lr_mismatch")
    for s in range(step):
        pairs = [key for rec in records for e in rec["events"] if e["optimizer_step"] == s for key in e["pair_keys"]]
        if len(pairs) != [128, 48, 128, 81][s] or len(set(pairs)) != len(pairs):
            raise ValueError("pair_coverage_mismatch")
    for record in records[1:]:
        for key in ("model", "optimizer"):
            if record["state"][key] != records[0]["state"][key]:
                raise ValueError("rank_parameter_state_mismatch")
    return records


def verify(root, summary_sha, *, binary=True):
    summary_path = root / "summary.json"
    if sha(summary_path) != summary_sha:
        raise ValueError("summary_hash_mismatch")
    report = json.loads(summary_path.read_text())
    if (report["status"] != "EXECUTION_COMPLETE_INDEPENDENT_VERIFICATION_REQUIRED"
            or report["research_model_fits"] != 0 or report["real_data_opened"] is not False
            or report["gpu_context_created"] is not False or report["API_calls"] != 0
            or sha(root / "preflight.json") != report["preflight_sha256"]):
        raise ValueError("scope_or_preflight_mismatch")
    expected = {f"w{w}-{a}-{t}" for w in (2, 4) for a in ("G_to_L", "Ghash_to_L")
                for t in ("full", "prefix2", "resume2", "prefix3", "resume3")}
    if len(report["trials"]) != len(expected) or {t["name"] for t in report["trials"]} != expected:
        raise ValueError("trajectory_matrix_mismatch")
    cache = {}
    forwards, updates, checkpoints = 0, 0, 0
    for row in report["trials"]:
        trial_root = root / row["name"]
        if sha(trial_root / "trajectory.json") != row["trajectory_sha256"]:
            raise ValueError("trajectory_hash_mismatch")
        trial = json.loads((trial_root / "trajectory.json").read_text())
        start = int(row["tag"][-1]) if row["tag"].startswith("resume") else 0
        end = int(row["tag"][-1]) if row["tag"].startswith("prefix") else 4
        if trial["start_step"] != start or trial["end_step"] != end or trial["optimizer_updates"] != end - start:
            raise ValueError("trajectory_cursor_mismatch")
        if {s["rank"] for s in trial["states"]} != set(range(row["world"])) or len(trial["states"]) != row["world"]:
            raise ValueError("trajectory_rank_set_mismatch")
        expected_saved = [i for i in (2, 3, 4) if start < i <= end]
        if [s["step"] for s in trial["saved"]] != expected_saved:
            raise ValueError("checkpoint_call_pattern_mismatch")
        final = None
        for saved in trial["saved"]:
            step = saved["step"]
            final = decode_checkpoint(trial_root / f"checkpoint-{step}", saved["manifest_sha256"],
                                      row["world"], row["arm"], step, binary=binary)
            checkpoints += 1
        for state, record in zip(trial["states"], final):
            suffix = [e for e in record["events"] if e["optimizer_step"] >= start]
            expected_reads = 2 * sum(len(e["pair_keys"]) for e in suffix
                                    if row["arm"] == "G_to_L" or e["optimizer_step"] >= 2)
            if state["new_forwards"] != len(suffix) or state["true_target_reads_this_process"] != expected_reads:
                raise ValueError("forward_or_true_label_access_mismatch")
            if start and (state["load_check"]["all_components_restored_exactly"] is not True
                          or state["load_check"]["preload_rng_all_different"] is not True
                          or state["load_check"]["start_step"] != start):
                raise ValueError("load_check_failed")
        count = sum(s["new_forwards"] for s in trial["states"])
        if count != trial["new_forwards"] or count != row["new_forwards"] or end - start != row["optimizer_updates"]:
            raise ValueError("trajectory_count_mismatch")
        forwards += count
        updates += end - start
        cache[row["name"]] = final
    cases = []
    for world in (2, 4):
        for arm in ("G_to_L", "Ghash_to_L"):
            full = cache[f"w{world}-{arm}-full"]
            for cut in (2, 3):
                prefix = cache[f"w{world}-{arm}-prefix{cut}"]
                resumed = cache[f"w{world}-{arm}-resume{cut}"]
                for a, b, p in zip(full, resumed, prefix):
                    if a != b:
                        raise ValueError("final_state_or_events_not_bitwise_equal")
                    if a["events"][:len(p["events"])] != p["events"] or a["state"]["model"] == p["state"]["model"]:
                        raise ValueError("prefix_or_suffix_progress_mismatch")
                cases.append({"world": world, "arm": arm, "cut": cut, "ranks": world,
                              "complete_state_and_events_equal": True})
        true, hashed = (cache[f"w{world}-{arm}-full"] for arm in ("G_to_L", "Ghash_to_L"))
        for a, b in zip(true, hashed):
            clean = lambda rec: [{k: v for k, v in e.items() if k != "plan_sha256"} for e in rec["events"]]
            if clean(a) != clean(b):
                raise ValueError("G_Ghash_input_trace_mismatch")
    if (report["distributed_trajectories"] != len(expected) or report["global_optimizer_updates"] != updates
            or report["all_rank_forward_calls"] != forwards):
        raise ValueError("summary_count_mismatch")
    return {"status": "PASS_INDEPENDENT_ACCELERATE_RESUME" if binary else "PASS_RECEIPT_ONLY_ACCELERATE_RESUME",
            "summary_sha256": summary_sha, "verifier_sha256": sha(Path(__file__)),
            "framework_binary_checkpoints_decoded": checkpoints if binary else 0,
            "checkpoint_receipts_checked": checkpoints, "resume_cases": cases,
            "verified_resume_rank_states": sum(c["ranks"] for c in cases),
            "distributed_trajectories": len(expected), "global_optimizer_updates": updates,
            "all_rank_forward_calls": forwards, "G_Ghash_input_trace_identical": True,
            "model_fit_or_scaling_result": False, "Zero3_bf16_or_power_failure_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--summary-sha", required=True)
    parser.add_argument("--receipt-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.summary_sha, binary=not args.receipt_only), sort_keys=True))
