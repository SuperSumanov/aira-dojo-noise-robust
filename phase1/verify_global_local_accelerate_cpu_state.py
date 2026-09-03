"""Independent JSON-only verifier for the bounded Accelerate CPU artifacts.

No imports from the adapter, producer, Torch, Transformers, or Accelerate.
This checks saved artifacts, not a new optimization trajectory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _read(path):
    _require(path.is_file() and not path.is_symlink(), "unsafe_or_missing_artifact")
    _require(0 < path.stat().st_size < 8 * 1024 * 1024, "invalid_artifact_size")
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def verify(root: Path, expected_summary_sha256: str):
    summary, digest = _read(root / "summary.json")
    _require(digest == expected_summary_sha256, "summary_hash_mismatch")
    _require(summary["status"] == "PASS_SYNTHETIC_ACCELERATE_DDP_PARTIAL_UPDATES_NOT_RESEARCH_FIT", "status_mismatch")
    _require(summary["distributed_trajectories"] == 4, "trajectory_count_mismatch")
    _require(summary["global_optimizer_updates"] == 16, "update_count_mismatch")
    _require(summary["all_rank_forward_calls"] == 204, "forward_count_mismatch")
    _require(summary["world_sizes"] == [2, 4], "world_matrix_mismatch")
    _require(summary["arms"] == ["G_to_L", "Ghash_to_L"], "arm_matrix_mismatch")
    _require(summary["matching_real_terminal_remainders"] == {"G": 48, "L": 81}, "remainder_mismatch")
    _require(summary["research_model_fits"] == summary["api_calls"] == 0, "scope_count_mismatch")
    _require(summary["real_data_opened"] is summary["gpu_context_created"] is False, "scope_access_mismatch")
    _require(summary["trainer_default_loop_used"] is False, "trainer_scope_mismatch")
    _require(summary["real_HF_reward_model_DeepSpeed_Zero3_bf16_verified"] is False, "unsupported_gpu_claim")
    _require(summary["runtime_binding"]["versions"] == {
        "torch": "2.11.0+cu128", "transformers": "5.12.1",
        "accelerate": "1.14.0", "deepspeed": "0.19.3",
    }, "runtime_version_mismatch")
    expected_matrix = {(2, "G_to_L"), (2, "Ghash_to_L"), (4, "G_to_L"), (4, "Ghash_to_L")}
    seen = set()
    receipts = []
    for trial in summary["trials"]:
        key = (trial["world"], trial["arm"])
        _require(key in expected_matrix and key not in seen, "unknown_or_duplicate_trial")
        seen.add(key)
        world, arm = key
        manifest, manifest_sha = _read(root / f"w{world}-{arm}" / "manifest.json")
        _require(manifest_sha == trial["manifest_sha256"], "manifest_hash_mismatch")
        _require(manifest == {k: v for k, v in trial.items() if k != "manifest_sha256"}, "manifest_summary_mismatch")
        _require(trial["optimizer_updates"] == 4, "trial_update_count_mismatch")
        _require(trial["matches_independent_full_update_reference"] is True, "reference_check_missing")
        states = trial["states"]
        _require({state["rank"] for state in states} == set(range(world)) and len(states) == world, "rank_set_mismatch")
        _require(trial["all_rank_forward_calls"] == sum(len(state["receipts"]) for state in states), "trial_forward_count_mismatch")
        all_addresses = set()
        global_pairs_per_update = [0, 0, 0, 0]
        weights = []
        for state in states:
            weights.append(state["weight"])
            updates = state["updates"]
            _require([update["optimizer_step"] for update in updates] == [0, 1, 2, 3], "update_order_mismatch")
            _require(len(state["sync_sequences"]) == 4, "sync_sequence_count_mismatch")
            expected_reads = 0
            for step, (sequence, update) in enumerate(zip(state["sync_sequences"], updates)):
                _require(sequence and sequence == [False] * (len(sequence) - 1) + [True], "invalid_sync_boundary")
                _require(len(sequence) == update["microsteps"] == len(update["local_pair_counts"]), "microstep_shape_mismatch")
                _require(all(0 < count <= 8 for count in update["local_pair_counts"]), "invalid_local_pair_count")
                _require(update["step_owner"] == "adapter_non_deepspeed", "step_owner_mismatch")
                _require(update["learning_rate"] == 0.00001, "fixture_lr_mismatch")
                pair_count = sum(update["local_pair_counts"])
                global_pairs_per_update[step] += pair_count
                if arm == "G_to_L" or step >= 2:
                    expected_reads += 2 * pair_count
                events = [event for event in state["receipts"] if event["optimizer_step"] == step]
                _require([event["micro_step"] for event in events] == list(range(len(sequence))), "receipt_microstep_order_mismatch")
                _require([len(event["pair_keys"]) for event in events] == update["local_pair_counts"], "receipt_pair_count_mismatch")
            _require(state["true_target_reads"] == expected_reads, "true_target_access_count_mismatch")
            for event in state["receipts"]:
                address = (event["optimizer_step"], event["micro_step"], event["rank"])
                _require(address not in all_addresses and event["rank"] == state["rank"], "duplicate_or_wrong_rank_receipt")
                _require(event["plan_sha256"] == trial["plan_sha256"], "receipt_plan_hash_mismatch")
                _require(event["valid_tokens"] == 8 * len(event["pair_keys"]), "fixture_token_count_mismatch")
                all_addresses.add(address)
        _require(global_pairs_per_update == [128, 48, 128, 81], "global_update_pair_count_mismatch")
        _require(all(weight == weights[0] for weight in weights), "rank_weights_differ")
        _require(len(weights[0]) == len(trial["reference_weight"]) == 2, "weight_schema_mismatch")
        _require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) for a, b in zip(weights[0], trial["reference_weight"])), "reference_weight_mismatch")
        receipts.append({
            "world": world,
            "arm": arm,
            "verified_ranks": world,
            "verified_forward_receipts": len(all_addresses),
            "global_pairs_per_update": global_pairs_per_update,
            "manifest_sha256": manifest_sha,
            "target_access_count_exact": True,
            "weights_match_independent_reference": True,
        })
    _require(seen == expected_matrix, "incomplete_trial_matrix")
    for world in (2, 4):
        true = next(row for row in summary["trials"] if (row["world"], row["arm"]) == (world, "G_to_L"))
        hashed = next(row for row in summary["trials"] if (row["world"], row["arm"]) == (world, "Ghash_to_L"))
        _require(true["input_sha256"] == hashed["input_sha256"], "control_input_hash_mismatch")
        for left, right in zip(true["states"], hashed["states"]):
            a = [{k: v for k, v in event.items() if k != "plan_sha256"} for event in left["receipts"]]
            b = [{k: v for k, v in event.items() if k != "plan_sha256"} for event in right["receipts"]]
            _require(a == b and left["sync_sequences"] == right["sync_sequences"], "control_trace_mismatch")
    return {
        "status": "PASS_INDEPENDENT_ACCELERATE_SAVED_ARTIFACT",
        "summary_sha256": digest,
        "trials": receipts,
        "G_and_Ghash_input_and_boundary_traces_identical": True,
        "new_optimization_trajectories": 0,
        "torch_or_adapter_imported": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-summary-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.root, args.expected_summary_sha256)
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
