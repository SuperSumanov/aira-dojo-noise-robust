#!/usr/bin/env python3
"""Recover and verify the locked ``ac008af`` mixed-pair generation recipe.

The recovery search is intentionally narrow and frozen.  It compares parsed
JSON-object sequences for 66 simple candidate recipes, requires exactly one
match, then requires the independently reconstructed UTF-8/LF bytes to equal
the locked Git-LFS object byte for byte.

This is a retrospective reproducibility audit.  It reads the four historical
pair JSONL objects, including their pair-construction metadata, but it never
opens Cards, source code payloads, raw grades, prospective outcome vaults,
checkpoints, or model predictions.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import sys
from typing import Any, Iterable, Iterator, Mapping, Sequence


PROTOCOL = "senior-mixed-recipe-recovery-v1"
SOURCE_COMMIT = "ac008af8b907d319b694f26b0ba9cf4053b3bf69"
BUILDER_RELATIVE_PATH = "src/mle_critic/src/postprocess/build_decision_augment_pairs.py"
BUILDER_GIT_BLOB_SHA1 = "2b92e447065fdd6948d916882ed08b8910bc352f"
BUILDER_LF_SHA256 = "e7302d5fe7b914682b3327ea23022d2560fb54c348ed80e6fe40a5a065e71e63"
SEED = 7
N_SAMPLES = 15_000
DECISION_COUNT = 1_500
GLOBAL_COUNTS = tuple(range(0, 7_501, 750))
DATASET_NAMES = ("local_batch_value", "decision", "global_hardware_time_value")
EXPECTED_ORDER = DATASET_NAMES
EXPECTED_COUNTS = {
    "local_batch_value": 12_000,
    "decision": 1_500,
    "global_hardware_time_value": 1_500,
}
EXPECTED_WEIGHTS = (8.0, 1.0, 1.0)
USE_TEST_DATASET = "decision"

LOCKED_FILES: dict[str, dict[str, Any]] = {
    "target": {
        "filename": "decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl",
        "sha256": "7792a7da4119bb607cf76628fcdde19923898651ac734ff6afffb0732883cf6e",
        "bytes": 6_625_497,
    },
    "decision": {
        "filename": "merged_decision_pairs_filtered_runsplit.jsonl",
        "sha256": "1a01d3a1202b35f21b9cd6c87237b29c50b1c293138b407cc453674108411442",
        "bytes": 3_337_808,
    },
    "global_hardware_time_value": {
        "filename": "value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl",
        "sha256": "60e9bbfba56ef94dfd70bb717694fa5b3b400f9458a13b92321bb1cb2ecdf3d9",
        "bytes": 3_807_175,
    },
    "local_batch_value": {
        "filename": "batch_value_pairs_filtered_runsplit.jsonl",
        "sha256": "8a01dfb90c2c3d8498174ebe78df43ee21d6d0eac9f4ff81f63700b315473405",
        "bytes": 7_223_244,
    },
}

CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class RecoveryError(RuntimeError):
    """Raised when any locked recovery condition fails closed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def canonical_receipt_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def rows_sha256(rows: Iterable[dict[str, Any]]) -> str:
    payload = "".join(canonical_receipt_json(row) + "\n" for row in rows).encode("utf-8")
    return sha256_bytes(payload)


def builder_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    """Serialize exactly as the locked upstream builder does on Linux."""

    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def checked_regular_file(path_value: str | Path, label: str) -> tuple[Path, bytes]:
    path = Path(path_value).resolve()
    if not path.is_file() or path.is_symlink():
        raise RecoveryError(f"{label} is absent, symlinked, or non-regular")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise RecoveryError(f"credential-shaped bytes refused in {label}")
    return path, raw


def checked_locked_jsonl(
    path_value: str | Path,
    label: str,
    expected_sha256: str,
    expected_bytes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    path, raw = checked_regular_file(path_value, label)
    actual_sha256 = sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise RecoveryError(f"SHA-256 mismatch for {label}")
    if len(raw) != expected_bytes:
        raise RecoveryError(f"byte-size mismatch for {label}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecoveryError(f"non-UTF-8 bytes in {label}") from exc

    rows: list[dict[str, Any]] = []
    key_union: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecoveryError(f"invalid JSON in {label} at line {line_number}") from exc
        if not isinstance(row, dict):
            raise RecoveryError(f"non-object row in {label} at line {line_number}")
        for field in ("better", "worse", "intask_split"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise RecoveryError(f"invalid {field} in {label} at line {line_number}")
        if row["intask_split"] not in {"train", "test"}:
            raise RecoveryError(f"unsupported split in {label} at line {line_number}")
        key_union.update(row)
        rows.append(row)
    if not rows:
        raise RecoveryError(f"empty JSONL object: {label}")
    metadata = {
        "filename": LOCKED_FILES[label]["filename"],
        "sha256": actual_sha256,
        "bytes": len(raw),
        "rows": len(rows),
        "train_rows": sum(row["intask_split"] == "train" for row in rows),
        "test_rows": sum(row["intask_split"] == "test" for row in rows),
        "field_names": sorted(key_union),
    }
    return rows, metadata, raw


def checked_builder_source(path_value: str | Path) -> dict[str, Any]:
    _, raw = checked_regular_file(path_value, "builder_source")
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise RecoveryError("builder source contains unsupported lone CR bytes")
    if sha256_bytes(normalized) != BUILDER_LF_SHA256:
        raise RecoveryError("builder normalized-LF SHA-256 mismatch")
    if git_blob_sha1(normalized) != BUILDER_GIT_BLOB_SHA1:
        raise RecoveryError("builder Git blob SHA-1 mismatch")
    return {
        "relative_path": BUILDER_RELATIVE_PATH,
        "git_blob_sha1": BUILDER_GIT_BLOB_SHA1,
        "normalized_lf_sha256": BUILDER_LF_SHA256,
        "normalized_lf_bytes": len(normalized),
    }


def allocate_counts(total: int, weights: Sequence[float]) -> list[int]:
    weight_sum = sum(weights)
    exact = [total * weight / weight_sum for weight in weights]
    counts = [int(value) for value in exact]
    remainder = total - sum(counts)
    for index in sorted(
        range(len(weights)),
        key=lambda index: exact[index] - counts[index],
        reverse=True,
    )[:remainder]:
        counts[index] += 1
    return counts


def deduplicate_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    unique: list[dict[str, Any]] = []
    for row in records:
        key = (row["better"], row["worse"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def simulate_builder(
    datasets: Mapping[str, Sequence[dict[str, Any]]],
    order: Sequence[str],
    counts: Mapping[str, int],
    seed: int,
    use_test_dataset: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    sample_pools = {
        name: [row for row in datasets[name] if row.get("intask_split") == "train"]
        for name in order
    }
    test_rows = [
        row
        for row in datasets[use_test_dataset]
        if row.get("intask_split") == "test"
    ]
    rng = random.Random(seed)
    sampled: list[dict[str, Any]] = []
    for name in order:
        count = counts[name]
        if count > len(sample_pools[name]):
            raise RecoveryError(f"candidate overdraws {name}")
        sampled.extend(rng.sample(sample_pools[name], count))
    rng.shuffle(sampled)

    unique_test = deduplicate_records(test_rows)
    test_keys = {(row["better"], row["worse"]) for row in unique_test}
    unique_sampled = [
        row
        for row in deduplicate_records(sampled)
        if (row["better"], row["worse"]) not in test_keys
    ]
    return unique_sampled + unique_test, {
        "requested_sampled": len(sampled),
        "unique_sampled": len(unique_sampled),
        "retained_test": len(unique_test),
    }


def candidate_specs() -> Iterator[tuple[tuple[str, ...], dict[str, int]]]:
    """Yield the frozen 6-order x 11-allocation search grid."""

    for order in itertools.permutations(DATASET_NAMES):
        for global_count in GLOBAL_COUNTS:
            yield order, {
                "decision": DECISION_COUNT,
                "global_hardware_time_value": global_count,
                "local_batch_value": N_SAMPLES - DECISION_COUNT - global_count,
            }


def find_exact_matches(
    datasets: Mapping[str, Sequence[dict[str, Any]]],
    target: Sequence[dict[str, Any]],
    specs: Iterable[tuple[tuple[str, ...], dict[str, int]]],
    seed: int,
    use_test_dataset: str,
) -> tuple[
    list[tuple[tuple[str, ...], dict[str, int], list[dict[str, Any]], dict[str, int]]],
    int,
]:
    exact_matches: list[
        tuple[tuple[str, ...], dict[str, int], list[dict[str, Any]], dict[str, int]]
    ] = []
    searched = 0
    for order, counts in specs:
        output, trace = simulate_builder(
            datasets, order, counts, seed, use_test_dataset
        )
        searched += 1
        if output == target:
            exact_matches.append((order, counts, output, trace))
    return exact_matches, searched


def source_count(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("src", "<missing>")) for row in rows)
    return dict(sorted(counts.items()))


def build_command() -> list[str]:
    return [
        "python",
        BUILDER_RELATIVE_PATH,
        "--datasets",
        LOCKED_FILES["local_batch_value"]["filename"],
        LOCKED_FILES["decision"]["filename"],
        LOCKED_FILES["global_hardware_time_value"]["filename"],
        "--weights",
        "8",
        "1",
        "1",
        "--n-samples",
        str(N_SAMPLES),
        "--output-path",
        LOCKED_FILES["target"]["filename"],
        "--use-test-split",
        LOCKED_FILES["decision"]["filename"],
        "--seed",
        str(SEED),
    ]


def recover(
    target_path: str | Path,
    decision_path: str | Path,
    global_value_path: str | Path,
    local_value_path: str | Path,
    builder_source_path: str | Path,
) -> dict[str, Any]:
    path_by_name = {
        "target": target_path,
        "decision": decision_path,
        "global_hardware_time_value": global_value_path,
        "local_batch_value": local_value_path,
    }
    loaded: dict[str, list[dict[str, Any]]] = {}
    input_metadata: dict[str, dict[str, Any]] = {}
    locked_raw: dict[str, bytes] = {}
    for label, path in path_by_name.items():
        spec = LOCKED_FILES[label]
        loaded[label], input_metadata[label], locked_raw[label] = checked_locked_jsonl(
            path, label, spec["sha256"], spec["bytes"]
        )
    builder_metadata = checked_builder_source(builder_source_path)

    datasets = {name: loaded[name] for name in DATASET_NAMES}
    exact_matches, searched = find_exact_matches(
        datasets,
        loaded["target"],
        candidate_specs(),
        SEED,
        USE_TEST_DATASET,
    )

    if searched != 66:
        raise RecoveryError(f"frozen search grid changed: {searched} candidates")
    if len(exact_matches) != 1:
        raise RecoveryError(
            f"expected one parsed-sequence match, found {len(exact_matches)}"
        )
    order, counts, output, trace = exact_matches[0]
    if order != EXPECTED_ORDER or counts != EXPECTED_COUNTS:
        raise RecoveryError("unique match differs from the pre-attested recovered recipe")
    if allocate_counts(N_SAMPLES, EXPECTED_WEIGHTS) != [counts[name] for name in order]:
        raise RecoveryError("weights do not allocate the recovered sample counts")

    reconstructed = builder_bytes(output)
    target_raw = locked_raw["target"]
    if reconstructed != target_raw:
        raise RecoveryError("parsed rows match but reconstructed bytes do not")
    if sha256_bytes(reconstructed) != LOCKED_FILES["target"]["sha256"]:
        raise RecoveryError("reconstructed output SHA-256 mismatch")

    output_splits = Counter(row["intask_split"] for row in output)
    output_sources = source_count(output)
    recipe_datasets = [LOCKED_FILES[name]["filename"] for name in order]
    receipt = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "formal_status": "UNIQUE_IN_FROZEN_GRID_AND_BYTE_EXACT",
        "source_commit": SOURCE_COMMIT,
        "builder": builder_metadata,
        "locks": input_metadata,
        "search": {
            "definition": (
                "all 6 dataset orders; seed=7; n_samples=15000; decision=1500; "
                "global=0..7500 step 750; local=13500-global"
            ),
            "candidate_count": searched,
            "parsed_sequence_exact_matches": len(exact_matches),
            "global_count_grid": list(GLOBAL_COUNTS),
            "claim_boundary": "unique only within this frozen 66-candidate grid",
        },
        "recovered_recipe": {
            "dataset_order": recipe_datasets,
            "weights": [8, 1, 1],
            "sample_counts": [counts[name] for name in order],
            "n_samples": N_SAMPLES,
            "use_test_split": LOCKED_FILES[USE_TEST_DATASET]["filename"],
            "seed": SEED,
            "command_argv": build_command(),
        },
        "output": {
            "filename": LOCKED_FILES["target"]["filename"],
            "sha256": sha256_bytes(reconstructed),
            "bytes": len(reconstructed),
            "rows": len(output),
            "split_counts": dict(sorted(output_splits.items())),
            "source_counts": output_sources,
            "requested_sampled": trace["requested_sampled"],
            "unique_sampled": trace["unique_sampled"],
            "retained_test": trace["retained_test"],
            "parsed_sequence_equal": output == loaded["target"],
            "serialized_bytes_equal": reconstructed == target_raw,
            "canonical_rows_sha256": rows_sha256(output),
        },
        "runtime": {
            "python_version": sys.version.split()[0],
            "os_name": os.name,
        },
        "access_attestation": {
            "historical_pair_jsonl_objects_read_in_full": True,
            "pair_construction_metadata_including_gap_raw_read": True,
            "cards_or_solution_code_opened": False,
            "raw_grades_opened": False,
            "prospective_outcome_vault_opened": False,
            "checkpoints_or_model_predictions_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
        },
    }
    scientific_core = {
        key: receipt[key]
        for key in (
            "protocol",
            "formal_status",
            "source_commit",
            "builder",
            "locks",
            "search",
            "recovered_recipe",
            "output",
        )
    }
    receipt["scientific_core_sha256"] = rows_sha256([scientific_core])
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--global-value", type=Path, required=True)
    parser.add_argument("--local-value", type=Path, required=True)
    parser.add_argument("--builder-source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = recover(
        args.target,
        args.decision,
        args.global_value,
        args.local_value,
        args.builder_source,
    )
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
