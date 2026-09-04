from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class IndependentVerificationError(ValueError):
    pass


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise IndependentVerificationError(f"duplicate key: {key}")
        output[key] = value
    return output


def independently_verify(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=_unique_pairs)
    if value["protocol"] != "g-reuse-effect-v1":
        raise IndependentVerificationError("protocol mismatch")
    if value["status"] != "FROZEN_AWAITING_SOURCE_G0_AND_GPU_APPROVAL":
        raise IndependentVerificationError("protocol is not blocked")
    if set(value["authorization"].values()) != {0}:
        raise IndependentVerificationError("nonzero authorization")

    pending = value["pending_contract"]
    if any(item is not False for key, item in pending.items() if key not in {
        "exact_pivot_checkpoint",
        "exact_common_valid_token_cap",
        "exact_gpu_hours",
    }):
        raise IndependentVerificationError("pending gate self-attested")
    if any(pending[key] is not None for key in {
        "exact_pivot_checkpoint",
        "exact_common_valid_token_cap",
        "exact_gpu_hours",
    }):
        raise IndependentVerificationError("pending quantity filled")
    if len(value["fixed_across_compute_matched_arms"]) != 8:
        raise IndependentVerificationError("fixed-across-arm contract drift")

    core = value["core_stage"]
    expected_arms = [
        "L1",
        "Lbudget",
        "G-reuse-budget",
        "G-reuse-to-L-full",
        "Ghash-reuse-to-L-full",
    ]
    arm_ids = [arm["id"] for arm in core["arms"]]
    seeds = core["seeds"]
    if arm_ids != expected_arms or seeds != [6, 7, 8]:
        raise IndependentVerificationError("arm or seed drift")
    if core["planned_fits"] != len(arm_ids) * len(seeds):
        raise IndependentVerificationError("core fit arithmetic mismatch")
    if core["arms"][4]["uses_true_global_orientation"] is not False:
        raise IndependentVerificationError("hash arm may read global truth")

    hash_control = value["hash_control"]
    if not (
        hash_control["seed"] == 20260823
        and hash_control["pair_level_independent_flips"] is False
        and hash_control["shared_endpoint_order_is_transitive"] is True
        and hash_control["global_rows_order_tokens_updates_match_full"] is True
        and hash_control["local_phase_byte_identical_to_full"] is True
        and hash_control["true_global_orientation_read"] is False
        and hash_control["collision_action"] == "fail closed"
    ):
        raise IndependentVerificationError("hash-control contract drift")

    gates = value["core_gates"]
    if gates["full_minus_lbudget_point_minimum"] != 0.02:
        raise IndependentVerificationError("deployment threshold drift")
    if gates["single_task_correct_difference_share_maximum"] != 0.35:
        raise IndependentVerificationError("task concentration threshold drift")

    cost = value["conditional_cost_stage"]
    if cost["enabled_only_if_all_core_gates_pass"] is not True:
        raise IndependentVerificationError("cost stage no longer conditional")
    if cost["arm"] != "G-reuse-to-L-spectral50" or cost["seeds"] != seeds:
        raise IndependentVerificationError("cost arm or seed drift")
    if cost["planned_additional_fits"] != len(seeds):
        raise IndependentVerificationError("cost fit arithmetic mismatch")
    if cost["try_other_budget_points_after_failure"] is not False:
        raise IndependentVerificationError("post-result budget rescue enabled")

    return {
        "status": "INDEPENDENT_PROTOCOL_VERIFICATION_PASS",
        "protocol_sha256": hashlib.sha256(raw).hexdigest(),
        "ready_for_fit": False,
        "core_planned_fits": len(arm_ids) * len(seeds),
        "conditional_cost_planned_fits": len(seeds),
        "protected_values_opened": False,
        "gpu_paid_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = independently_verify(args.protocol)
    rendered = json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
