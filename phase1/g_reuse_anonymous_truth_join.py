"""In-memory anonymous join kernel; this module does not open or authorize a truth vault."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from phase1.g_reuse_effect_readout_statistics import evaluate, margin_keys, validate_protocol as validate_readout


class AnonymousJoinError(RuntimeError):
    pass


JOIN_PROTOCOL = "g-reuse-anonymous-truth-join-v1"
READOUT_SHA = "3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5"
JOIN_SHA = "d6a0540b3a78cae15827d88dddb2419bef599be2fdf936e51abb74201212d7f9"
ESCROW_SHA = "5384ceae001952d7aee225cebf09c277f7d92e404ec330a4ec436098b29fc55f"
MARGIN_PROTOCOL_SHA = "1b13bd111f074d9f4a703fe2e04a1dc06a46eb3d5dbd329daa85fcd45e122edd"
PREDICTION_FIELDS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "margins"}
TRUTH_FIELDS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "truth_sign"}
PREDICTION_FIELD_ORDER = ["pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "margins"]
TRUTH_FIELD_ORDER = ["pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "truth_sign"]
CLUSTERS = ("task_sha256", "parent_sha256", "run_sha256")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise AnonymousJoinError(reason)


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not (set(value) - set("0123456789abcdef"))


def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "duplicate_protocol_key")
        value[key] = item
    return value


def protocol_object(raw: bytes, expected_sha256: str, reason: str) -> dict[str, Any]:
    require(isinstance(raw, bytes) and 0 < len(raw) <= 100_000, reason + "_bytes")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, reason + "_sha")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnonymousJoinError(reason + "_json") from exc
    require(isinstance(value, dict), reason + "_object")
    return value


def validate_join_protocol(value: dict[str, Any]) -> None:
    require(value.get("protocol") == JOIN_PROTOCOL, "protocol")
    require(value.get("status") == "FROZEN_BEFORE_PROTECTED_TRUTH_READ_NOT_AN_UNSEAL_CALLER", "status")
    require(value.get("parent_prediction_escrow_contract_sha256") == ESCROW_SHA, "escrow_parent")
    require(value.get("parent_margin_materialization_protocol_sha256") == MARGIN_PROTOCOL_SHA, "margin_parent")
    require(value.get("parent_effect_readout_protocol_sha256") == READOUT_SHA, "readout_parent")
    require(value.get("prediction_fields") == PREDICTION_FIELD_ORDER, "prediction_contract")
    require(value.get("truth_fields") == TRUTH_FIELD_ORDER, "truth_contract")
    require(value.get("join_contract") == {
        "key": "pair_sha256",
        "prediction_and_truth_pair_support_exactly_equal": True,
        "task_parent_run_sha_must_match_for_each_pair": True,
        "truth_sign_values": [-1, 1],
        "canonical_sort_before_statistics": "pair_sha256",
    }, "join_contract")
    require(value.get("output_contract") == {
        "aggregate_statistics_only": True,
        "joined_rows_written": False,
        "truth_signs_written": False,
        "raw_identifiers_written": False,
        "input_rows_represented_only_by_sha256_and_counts": True,
    }, "output_contract")
    require(value.get("future_caller_order") == [
        "authenticate complete prediction escrow and all checkpoints",
        "authenticate frozen evaluation closure and pristine truth package",
        "join in memory with this kernel",
        "run producer and independent statistics",
        "write aggregate result and verification receipts atomically",
    ], "future_caller_order")
    require(value.get("classification") == "ANONYMOUS_JOIN_KERNEL_READY_NOT_AUTHORIZED_FOR_PRODUCTION_UNSEAL",
            "classification")
    require(value.get("resources") == {"gpu_jobs": 0, "paid_api_calls": 0, "model_fits": 0,
                                        "protected_values_read": 0}, "resources")


def canonical_digest(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: row["pair_sha256"])
    raw = "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
                  for row in ordered).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def anonymous_rows(predictions: list[dict[str, Any]], truths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require(bool(predictions) and bool(truths), "empty")
    prediction_map: dict[str, dict[str, Any]] = {}
    truth_map: dict[str, dict[str, Any]] = {}
    expected_margins = margin_keys()
    for row in predictions:
        require(isinstance(row, dict) and set(row) == PREDICTION_FIELDS, "prediction_schema")
        require(all(is_sha(row[field]) for field in ("pair_sha256", *CLUSTERS)), "prediction_sha")
        require(row["pair_sha256"] not in prediction_map, "duplicate_prediction")
        require(isinstance(row["margins"], dict) and set(row["margins"]) == expected_margins,
                "margin_schema")
        require(all(type(value) in (int, float) and math.isfinite(float(value))
                    for value in row["margins"].values()), "margin_value")
        prediction_map[row["pair_sha256"]] = row
    for row in truths:
        require(isinstance(row, dict) and set(row) == TRUTH_FIELDS, "truth_schema")
        require(all(is_sha(row[field]) for field in ("pair_sha256", *CLUSTERS)), "truth_sha")
        require(type(row["truth_sign"]) is int and row["truth_sign"] in (-1, 1), "truth_sign")
        require(row["pair_sha256"] not in truth_map, "duplicate_truth")
        truth_map[row["pair_sha256"]] = row
    require(set(prediction_map) == set(truth_map), "pair_support")
    joined = []
    for pair_sha in sorted(prediction_map):
        prediction, truth = prediction_map[pair_sha], truth_map[pair_sha]
        require(all(prediction[field] == truth[field] for field in CLUSTERS), "cluster_binding")
        joined.append({"pair_sha256": pair_sha, **{field: prediction[field] for field in CLUSTERS},
                       "truth_sign": truth["truth_sign"],
                       "margins": {key: float(value) for key, value in prediction["margins"].items()}})
    return joined


def compose(predictions: list[dict[str, Any]], truths: list[dict[str, Any]],
            join_protocol_raw: bytes, readout_protocol_raw: bytes) -> dict[str, Any]:
    join_protocol = protocol_object(join_protocol_raw, JOIN_SHA, "join_protocol")
    readout_protocol = protocol_object(readout_protocol_raw, READOUT_SHA, "readout_protocol")
    validate_join_protocol(join_protocol)
    validate_readout(readout_protocol)
    rows = anonymous_rows(predictions, truths)
    statistics = evaluate(rows, readout_protocol)
    return {
        "protocol": "g-reuse-anonymous-truth-join-result-v1",
        "status": statistics["status"],
        "join_protocol_sha256": JOIN_SHA,
        "effect_readout_protocol_sha256": READOUT_SHA,
        "prediction_rows_canonical_sha256": canonical_digest(predictions),
        "truth_rows_canonical_sha256": canonical_digest(truths),
        "pair_count": len(rows),
        "task_count": len({row["task_sha256"] for row in rows}),
        "statistics": statistics,
        "scope": {"joined_rows_written": False, "truth_signs_written": False,
                  "raw_identifiers_written": False, "opens_or_authorizes_vault": False},
    }
