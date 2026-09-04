from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath


class EscrowError(RuntimeError):
    pass


ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SEEDS = (6, 7, 8)
ROLES = {"pair_predictions", "checkpoint_manifest", "access_receipt", "summary"}
HEX64 = re.compile(r"[0-9a-f]{64}")
SECRET = re.compile(
    rb"(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})"
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise EscrowError(reason)


def no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def json_object(path: Path, cap: int = 2_000_000) -> tuple[dict, bytes]:
    require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, "unsafe_json")
    raw = path.read_bytes()
    require(0 < len(raw) <= cap and not SECRET.search(raw), "json_size_or_credential")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    require(isinstance(value, dict), "json_object")
    return value, raw


def safe_file(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and "\\" not in relative, "path_shape")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and relative == pure.as_posix() and ".." not in pure.parts, "path_escape")
    current = root
    for part in pure.parts:
        current = current / part
        require(not current.is_symlink(), "symlink")
    resolved = current.resolve(strict=True)
    require(resolved.is_relative_to(root) and resolved.is_file() and resolved.stat().st_nlink == 1,
            "unsafe_artifact")
    return resolved


def load_contract(path: Path) -> tuple[dict, str]:
    contract, raw = json_object(path)
    require(contract.get("protocol") == "g-reuse-prediction-escrow-contract-v1", "contract_protocol")
    require(contract.get("status") == "FROZEN_BEFORE_MODEL_EFFECT_NOT_A_SCORER", "contract_status")
    require(contract.get("parent_effect_protocol_sha256")
            == "2e95b73ca6a21c45502bc64919dd1dc5f447bd5f21f61f939dbbcfd97f080ed5",
            "effect_parent")
    require(contract.get("parent_readout_protocol_sha256")
            == "3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5",
            "readout_parent")
    require(contract.get("required_artifacts")
            == ["pair_predictions", "checkpoint_manifest", "access_receipt", "summary"],
            "contract_roles")
    rows = contract.get("prediction_rows", {})
    require(rows.get("required_seeded_arms") == list(ARMS) and rows.get("required_seeds") == list(SEEDS),
            "contract_arms")
    require(rows.get("required_unseeded_arms") == ["tfidf"]
            and rows.get("truth_label_fields_allowed") is False
            and rows.get("raw_identity_fields_allowed") is False, "contract_blinding")
    checkpoint = contract.get("checkpoint_gate", {})
    require(checkpoint.get("expected_checkpoints") == 15
            and checkpoint.get("all_final_steps_and_hashes_locked_before_scoring") is True
            and checkpoint.get("dev_or_test_selected_checkpoint_allowed") is False
            and checkpoint.get("incomplete_nan_oom_or_access_violation_allowed") is False,
            "contract_checkpoints")
    require(contract.get("access_gate") == {
        "model_process_reads_only_blinded_pairs_cards_and_locked_checkpoints": True,
        "label_outcome_vault_or_oriented_pair_reads_allowed": False,
        "accuracy_or_utility_computed": False,
        "receipt_is_hash_bound_self_attestation_not_os_level_proof": True,
    }, "contract_access")
    require(contract.get("classification") == "PREDICTION_ESCROW_HASH_BOUND_NOT_EFFECT_READOUT_ELIGIBLE",
            "contract_classification")
    require(contract.get("resources") == {"validator_gpu_jobs": 0, "validator_api_calls": 0,
                                           "validator_model_fits": 0,
                                           "validator_protected_values_read": 0}, "contract_resources")
    return contract, hashlib.sha256(raw).hexdigest()


def pair_rows(path: Path) -> tuple[list[dict], str]:
    require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, "unsafe_pairs")
    expected_margins = {f"{arm}|{seed}" for arm in ARMS for seed in SEEDS} | {"tfidf"}
    expected = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "margins"}
    rows, seen = [], set()
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, 1):
            require(raw.strip() and len(raw) <= 1_000_000 and not SECRET.search(raw), "pair_row_shape")
            row = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
            require(isinstance(row, dict) and set(row) == expected, "pair_schema")
            require(all(isinstance(row[key], str) and HEX64.fullmatch(row[key])
                        for key in ("pair_sha256", "task_sha256", "parent_sha256", "run_sha256")),
                    "pair_identifier")
            require(row["pair_sha256"] not in seen, "duplicate_pair")
            seen.add(row["pair_sha256"])
            margins = row["margins"]
            require(isinstance(margins, dict) and set(margins) == expected_margins, "margin_schema")
            require(all(type(value) in (int, float) and math.isfinite(float(value))
                        for value in margins.values()), "margin_value")
            rows.append(row)
    require(rows, "empty_pairs")
    return rows, digest(path)


def validate(root: Path, contract_path: Path, manifest_path: Path) -> dict:
    require(root.is_dir() and not root.is_symlink(), "root")
    root = root.resolve(strict=True)
    contract, contract_sha = load_contract(contract_path)
    require(manifest_path.resolve(strict=True).is_relative_to(root), "manifest_outside")
    manifest, manifest_raw = json_object(manifest_path)
    require(set(manifest) == {"protocol", "contract_sha256", "artifacts"}, "manifest_schema")
    require(manifest["protocol"] == "g-reuse-prediction-escrow-manifest-v1"
            and manifest["contract_sha256"] == contract_sha, "manifest_binding")
    artifacts = manifest["artifacts"]
    require(isinstance(artifacts, list) and len(artifacts) == len(ROLES), "artifact_count")
    paths, roles, inodes = {}, set(), set()
    for item in artifacts:
        require(isinstance(item, dict) and set(item) == {"role", "path", "bytes", "sha256"},
                "artifact_schema")
        require(item["role"] in ROLES and item["role"] not in roles, "artifact_role")
        require(type(item["bytes"]) is int and item["bytes"] > 0 and HEX64.fullmatch(item["sha256"] or ""),
                "artifact_receipt")
        path = safe_file(root, item["path"])
        stat = path.stat()
        require((stat.st_dev, stat.st_ino) not in inodes, "artifact_alias")
        require(stat.st_size == item["bytes"] and digest(path) == item["sha256"], "artifact_drift")
        roles.add(item["role"]); inodes.add((stat.st_dev, stat.st_ino)); paths[item["role"]] = path
    require(roles == ROLES, "roles")

    checkpoints, checkpoint_raw = json_object(paths["checkpoint_manifest"])
    require(set(checkpoints) == {"protocol", "checkpoints"}
            and checkpoints["protocol"] == "g-reuse-locked-checkpoints-v1", "checkpoint_manifest")
    items = checkpoints["checkpoints"]
    require(isinstance(items, list) and len(items) == 15, "checkpoint_count")
    expected = {(arm, seed) for arm in ARMS for seed in SEEDS}
    observed = set()
    for item in items:
        require(isinstance(item, dict) and set(item) == {
            "arm", "seed", "checkpoint_sha256", "training_manifest_sha256", "config_sha256",
            "final_optimizer_step", "complete", "selection_metric_read", "frozen_evaluation_read"
        }, "checkpoint_schema")
        require(item["arm"] in ARMS and type(item["seed"]) is int and item["seed"] in SEEDS,
                "checkpoint_identity")
        observed.add((item["arm"], item["seed"]))
        require(all(isinstance(item[key], str) and HEX64.fullmatch(item[key]) for key in
                    ("checkpoint_sha256", "training_manifest_sha256", "config_sha256")), "checkpoint_hash")
        require(type(item["final_optimizer_step"]) is int and item["final_optimizer_step"] > 0
                and item["complete"] is True and item["selection_metric_read"] is False
                and item["frozen_evaluation_read"] is False, "checkpoint_state")
    require(observed == expected, "checkpoint_matrix")

    access, access_raw = json_object(paths["access_receipt"])
    require(set(access) == {"protocol", "blinded_pair_manifest_sha256", "cards_sha256",
                            "checkpoint_manifest_sha256", "model_process_label_reads",
                            "model_process_outcome_reads", "model_process_forbidden_open_count",
                            "accuracy_computed", "utility_computed", "raw_identity_output"}, "access_schema")
    require(access["protocol"] == "g-reuse-model-access-receipt-v1"
            and all(isinstance(access[key], str) and HEX64.fullmatch(access[key]) for key in
                    ("blinded_pair_manifest_sha256", "cards_sha256", "checkpoint_manifest_sha256"))
            and access["checkpoint_manifest_sha256"] == hashlib.sha256(checkpoint_raw).hexdigest()
            and all(type(access[key]) is int for key in
                    ("model_process_label_reads", "model_process_outcome_reads",
                     "model_process_forbidden_open_count"))
            and access["model_process_label_reads"] == access["model_process_outcome_reads"]
            == access["model_process_forbidden_open_count"] == 0
            and access["accuracy_computed"] is access["utility_computed"] is access["raw_identity_output"] is False,
            "access_gate")

    rows, rows_sha = pair_rows(paths["pair_predictions"])
    summary, summary_raw = json_object(paths["summary"])
    require(set(summary) == {"protocol", "status", "contract_sha256", "source_package_manifest_sha256",
                             "blinded_pair_manifest_sha256", "checkpoint_manifest_sha256",
                             "access_receipt_sha256", "pair_predictions_sha256", "tfidf_receipt_sha256",
                             "pair_count", "task_count", "arms", "seeds", "accuracy_computed",
                             "labels_read", "outcomes_read", "utility_computed"}, "summary_schema")
    require(summary["protocol"] == "g-reuse-prediction-escrow-v1"
            and summary["status"] == "G_REUSE_PREDICTION_ESCROW_COMPLETE_OUTCOME_BLIND"
            and summary["contract_sha256"] == contract_sha
            and summary["checkpoint_manifest_sha256"] == hashlib.sha256(checkpoint_raw).hexdigest()
            and summary["access_receipt_sha256"] == hashlib.sha256(access_raw).hexdigest()
            and summary["pair_predictions_sha256"] == rows_sha
            and summary["blinded_pair_manifest_sha256"] == access["blinded_pair_manifest_sha256"]
            and all(isinstance(summary[key], str) and HEX64.fullmatch(summary[key]) for key in
                    ("source_package_manifest_sha256", "tfidf_receipt_sha256"))
            and type(summary["pair_count"]) is int and summary["pair_count"] == len(rows)
            and type(summary["task_count"]) is int
            and summary["task_count"] == len({row["task_sha256"] for row in rows})
            and summary["arms"] == list(ARMS) and summary["seeds"] == list(SEEDS)
            and summary["accuracy_computed"] is summary["labels_read"] is summary["outcomes_read"]
            is summary["utility_computed"] is False, "summary_gate")
    return {
        "classification": contract["classification"], "contract_sha256": contract_sha,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(), "summary_sha256": hashlib.sha256(summary_raw).hexdigest(),
        "checkpoint_manifest_sha256": hashlib.sha256(checkpoint_raw).hexdigest(),
        "access_receipt_sha256": hashlib.sha256(access_raw).hexdigest(), "pair_predictions_sha256": rows_sha,
        "pair_count": len(rows), "task_count": len({row["task_sha256"] for row in rows}),
        "checkpoint_count": len(items), "accuracy_computed": False, "protected_values_read": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--escrow-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.escrow_root, args.contract, args.manifest)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
                           encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
