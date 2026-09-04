"""Independent anonymous join verification; deliberately does not import the producer join module."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from phase1.verify_g_reuse_effect_readout_statistics import (
    IndependentReadoutError, compare_trees, recompute,
)


class IndependentJoinError(RuntimeError):
    pass


ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SEEDS = (6, 7, 8)
MARGINS = {f"{arm}|{seed}" for arm in ARMS for seed in SEEDS} | {"tfidf"}
PREDICTION_FIELDS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "margins"}
TRUTH_FIELDS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "truth_sign"}
CLUSTERS = ("task_sha256", "parent_sha256", "run_sha256")
READOUT_SHA = "3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5"
ESCROW_SHA = "5384ceae001952d7aee225cebf09c277f7d92e404ec330a4ec436098b29fc55f"
MARGIN_PROTOCOL_SHA = "1b13bd111f074d9f4a703fe2e04a1dc06a46eb3d5dbd329daa85fcd45e122edd"


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise IndependentJoinError(reason)


def sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not (set(value) - set("0123456789abcdef"))


def digest(rows: list[dict[str, Any]]) -> str:
    raw = "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
                  for row in sorted(rows, key=lambda item: item["pair_sha256"])).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_join_protocol(value: dict[str, Any]) -> None:
    check(value.get("protocol") == "g-reuse-anonymous-truth-join-v1", "join_protocol")
    check(value.get("status") == "FROZEN_BEFORE_PROTECTED_TRUTH_READ_NOT_AN_UNSEAL_CALLER",
          "join_status")
    check(value.get("parent_prediction_escrow_contract_sha256") == ESCROW_SHA, "escrow_parent")
    check(value.get("parent_margin_materialization_protocol_sha256") == MARGIN_PROTOCOL_SHA,
          "margin_parent")
    check(value.get("parent_effect_readout_protocol_sha256") == READOUT_SHA, "readout_parent")
    check(value.get("prediction_fields") == ["pair_sha256", "task_sha256", "parent_sha256",
                                              "run_sha256", "margins"], "prediction_contract")
    check(value.get("truth_fields") == ["pair_sha256", "task_sha256", "parent_sha256",
                                         "run_sha256", "truth_sign"], "truth_contract")
    check(value.get("join_contract") == {
        "key": "pair_sha256",
        "prediction_and_truth_pair_support_exactly_equal": True,
        "task_parent_run_sha_must_match_for_each_pair": True,
        "truth_sign_values": [-1, 1],
        "canonical_sort_before_statistics": "pair_sha256",
    }, "join_contract")
    check(value.get("output_contract") == {
        "aggregate_statistics_only": True,
        "joined_rows_written": False,
        "truth_signs_written": False,
        "raw_identifiers_written": False,
        "input_rows_represented_only_by_sha256_and_counts": True,
    }, "output_contract")
    check(value.get("future_caller_order") == [
        "authenticate complete prediction escrow and all checkpoints",
        "authenticate frozen evaluation closure and pristine truth package",
        "join in memory with this kernel",
        "run producer and independent statistics",
        "write aggregate result and verification receipts atomically",
    ], "future_caller_order")
    check(value.get("classification") == "ANONYMOUS_JOIN_KERNEL_READY_NOT_AUTHORIZED_FOR_PRODUCTION_UNSEAL",
          "classification")
    check(value.get("resources") == {"gpu_jobs": 0, "paid_api_calls": 0, "model_fits": 0,
                                      "protected_values_read": 0}, "resources")


def rejoin(predictions: list[dict[str, Any]], truths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prediction_map, truth_map = {}, {}
    for row in predictions:
        check(isinstance(row, dict) and set(row) == PREDICTION_FIELDS, "prediction_fields")
        check(all(sha(row[field]) for field in ("pair_sha256", *CLUSTERS)), "prediction_hash")
        check(row["pair_sha256"] not in prediction_map, "prediction_duplicate")
        check(isinstance(row["margins"], dict) and set(row["margins"]) == MARGINS, "margins")
        check(all(type(value) in (int, float) and math.isfinite(float(value))
                  for value in row["margins"].values()), "finite")
        prediction_map[row["pair_sha256"]] = row
    for row in truths:
        check(isinstance(row, dict) and set(row) == TRUTH_FIELDS, "truth_fields")
        check(all(sha(row[field]) for field in ("pair_sha256", *CLUSTERS)), "truth_hash")
        check(type(row["truth_sign"]) is int and abs(row["truth_sign"]) == 1, "truth_sign")
        check(row["pair_sha256"] not in truth_map, "truth_duplicate")
        truth_map[row["pair_sha256"]] = row
    check(bool(prediction_map) and set(prediction_map) == set(truth_map), "support")
    rows = []
    for pair in sorted(prediction_map):
        left, right = prediction_map[pair], truth_map[pair]
        check(all(left[field] == right[field] for field in CLUSTERS), "clusters")
        rows.append({"pair_sha256": pair, **{field: left[field] for field in CLUSTERS},
                     "truth_sign": right["truth_sign"], "margins": left["margins"]})
    return rows


def verify(predictions: list[dict[str, Any]], truths: list[dict[str, Any]], observed: dict[str, Any],
           join_protocol: dict[str, Any], readout_protocol: dict[str, Any],
           join_protocol_sha256: str) -> dict[str, Any]:
    validate_join_protocol(join_protocol)
    check(sha(join_protocol_sha256), "join_protocol_sha")
    rows = rejoin(predictions, truths)
    check(observed.get("protocol") == "g-reuse-anonymous-truth-join-result-v1", "result_protocol")
    check(observed.get("join_protocol_sha256") == join_protocol_sha256, "result_join_protocol")
    check(observed.get("effect_readout_protocol_sha256") == READOUT_SHA, "result_readout_protocol")
    check(observed.get("prediction_rows_canonical_sha256") == digest(predictions), "prediction_digest")
    check(observed.get("truth_rows_canonical_sha256") == digest(truths), "truth_digest")
    check(observed.get("pair_count") == len(rows), "pair_count")
    check(observed.get("task_count") == len({row["task_sha256"] for row in rows}), "task_count")
    try:
        expected_statistics = recompute(rows, readout_protocol)
        maximum = compare_trees(observed.get("statistics"), expected_statistics, "$.statistics")
    except IndependentReadoutError as exc:
        raise IndependentJoinError("statistics_mismatch") from exc
    check(observed.get("status") == expected_statistics["status"], "status")
    check(observed.get("scope") == {"joined_rows_written": False, "truth_signs_written": False,
                                    "raw_identifiers_written": False, "opens_or_authorizes_vault": False},
          "scope")
    return {"verification_pass": True, "pair_count": len(rows),
            "maximum_numeric_absolute_difference": maximum,
            "joined_rows_written": False, "truth_signs_written": False}
