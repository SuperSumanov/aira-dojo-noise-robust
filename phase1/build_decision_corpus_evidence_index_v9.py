#!/usr/bin/env python3
"""Build the lineage-repaired Decision-Corpus Evidence Index v9."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "a5d49990f3af37ce8968495fd13bf1b1c3f5e48875b117a86a878b75ed8d958a"
INDEX_PROTOCOL = "decision_corpus_evidence_index_v9"


class BuildError(RuntimeError):
    """Raised when a frozen source or reporting boundary fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_bytes(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"file is not UTF-8: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(normalized_bytes(path).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise BuildError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def safe_path(repo_root: Path, relative: str, *, directory: bool = False) -> Path:
    value = Path(relative)
    require(not value.is_absolute() and ".." not in value.parts, f"unsafe path: {relative}")
    raw = repo_root / value
    require(not raw.is_symlink(), f"symlink input is forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"path escapes repository: {relative}") from error
    require(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def asserted_value(payload: Any, assertion_path: str) -> Any:
    current = payload
    for component in assertion_path.split("."):
        if isinstance(current, dict) and component in current:
            current = current[component]
        elif isinstance(current, list) and component.isdigit() and int(component) < len(current):
            current = current[int(component)]
        else:
            raise BuildError(f"missing assertion path: {assertion_path}")
    return current


def verify_artifact(repo_root: Path, specification: dict[str, Any]) -> tuple[dict[str, Any], int]:
    require(
        set(specification) == {"path", "sha256_normalized_lf", "json_assertions"},
        "replacement artifact schema drift",
    )
    path = safe_path(repo_root, specification["path"])
    require(path.suffix == ".json", f"replacement artifact is not JSON: {path}")
    require(
        normalized_sha256(path) == specification["sha256_normalized_lf"],
        f"replacement artifact SHA drift: {specification['path']}",
    )
    payload = read_json(path)
    assertions = specification["json_assertions"]
    require(isinstance(assertions, dict) and assertions, "replacement assertions missing")
    for assertion_path, expected in assertions.items():
        require(
            asserted_value(payload, assertion_path) == expected,
            f"replacement assertion mismatch: {assertion_path}",
        )
    return payload, len(assertions)


def parse_package_manifest(root: Path, manifest_name: str) -> tuple[Path, dict[str, str]]:
    manifest = root / manifest_name
    require(manifest.is_file() and not manifest.is_symlink(), "lineage package manifest missing")
    rows: dict[str, str] = {}
    for line_number, line in enumerate(normalized_bytes(manifest).decode("utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, f"malformed lineage manifest line: {line_number}")
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        value = Path(name)
        require(name and not value.is_absolute() and ".." not in value.parts, "unsafe manifest member")
        require(name not in rows and name != manifest_name, "duplicate lineage manifest member")
        candidate = root / value
        require(candidate.is_file() and not candidate.is_symlink(), f"missing lineage member: {name}")
        require(sha256_file(candidate) == digest, f"lineage manifest hash mismatch: {name}")
        rows[name] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != manifest_name
    }
    require(set(rows) == actual, "lineage package manifest membership drift")
    return manifest, rows


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def merge_without_overlap(source: dict[str, Any], additions: dict[str, Any], label: str) -> dict[str, Any]:
    overlap = set(source).intersection(additions)
    require(not overlap, f"v9 scope would overwrite v8 {label}: {sorted(overlap)}")
    return {**copy.deepcopy(source), **copy.deepcopy(additions)}


def verify_source_v8(repo_root: Path, protocol: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    frozen = protocol["source_v8"]
    source_path = safe_path(repo_root, frozen["path"])
    require(sha256_file(source_path) == frozen["sha256"], "source v8 SHA drift")
    source = read_json(source_path)
    require(source.get("protocol") == frozen["protocol"], "source v8 protocol drift")
    require(source.get("status") == frozen["status"], "source v8 status drift")
    entries = source.get("entries")
    require(isinstance(entries, list) and len(entries) == frozen["entry_count"], "source v8 entry count")
    require(len({entry.get("name") for entry in entries}) == len(entries), "source v8 entry names")
    index = frozen["replacement_entry_index"]
    require(isinstance(index, int) and 0 <= index < len(entries), "replacement entry index")
    require(entries[index].get("name") == frozen["replacement_entry_name"], "replacement entry position")
    require(
        sum(entry.get("name") == frozen["replacement_entry_name"] for entry in entries) == 1,
        "replacement entry is not unique",
    )
    require(isinstance(source.get("scope"), dict), "source v8 scope missing")
    require(isinstance(source.get("reporting_contract"), dict), "source v8 reporting contract missing")
    return source_path, source


def verify_lineage_package(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[Path, dict[str, str], list[dict[str, Any]], int]:
    frozen = protocol["lineage_package"]
    root = safe_path(repo_root, frozen["root"], directory=True)
    manifest, manifest_rows = parse_package_manifest(root, frozen["manifest"])
    require(sha256_file(manifest) == frozen["manifest_sha256"], "lineage package manifest SHA drift")

    artifacts = protocol["replacement_entry"]["artifacts"]
    require(isinstance(artifacts, list) and len(artifacts) == 3, "replacement artifact count")
    payloads: list[dict[str, Any]] = []
    assertion_count = 0
    for specification in artifacts:
        relative_to_package = Path(specification["path"]).relative_to(Path(frozen["root"])).as_posix()
        require(relative_to_package in manifest_rows, "replacement artifact absent from package manifest")
        require(
            manifest_rows[relative_to_package] == specification["sha256_normalized_lf"],
            "replacement artifact and package manifest SHA disagree",
        )
        payload, count = verify_artifact(repo_root, specification)
        payloads.append(payload)
        assertion_count += count

    producer, independent, bindings = payloads
    counts = frozen["required_counts"]
    relations = producer["scientific"]["global_relation_counts"]
    require(sum(relations.values()) == counts["all_rows"], "lineage relation counts do not exhaust rows")
    require(
        relations
        == {
            "parent_present_verified_direct_sibling": counts["parent_present_verified_direct_sibling"],
            "lineage_verified_orphan_parent_sibling": counts["lineage_verified_orphan_parent_sibling"],
            "same_run_declared_context_non_sibling": counts["same_run_declared_context_non_sibling"],
            "cross_run_declared_context": counts["cross_run_declared_context"],
        },
        "lineage relation count drift",
    )
    hard = producer["scientific"]["hard_integrity_gates"]
    require(len(hard) == counts["hard_gates_total"] and all(value is True for value in hard.values()), "hard gates")
    support = producer["scientific"]["support_gates"]
    flattened = [(group, gate, value) for group, gates in support.items() for gate, value in gates.items()]
    require(len(flattened) == counts["support_gates_total"], "support gate total")
    failed = [(group, gate) for group, gate, value in flattened if value is not True]
    require(failed == [("frozen:b2", "maximum_single_run_pair_share")], "support failure localization")
    require(sum(value is True for _, _, value in flattened) == counts["support_gates_passed"], "support pass count")
    b2 = producer["scientific"]["set_profiles"]["frozen:b2"]["strict_core"]
    require(b2["pairs"] == counts["frozen_b2_core_pairs"], "frozen:b2 core count")
    require(
        b2["maximum_single_run_pair_share"]["numerator"]
        == counts["frozen_b2_max_run_share_numerator"],
        "frozen:b2 run-share numerator",
    )
    require(
        b2["maximum_single_run_pair_share"]["denominator"]
        == counts["frozen_b2_max_run_share_denominator"],
        "frozen:b2 run-share denominator",
    )
    require(independent.get("producer_result_sha256") == frozen["producer_sha256"], "independent producer binding")
    require(independent.get("all_aggregate_fields_equal") is True, "independent aggregate mismatch")
    require(independent.get("imports_producer") is False, "independent verifier imported producer")
    require(bindings.get("status") == frozen["package_status"], "package status")
    require(bindings.get("source_commit") == frozen["source_commit"], "lineage source commit")
    require(bindings.get("protocol_sha256") == frozen["protocol_sha256"], "lineage protocol SHA")
    require(bindings.get("classification") == frozen["classification"], "lineage classification")
    require(bindings.get("formal", {}).get("producer_a_sha256") == frozen["producer_sha256"], "binding producer SHA")
    require(bindings.get("formal", {}).get("verifier_a_sha256") == frozen["verifier_sha256"], "binding verifier SHA")
    return manifest, manifest_rows, payloads, assertion_count


def build_index(repo_root: Path, protocol_path: Path, expected_protocol_sha256: str = PROTOCOL_SHA256) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    require(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    require(sha256_file(protocol_path) == expected_protocol_sha256, "protocol SHA drift")
    protocol = read_json(protocol_path)
    require(protocol.get("status") == "POST_RESULT_REPORTING_REPAIR_PROTOCOL_FIXED", "protocol status")
    require(protocol.get("security", {}).get("prospective_label_grade_outcome_or_prediction_values_read") is False, "protocol prospective access")
    require(protocol.get("security", {}).get("raw_senior_archives_opened") is False, "protocol raw archive access")
    require(protocol.get("security", {}).get("row_level_release_created") is False, "protocol row release")
    require(protocol.get("security", {}).get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "protocol resources")

    source_path, source = verify_source_v8(repo_root, protocol)
    manifest, manifest_rows, _, assertion_count = verify_lineage_package(repo_root, protocol)
    frozen_source = protocol["source_v8"]
    replacement = copy.deepcopy(protocol["replacement_entry"])
    entries = copy.deepcopy(source["entries"])
    replacement_index = frozen_source["replacement_entry_index"]
    old_entry = entries[replacement_index]
    entries[replacement_index] = replacement
    require(
        all(
            entries[index] == source["entries"][index]
            for index in range(len(entries))
            if index != replacement_index
        ),
        "non-target v8 entry changed",
    )
    require(
        len(entries) - 1 == frozen_source["unchanged_entry_count"],
        "unchanged v8 entry count",
    )

    candidate = copy.deepcopy(source)
    candidate.update(
        {
            "protocol": INDEX_PROTOCOL,
            "status": source["status"],
            "source_v8_index": {
                "path": frozen_source["path"],
                "sha256": frozen_source["sha256"],
                "entry_count": frozen_source["entry_count"],
                "entries_preserved_without_modification": frozen_source["unchanged_entry_count"],
                "entries_replaced": 1,
            },
            "v9_protocol": {
                "path": protocol_path.relative_to(repo_root).as_posix(),
                "sha256": expected_protocol_sha256,
                "post_result_reporting_repair": True,
            },
            "lineage_repair": {
                "replacement_entry_name": frozen_source["replacement_entry_name"],
                "replacement_entry_index": replacement_index,
                "old_entry_canonical_sha256": canonical_sha256(old_entry),
                "new_entry_canonical_sha256": canonical_sha256(replacement),
                "lineage_package_manifest_path": manifest.relative_to(repo_root).as_posix(),
                "lineage_package_manifest_sha256": sha256_file(manifest),
                "lineage_package_member_count": len(manifest_rows),
                "replacement_artifact_count": len(replacement["artifacts"]),
                "replacement_json_assertion_count": assertion_count,
                "classification": protocol["lineage_package"]["classification"],
                "hard_integrity_gates_passed": protocol["lineage_package"]["required_counts"]["hard_gates_passed"],
                "hard_integrity_gates_total": protocol["lineage_package"]["required_counts"]["hard_gates_total"],
                "support_gates_passed": protocol["lineage_package"]["required_counts"]["support_gates_passed"],
                "support_gates_total": protocol["lineage_package"]["required_counts"]["support_gates_total"],
                "all_support_gates_passed": False,
                "failed_support_gate": "frozen:b2.maximum_single_run_pair_share",
                "source_v8_status_preserved": True,
            },
            "scope": merge_without_overlap(source["scope"], protocol["scope_additions"], "scope"),
            "reporting_contract": merge_without_overlap(
                source["reporting_contract"], protocol["reporting_contract_additions"], "reporting contract"
            ),
            "v9_security": copy.deepcopy(protocol["security"]),
            "entries": entries,
        }
    )
    require(candidate["status"] == frozen_source["status"], "v9 status promotion is forbidden")
    return candidate


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    payload = build_index(arguments.repo_root, arguments.protocol)
    write_json_atomic(arguments.output, payload)
    print(json.dumps({"status": payload["status"], "entries": len(payload["entries"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
