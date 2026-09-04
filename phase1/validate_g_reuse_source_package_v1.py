from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ROLES = {
    "cards", "global_pairs", "local_pairs", "split_manifest", "source_provenance",
    "producer_receipt", "evaluator_receipt",
}
TOP_KEYS = {"protocol", "package_id", "producer", "declarations", "artifacts"}
ARTIFACT_KEYS = {"role", "path", "bytes", "sha256", "lfs_oid_sha256"}
PRODUCER_KEYS = {"producer_commit", "stable_release_id", "exact_config_stratum_id"}
DECLARATION_KEYS = {"historical_development_only", "whole_experiment_split_declared", "source_provenance_schema"}
PRODUCER_RECEIPT_KEYS = {
    "protocol", "producer_commit", "stable_release_id", "exact_config_stratum_id",
    "command_argv_sha256", "instance_manifest_sha256", "run_count", "executed_at_utc",
}
EVALUATOR_RECEIPT_KEYS = {
    "protocol", "evaluator_commit", "evaluator_id", "score_schema_id", "execution_records_sha256",
}
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}")
SECRET = re.compile(
    rb"(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})"
)


class PackageDeclarationError(RuntimeError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PackageDeclarationError(reason)


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "duplicate_json_key")
        out[key] = value
    return out


def load_small_json(path: Path, cap: int = 1_000_000) -> tuple[dict, bytes]:
    require(path.is_file() and not path.is_symlink(), "unsafe_json_file")
    raw = path.read_bytes()
    require(0 < len(raw) <= cap, "json_size")
    require(not SECRET.search(raw), "credential_shape")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    require(isinstance(value, dict), "json_object_required")
    return value, raw


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def exact_keys(value: dict, expected: set[str], reason: str) -> None:
    require(set(value) == expected, reason)


def safe_member(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and "\\" not in relative, "invalid_relative_path")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and relative == pure.as_posix() and ".." not in pure.parts, "path_traversal")
    path = root.joinpath(*pure.parts)
    require(path.resolve(strict=True).is_relative_to(root), "path_escape")
    require(path.is_file() and not path.is_symlink(), "artifact_not_regular")
    return path


def validate(root: Path, manifest_path: Path) -> dict:
    require(root.exists() and root.is_dir() and not root.is_symlink(), "unsafe_package_root")
    root = root.resolve(strict=True)
    require(manifest_path.exists() and manifest_path.is_file() and not manifest_path.is_symlink(),
            "unsafe_manifest")
    manifest_path = manifest_path.resolve(strict=True)
    require(manifest_path.is_relative_to(root), "manifest_outside_root")
    manifest, raw_manifest = load_small_json(manifest_path)
    exact_keys(manifest, TOP_KEYS, "manifest_schema")
    require(manifest["protocol"] == "g-reuse-source-package-declaration-v1", "protocol")
    require(isinstance(manifest["package_id"], str) and SAFE_ID.fullmatch(manifest["package_id"]), "package_id")
    producer, declarations = manifest["producer"], manifest["declarations"]
    require(isinstance(producer, dict) and isinstance(declarations, dict), "declaration_objects")
    exact_keys(producer, PRODUCER_KEYS, "producer_schema")
    exact_keys(declarations, DECLARATION_KEYS, "declarations_schema")
    require(HEX40.fullmatch(producer["producer_commit"] or "") is not None, "producer_commit")
    require(all(SAFE_ID.fullmatch(producer[key] or "") for key in ("stable_release_id", "exact_config_stratum_id")),
            "producer_ids")
    require(declarations == {
        "historical_development_only": True,
        "whole_experiment_split_declared": True,
        "source_provenance_schema": "source-declaration-v2",
    }, "required_declarations")
    artifacts = manifest["artifacts"]
    require(isinstance(artifacts, list) and len(artifacts) == len(ROLES), "artifact_count")
    by_role, paths, inodes = {}, set(), set()
    for item in artifacts:
        require(isinstance(item, dict), "artifact_object")
        exact_keys(item, ARTIFACT_KEYS, "artifact_schema")
        role = item["role"]
        require(role in ROLES and role not in by_role, "artifact_role")
        require(type(item["bytes"]) is int and item["bytes"] > 0, "artifact_bytes")
        require(HEX64.fullmatch(item["sha256"] or "") is not None, "artifact_sha256")
        oid = item["lfs_oid_sha256"]
        require(oid is None or (isinstance(oid, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", oid)), "lfs_oid")
        path = safe_member(root, item["path"])
        stat = path.stat()
        require(item["path"] not in paths and (stat.st_dev, stat.st_ino) not in inodes, "artifact_alias")
        require(stat.st_size == item["bytes"] and sha256(path) == item["sha256"], "artifact_drift")
        paths.add(item["path"]); inodes.add((stat.st_dev, stat.st_ino)); by_role[role] = path
    require(set(by_role) == ROLES, "missing_roles")
    producer_receipt, producer_raw = load_small_json(by_role["producer_receipt"])
    evaluator_receipt, evaluator_raw = load_small_json(by_role["evaluator_receipt"])
    exact_keys(producer_receipt, PRODUCER_RECEIPT_KEYS, "producer_receipt_schema")
    exact_keys(evaluator_receipt, EVALUATOR_RECEIPT_KEYS, "evaluator_receipt_schema")
    require(producer_receipt["protocol"] == "g-reuse-producer-receipt-v1", "producer_receipt_protocol")
    require(evaluator_receipt["protocol"] == "g-reuse-evaluator-receipt-v1", "evaluator_receipt_protocol")
    for key in ("producer_commit", "stable_release_id", "exact_config_stratum_id"):
        require(producer_receipt[key] == producer[key], "producer_receipt_mismatch")
    require(type(producer_receipt["run_count"]) is int and producer_receipt["run_count"] > 0, "run_count")
    for key in ("command_argv_sha256", "instance_manifest_sha256"):
        require(HEX64.fullmatch(producer_receipt[key] or "") is not None, "producer_receipt_hash")
    try:
        executed = dt.datetime.fromisoformat(producer_receipt["executed_at_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise PackageDeclarationError("executed_at_utc") from None
    require(executed.tzinfo is not None and executed.utcoffset() == dt.timedelta(0), "executed_at_utc")
    require(HEX40.fullmatch(evaluator_receipt["evaluator_commit"] or "") is not None, "evaluator_commit")
    require(HEX64.fullmatch(evaluator_receipt["execution_records_sha256"] or "") is not None,
            "execution_records_sha256")
    require(all(isinstance(evaluator_receipt[key], str) and SAFE_ID.fullmatch(evaluator_receipt[key])
                for key in ("evaluator_id", "score_schema_id")), "evaluator_ids")
    return {
        "artifacts": len(artifacts),
        "classification": "PACKAGE_DECLARATION_HASH_BOUND_NOT_EFFECT_ELIGIBLE",
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "package_id": manifest["package_id"],
        "producer_receipt_sha256": hashlib.sha256(producer_raw).hexdigest(),
        "evaluator_receipt_sha256": hashlib.sha256(evaluator_raw).hexdigest(),
        "payload_files_parsed": 0,
        "protected_values_read": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.package_root, args.manifest)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
