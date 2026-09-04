from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


class MarginMaterializationError(RuntimeError):
    pass


ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SEEDS = (6, 7, 8)
PAIR_KEYS = {"left_endpoint_id", "right_endpoint_id", "pair_sha256", "task_sha256", "parent_sha256", "run_sha256"}
SCORE_KEYS = {f"{arm}|{seed}" for arm in ARMS for seed in SEEDS} | {"tfidf"}
HEX = set("0123456789abcdef")
PROTOCOL_NAME = "g-reuse-blinded-margin-materialization-v1"
PARENT_ESCROW_SHA256 = "5384ceae001952d7aee225cebf09c277f7d92e404ec330a4ec436098b29fc55f"
MAX_LINE_BYTES = 4 * 1024 * 1024


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise MarginMaterializationError(reason)


def no_duplicates(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha_shape(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not (set(value) - HEX)


def endpoint_id(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value.encode("utf-8")) <= 512 and all(ord(c) >= 32 for c in value)


def safe_regular_file(path: Path) -> None:
    require(path.exists() and path.is_file() and not path.is_symlink(), "unsafe_input_path")
    require(os.stat(path, follow_symlinks=False).st_nlink == 1, "unsafe_input_link_count")


def load_protocol(path: Path) -> dict[str, Any]:
    safe_regular_file(path)
    raw = path.read_text(encoding="utf-8")
    value = json.loads(raw, object_pairs_hook=no_duplicates)
    require(isinstance(value, dict), "protocol_object")
    require(value.get("protocol") == PROTOCOL_NAME, "protocol_name")
    require(value.get("status") == "FROZEN_BEFORE_ENDPOINT_SCORE_OR_EFFECT_READOUT", "protocol_status")
    require(value.get("parent_escrow_contract_sha256") == PARENT_ESCROW_SHA256, "parent_contract")
    require(value.get("required_seeded_arms") == list(ARMS), "protocol_arms")
    require(value.get("required_seeds") == list(SEEDS), "protocol_seeds")
    require(value.get("required_unseeded_arms") == ["tfidf"], "protocol_unseeded")
    output = value.get("output_contract")
    require(isinstance(output, dict), "protocol_output")
    require(output.get("margin") == "endpoint_score(left)-endpoint_score(right)", "protocol_margin")
    require(output.get("raw_endpoint_identity_written") is False, "protocol_identity")
    require(output.get("truth_or_outcome_written") is False, "protocol_truth")
    return value


def rows(path: Path) -> list[dict[str, Any]]:
    safe_regular_file(path)
    result = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            require(len(line.encode("utf-8")) <= MAX_LINE_BYTES, "line_too_long")
            require(bool(line.strip()), "blank_row")
            value = json.loads(line, object_pairs_hook=no_duplicates)
            require(isinstance(value, dict), "row_object")
            result.append(value)
    require(bool(result), "empty_file")
    return result


def materialize(pair_path: Path, score_path: Path) -> list[dict[str, Any]]:
    pair_rows = rows(pair_path)
    score_rows = rows(score_path)
    seen_pairs, required_endpoints = set(), set()
    for row in pair_rows:
        require(set(row) == PAIR_KEYS, "pair_schema")
        left, right = row["left_endpoint_id"], row["right_endpoint_id"]
        require(endpoint_id(left) and endpoint_id(right) and left < right, "canonical_endpoints")
        expected = sha(left + "\0" + right)
        require(row["pair_sha256"] == expected and expected not in seen_pairs, "pair_hash_or_duplicate")
        require(all(sha_shape(row[key]) for key in
                    ("task_sha256", "parent_sha256", "run_sha256")), "cluster_sha")
        seen_pairs.add(expected); required_endpoints.update((left, right))
    scores = {}
    for row in score_rows:
        require(set(row) == {"endpoint_id", "scores"} and endpoint_id(row["endpoint_id"]), "score_schema")
        require(row["endpoint_id"] not in scores, "duplicate_endpoint_score")
        values = row["scores"]
        require(isinstance(values, dict) and set(values) == SCORE_KEYS, "score_matrix")
        require(all(type(value) in (int, float) and math.isfinite(float(value))
                    for value in values.values()), "score_value")
        scores[row["endpoint_id"]] = {key: float(value) for key, value in values.items()}
    require(set(scores) == required_endpoints, "endpoint_support")
    output = []
    for pair in pair_rows:
        left, right = pair["left_endpoint_id"], pair["right_endpoint_id"]
        output.append({
            "pair_sha256": pair["pair_sha256"], "task_sha256": pair["task_sha256"],
            "parent_sha256": pair["parent_sha256"], "run_sha256": pair["run_sha256"],
            "margins": {key: scores[left][key] - scores[right][key] for key in sorted(SCORE_KEYS)},
        })
    return sorted(output, key=lambda row: row["pair_sha256"])


def write(path: Path, output: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in output:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--blinded-pairs", type=Path, required=True)
    parser.add_argument("--endpoint-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_protocol(args.protocol)
    write(args.output, materialize(args.blinded_pairs, args.endpoint_scores))


if __name__ == "__main__":
    main()
