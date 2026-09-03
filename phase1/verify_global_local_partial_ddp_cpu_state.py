"""Independent read-only verification of partial-DDP synthetic saved states."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch


def equal(left, right):
    if isinstance(left, torch.Tensor):
        return (isinstance(right, torch.Tensor) and left.dtype == right.dtype
                and left.shape == right.shape and torch.equal(left, right))
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(root):
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("unsafe_manifest")
    manifest = json.loads(manifest_path.read_text())
    expected = {f"rank-{rank}.pt" for rank in range(manifest["world"])}
    if manifest["world"] not in (2, 4) or set(manifest["rank_files"]) != expected:
        raise ValueError("rank_manifest_mismatch")
    # Hash every rank before deserializing any rank.
    for name, expected_sha in manifest["rank_files"].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or sha(path) != expected_sha:
            raise ValueError("checkpoint_hash_mismatch")
    return manifest, [
        torch.load(root / f"rank-{rank}.pt", map_location="cpu", weights_only=True)
        for rank in range(manifest["world"])
    ]


def verify(root):
    summary_path = root / "summary.json"
    report = json.loads(summary_path.read_text())
    if (report.get("status") != "PASS_SYNTHETIC_PARTIAL_DDP_GLOO_NOT_RESEARCH_FIT"
            or report.get("research_model_fits") != 0
            or report.get("real_data_opened") is not False
            or report.get("gpu_context_created") is not False):
        raise ValueError("summary_scope_mismatch")
    cases = []
    expected_events = {2: (25, 11, 14), 4: (13, 6, 7)}
    for world in (2, 4):
        full_count, prefix_count, resumed_count = expected_events[world]
        for arm in ("G_to_L", "Ghash_to_L"):
            full_manifest, full = read(root / f"w{world}-{arm}-stochastic-full")
            resumed_manifest, resumed = read(root / f"w{world}-{arm}-fresh-process-resume")
            prefix_manifest, prefix = read(root / f"w{world}-{arm}-prefix")
            if not (full_manifest["completed_steps"] == resumed_manifest["completed_steps"] == 4
                    and prefix_manifest["completed_steps"] == 2):
                raise ValueError("completed_step_mismatch")
            for rank, (left, right, first) in enumerate(zip(full, resumed, prefix)):
                for key in ("binding", "model", "optimizer", "rng", "events", "completed_steps"):
                    if not equal(left[key], right[key]):
                        raise ValueError("resume_state_mismatch:" + key)
                if left["binding"]["rank"] != rank or left["binding"]["world"] != world:
                    raise ValueError("rank_binding_mismatch")
                if not (len(left["events"]) == full_count
                        and len(first["events"]) == prefix_count
                        and left["events"][:prefix_count] == first["events"]
                        and left["new_forward_calls"] == full_count
                        and right["new_forward_calls"] == resumed_count):
                    raise ValueError("event_prefix_or_count_mismatch")
                if equal(left["model"], first["model"]):
                    raise ValueError("resume_suffix_did_not_update_model")
                for event in left["events"]:
                    if (event["loss_mean_scale_denominator"] != event["update_real_pairs"]
                            or event["lr_scale_denominator"] <= 0):
                        raise ValueError("loss_or_lr_receipt_mismatch")
            for state in full[1:]:
                for key in ("model", "optimizer"):
                    if not equal(full[0][key], state[key]):
                        raise ValueError("rank_state_mismatch")
            cases.append({
                "world": world,
                "arm": arm,
                "verified_ranks": len(full),
                "complete_state_bitwise_equal": True,
                "event_prefix_equal": True,
            })
        _, true_states = read(root / f"w{world}-G_to_L-stochastic-full")
        _, hash_states = read(root / f"w{world}-Ghash_to_L-stochastic-full")
        for true_state, hash_state in zip(true_states, hash_states):
            for left, right in zip(true_state["events"], hash_state["events"]):
                if ({key: value for key, value in left.items() if key != "plan_sha256"}
                        != {key: value for key, value in right.items() if key != "plan_sha256"}):
                    raise ValueError("cross_label_input_trace_mismatch")
    if (len(report.get("trials", [])) != 16
            or report.get("distributed_trajectories") != 16
            or report.get("global_optimizer_updates") != 48
            or report.get("all_rank_forward_calls") != 612
            or report.get("partial_loss_normalization_matches_full_update_reference") is not True
            or report.get("G_and_Ghash_input_trace_identical") is not True):
        raise ValueError("summary_count_or_relation_mismatch")
    return {
        "status": "PASS_INDEPENDENT_PARTIAL_DDP_SAVED_STATE",
        "resume_cases": cases,
        "input_identity_across_label_arms": True,
        "partial_loss_reference_checks": 4,
        "research_model_fits": 0,
        "summary_sha256": sha(summary_path),
        "verifier_sha256": sha(__file__),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    print(json.dumps(verify(parser.parse_args().root.resolve()), sort_keys=True))

