from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


class IndependentMarginError(RuntimeError):
    pass


ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SEEDS = (6, 7, 8)
SCORE_NAMES = {f"{arm}|{seed}" for seed in SEEDS for arm in ARMS} | {"tfidf"}
HEX = set("0123456789abcdef")
MAX_LINE_BYTES = 4 * 1024 * 1024
PROTOCOL_NAME = "g-reuse-blinded-margin-materialization-v1"
PARENT_ESCROW_SHA256 = "5384ceae001952d7aee225cebf09c277f7d92e404ec330a4ec436098b29fc55f"


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise IndependentMarginError(reason)


def unique_object(items):
    value = {}
    for key, item in items:
        check(key not in value, "duplicate_key")
        value[key] = item
    return value


def read(path: Path) -> list[dict[str, Any]]:
    check(path.exists() and path.is_file() and not path.is_symlink(), "unsafe_path")
    check(os.stat(path, follow_symlinks=False).st_nlink == 1, "unsafe_link_count")
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        check(len(line.encode("utf-8")) <= MAX_LINE_BYTES, "line_too_long")
        check(bool(line), "blank")
        value = json.loads(line, object_pairs_hook=unique_object)
        check(isinstance(value, dict), "object")
        values.append(value)
    check(bool(values), "empty")
    return values


def validate_protocol(path: Path) -> None:
    check(path.exists() and path.is_file() and not path.is_symlink(), "unsafe_protocol_path")
    check(os.stat(path, follow_symlinks=False).st_nlink == 1, "unsafe_protocol_link_count")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    check(isinstance(value, dict) and value.get("protocol") == PROTOCOL_NAME, "protocol_name")
    check(value.get("status") == "FROZEN_BEFORE_ENDPOINT_SCORE_OR_EFFECT_READOUT", "protocol_status")
    check(value.get("parent_escrow_contract_sha256") == PARENT_ESCROW_SHA256, "parent_contract")
    check(value.get("required_seeded_arms") == list(ARMS), "protocol_arms")
    check(value.get("required_seeds") == list(SEEDS), "protocol_seeds")
    check(value.get("required_unseeded_arms") == ["tfidf"], "protocol_unseeded")
    output = value.get("output_contract")
    check(isinstance(output, dict), "protocol_output")
    check(output.get("margin") == "endpoint_score(left)-endpoint_score(right)", "protocol_margin")
    check(output.get("raw_endpoint_identity_written") is False, "protocol_identity")
    check(output.get("truth_or_outcome_written") is False, "protocol_truth")


def valid_id(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value.encode()) <= 512 and all(ord(c) >= 32 for c in value)


def hash_id(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not (set(value) - HEX)


def recompute(pair_path: Path, score_path: Path) -> list[dict[str, Any]]:
    pairs, score_rows = read(pair_path), read(score_path)
    endpoints, pair_ids = set(), set()
    for pair in pairs:
        check(set(pair) == {"left_endpoint_id", "right_endpoint_id", "pair_sha256",
                            "task_sha256", "parent_sha256", "run_sha256"}, "pair_fields")
        left, right = pair["left_endpoint_id"], pair["right_endpoint_id"]
        check(valid_id(left) and valid_id(right) and left < right, "endpoint_order")
        identity = hashlib.sha256((left + "\0" + right).encode()).hexdigest()
        check(pair["pair_sha256"] == identity and identity not in pair_ids, "pair_identity")
        check(all(hash_id(pair[key]) for key in ("task_sha256", "parent_sha256", "run_sha256")),
              "clusters")
        pair_ids.add(identity); endpoints |= {left, right}
    score_map = {}
    for item in score_rows:
        check(set(item) == {"endpoint_id", "scores"} and valid_id(item["endpoint_id"]), "score_fields")
        check(item["endpoint_id"] not in score_map and isinstance(item["scores"], dict)
              and set(item["scores"]) == SCORE_NAMES, "score_identity")
        check(all(type(number) in (int, float) and math.isfinite(float(number))
                  for number in item["scores"].values()), "finite")
        score_map[item["endpoint_id"]] = item["scores"]
    check(set(score_map) == endpoints, "support")
    expected = []
    for pair in pairs:
        left, right = pair["left_endpoint_id"], pair["right_endpoint_id"]
        expected.append({"pair_sha256": pair["pair_sha256"], "task_sha256": pair["task_sha256"],
                         "parent_sha256": pair["parent_sha256"], "run_sha256": pair["run_sha256"],
                         "margins": {name: float(score_map[left][name]) - float(score_map[right][name])
                                     for name in sorted(SCORE_NAMES)}})
    return sorted(expected, key=lambda item: item["pair_sha256"])


def verify(protocol_path: Path, pair_path: Path, score_path: Path, output_path: Path) -> dict[str, Any]:
    validate_protocol(protocol_path)
    pair_rows = read(pair_path)
    expected, observed = recompute(pair_path, score_path), read(output_path)
    check(observed == expected, "output_mismatch")
    return {"verification_pass": True, "pair_count": len(expected),
            "endpoint_count": len({item["left_endpoint_id"] for item in pair_rows}
                                  | {item["right_endpoint_id"] for item in pair_rows}),
            "raw_endpoint_identity_written": False, "truth_or_outcome_written": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--blinded-pairs", type=Path, required=True)
    parser.add_argument("--endpoint-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.blinded_pairs, args.endpoint_scores, args.output),
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
