"""Verify the aggregate historical token-plan receipt without source data.

This checker does not import either plan implementation.  It validates the
published cross-arm, cross-shape, accounting, and scope relationships and can
therefore run after the guarded real-input process has exited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ARMS = {"L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"}
SEEDS = {6, 7, 8}
WORLDS = {2, 4}
REFERENCE_PAIRS = 14081
REFERENCE_TOKENS = 104863947
GLOBAL_PAIRS = 9392
GLOBAL_TOKENS = 72676205
LOCAL_PAIRS = 4689
LOCAL_TOKENS = 32187742
WARMUP_TOKENS = 3145919
FROZEN_SHA256 = "3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9"


class ReceiptVerificationError(ValueError):
    pass


def check(condition: bool, reason: str) -> None:
    if not condition:
        raise ReceiptVerificationError(reason)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected_protocol_sha256: str) -> dict:
    check(path.is_file() and not path.is_symlink(), "unsafe_summary_path")
    check(re.fullmatch(r"[0-9a-f]{64}", expected_protocol_sha256) is not None,
          "invalid_expected_protocol_sha256")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(value.get("status") == "PASS_HISTORICAL_TOKEN_PLAN_READINESS_EFFECT_BLOCKED",
          "status_mismatch")
    check(value.get("protocol_sha256") == expected_protocol_sha256,
          "protocol_binding_mismatch")
    check(value.get("frozen_v2_sha256") == FROZEN_SHA256, "frozen_binding_mismatch")
    counts = value.get("identity_counts", {})
    check(counts.get("local_pairs") == LOCAL_PAIRS, "local_pair_count_mismatch")
    check(counts.get("global_candidate_pairs") == GLOBAL_PAIRS, "global_pair_count_mismatch")
    check(counts.get("combined_pairs_once") == REFERENCE_PAIRS, "reference_pair_count_mismatch")
    tokens = value.get("token_counts", {})
    check(tokens.get("global_once") == GLOBAL_TOKENS, "global_token_count_mismatch")
    check(tokens.get("local_once") == LOCAL_TOKENS, "local_token_count_mismatch")
    check(tokens.get("combined_once") == REFERENCE_TOKENS, "reference_token_count_mismatch")
    check(tokens.get("warmup") == WARMUP_TOKENS, "warmup_token_count_mismatch")

    plans = value.get("plans")
    check(isinstance(plans, list) and len(plans) == 30, "plan_count_mismatch")
    index = {}
    for item in plans:
        key = (item.get("world_size"), item.get("seed"), item.get("arm"))
        check(key not in index and key[0] in WORLDS and key[1] in SEEDS and key[2] in ARMS,
              "invalid_or_duplicate_plan_key")
        index[key] = item
        check(item.get("status") == "APPROVED_METADATA_PLAN_EFFECT_TRAINING_BLOCKED",
              "plan_status_mismatch")
        check(item.get("reference_pair_visits") == REFERENCE_PAIRS,
              "plan_reference_pair_mismatch")
        check(item.get("reference_valid_tokens") == REFERENCE_TOKENS,
              "plan_reference_token_mismatch")
        check(item.get("warmup_valid_tokens") == WARMUP_TOKENS,
              "plan_warmup_mismatch")
        check(item.get("peak_lr_decimal") == "0.00001", "plan_lr_mismatch")
        check(item.get("training_authorized") is False
              and item.get("trainer_integrated") is False
              and item.get("actual_compute_matched") is None,
              "plan_scope_mismatch")
        check(item.get("real_pair_padding_or_drop") is False, "hidden_pair_padding_or_drop")
        check(item.get("all_ranks_participate_each_micro_step") is True,
              "rank_participation_claim_missing")
        check(item.get("planned_valid_tokens") <= REFERENCE_TOKENS,
              "plan_token_overshoot")
        shortfall = item.get("token_budget_shortfall")
        check(type(shortfall) is int and shortfall == REFERENCE_TOKENS - item["planned_valid_tokens"],
              "plan_shortfall_mismatch")
        if item["arm"] in ("Lbudget", "Gbudget"):
            next_tokens = item.get("budget_stop_next_pair_tokens")
            if next_tokens is None:
                check(shortfall == 0, "exact_budget_missing_next_pair_mismatch")
            else:
                check(type(next_tokens) is int and 0 <= shortfall < next_tokens,
                      "whole_pair_prefix_not_maximal")
        for field in ("plan_sha256", "input_sha256"):
            check(re.fullmatch(r"[0-9a-f]{64}", str(item.get(field, ""))) is not None,
                  "invalid_plan_hash")

    check(set(index) == {(world, seed, arm) for world in WORLDS for seed in SEEDS for arm in ARMS},
          "plan_matrix_incomplete")
    for world in WORLDS:
        for seed in SEEDS:
            l1 = index[world, seed, "L1"]
            lbudget = index[world, seed, "Lbudget"]
            staged = index[world, seed, "G_to_L"]
            hashed = index[world, seed, "Ghash_to_L"]
            check(l1["planned_pair_visits"] == LOCAL_PAIRS
                  and l1["planned_valid_tokens"] == LOCAL_TOKENS,
                  "L1_budget_mismatch")
            check(lbudget["segment_receipts"][0] == l1["segment_receipts"][0],
                  "L1_first_pass_receipt_mismatch")
            check(staged["planned_pair_visits"] == REFERENCE_PAIRS
                  and staged["planned_valid_tokens"] == REFERENCE_TOKENS
                  and staged["token_budget_shortfall"] == 0,
                  "staged_budget_mismatch")
            check(staged["segment_receipts"] == [
                {"source": "G", "cycle": 0, "optimizer_updates": 74,
                 "pair_visits": GLOBAL_PAIRS, "valid_tokens": GLOBAL_TOKENS},
                {"source": "L", "cycle": 0, "optimizer_updates": 37,
                 "pair_visits": LOCAL_PAIRS, "valid_tokens": LOCAL_TOKENS},
            ], "staged_segment_mismatch")
            for field in (
                "input_sha256", "optimizer_steps", "planned_pair_visits",
                "planned_valid_tokens", "planned_padded_slots", "partial_optimizer_updates",
                "segment_receipts",
            ):
                check(staged[field] == hashed[field], "Ghash_input_or_schedule_mismatch")
            check(staged["plan_sha256"] != hashed["plan_sha256"],
                  "Ghash_target_contract_not_distinct")
            # Effective batch is 128 for both candidate shapes.  Only per-rank
            # packing/padding and the shape-bound hashes may differ.
            other_world = 4 if world == 2 else 2
            for arm in ARMS:
                other = index[other_world, seed, arm]
                for field in (
                    "optimizer_steps", "planned_pair_visits", "planned_valid_tokens",
                    "token_budget_shortfall", "budget_stop_next_pair_tokens",
                    "partial_optimizer_updates", "segment_receipts",
                ):
                    check(index[world, seed, arm][field] == other[field],
                          "cross_shape_effective_batch_accounting_mismatch")

    relations = value.get("cross_arm_relations")
    check(isinstance(relations, list) and len(relations) == 6, "relation_receipt_count_mismatch")
    check({(row.get("world_size"), row.get("seed")) for row in relations}
          == {(world, seed) for world in WORLDS for seed in SEEDS},
          "relation_receipt_matrix_mismatch")
    check(all(row.get("status") == "PASS_CROSS_ARM_INPUT_RELATIONS"
              and row.get("G_and_Ghash_identical_inputs") is True
              and row.get("L1_exact_Lbudget_first_pass") is True for row in relations),
          "relation_receipt_failure")

    replays = value.get("independent_replays")
    check(isinstance(replays, list) and len(replays) == 30, "independent_replay_count_mismatch")
    replay_by_hash = {}
    for row in replays:
        plan_hash = row.get("plan_sha256")
        check(plan_hash not in replay_by_hash, "duplicate_replay_plan_hash")
        replay_by_hash[plan_hash] = row
        check(row.get("status") == "PASS_INDEPENDENT_TOKEN_PLAN_REPLAY_EFFECT_NOT_AUTHORIZED"
              and row.get("model_fits") == row.get("gpu_jobs") == row.get("api_calls") == 0,
              "independent_replay_scope_mismatch")
    check(set(replay_by_hash) == {item["plan_sha256"] for item in plans},
          "independent_replay_plan_set_mismatch")
    for item in plans:
        replay = replay_by_hash[item["plan_sha256"]]
        for field in ("arm", "seed", "optimizer_steps", "planned_pair_visits", "planned_valid_tokens"):
            check(replay.get(field) == item.get(field), "independent_replay_value_mismatch")

    for digest in value.get("source_hashes", {}).values():
        check(re.fullmatch(r"[0-9a-f]{64}", str(digest)) is not None,
              "invalid_source_hash")
    check(value.get("new_train_pool_created") is False
          and value.get("candidate_global_effect_eligible") is False
          and value.get("real_HF_Trainer_DeepSpeed_bf16_integrated") is False
          and value.get("model_weights_loaded") == 0
          and value.get("model_fits") == 0
          and value.get("gpu_jobs") == 0
          and value.get("api_calls") == 0
          and value.get("dev_test_vault_files_opened") == 0
          and value.get("output_contains_card_ids_code_tasks_labels_predictions_or_effects") is False,
          "receipt_scope_mismatch")
    check(value.get("denied_attempts") == {}, "guard_denial_present")
    return {
        "status": "PASS_INDEPENDENT_AGGREGATE_RECEIPT",
        "summary_sha256": sha256(path),
        "plans_verified": 30,
        "cross_arm_relations_verified": 6,
        "independent_plan_replays_bound": 30,
        "model_fits": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "source_data_files_opened": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(
        args.summary.resolve(), args.expect_protocol_sha256,
    ), sort_keys=True))
