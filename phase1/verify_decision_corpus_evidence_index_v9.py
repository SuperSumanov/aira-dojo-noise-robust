#!/usr/bin/env python3
"""Independently verify the lineage-repaired Evidence Index v9."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "a5d49990f3af37ce8968495fd13bf1b1c3f5e48875b117a86a878b75ed8d958a"


class VerificationError(RuntimeError):
    """Raised when the candidate or a bound source differs from v9."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def text_bytes(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise VerificationError(f"non-UTF-8 input: {path}") from error
    return text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def text_sha256(path: Path) -> str:
    return hashlib.sha256(text_bytes(path)).hexdigest()


def json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(text_bytes(path).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise VerificationError(f"invalid JSON: {path}") from error
    check(isinstance(value, dict), f"non-object JSON: {path}")
    return value


def inside(repo_root: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    check(not part.is_absolute() and ".." not in part.parts, f"unsafe relative path: {relative}")
    raw = repo_root / part
    check(not raw.is_symlink(), f"symlink forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"path escaped repository: {relative}") from error
    check(resolved.is_dir() if directory else resolved.is_file(), f"missing bound input: {relative}")
    return resolved


def lookup(payload: Any, dotted: str) -> Any:
    current = payload
    for item in dotted.split("."):
        if isinstance(current, dict) and item in current:
            current = current[item]
        elif isinstance(current, list) and item.isdecimal() and int(item) < len(current):
            current = current[int(item)]
        else:
            raise VerificationError(f"assertion path absent: {dotted}")
    return current


def canonical_digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def read_manifest(root: Path, filename: str) -> tuple[Path, dict[str, str]]:
    manifest = root / filename
    check(manifest.is_file() and not manifest.is_symlink(), "package manifest absent")
    members: dict[str, str] = {}
    for number, row in enumerate(text_bytes(manifest).decode("utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", row)
        check(match is not None, f"manifest syntax at line {number}")
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        relative = Path(name)
        check(name and not relative.is_absolute() and ".." not in relative.parts, "unsafe manifest name")
        check(name not in members and name != filename, "manifest duplicate")
        member = root / relative
        check(member.is_file() and not member.is_symlink(), f"manifest member absent: {name}")
        check(file_sha256(member) == digest, f"manifest digest mismatch: {name}")
        members[name] = digest
    observed = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != filename
    }
    check(set(members) == observed, "package manifest membership mismatch")
    return manifest, members


def independently_verify_sources(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[Path, dict[str, Any], Path, dict[str, str], int]:
    source_rule = protocol["source_v8"]
    source_path = inside(repo_root, source_rule["path"])
    check(file_sha256(source_path) == source_rule["sha256"], "source v8 digest")
    source = json_object(source_path)
    check(source.get("protocol") == source_rule["protocol"], "source v8 protocol")
    check(source.get("status") == source_rule["status"], "source v8 status")
    entries = source.get("entries")
    check(isinstance(entries, list) and len(entries) == source_rule["entry_count"], "source entry count")
    check(len({entry.get("name") for entry in entries}) == len(entries), "source duplicate entry")
    position = source_rule["replacement_entry_index"]
    check(entries[position].get("name") == source_rule["replacement_entry_name"], "source replacement position")

    package_rule = protocol["lineage_package"]
    package_root = inside(repo_root, package_rule["root"], directory=True)
    manifest, members = read_manifest(package_root, package_rule["manifest"])
    check(file_sha256(manifest) == package_rule["manifest_sha256"], "package manifest digest")

    loaded: dict[str, dict[str, Any]] = {}
    assertions_checked = 0
    replacement = protocol["replacement_entry"]
    check(replacement.get("name") == source_rule["replacement_entry_name"], "replacement name")
    artifacts = replacement.get("artifacts")
    check(isinstance(artifacts, list) and len(artifacts) == 3, "replacement artifact count")
    for specification in artifacts:
        check(set(specification) == {"path", "sha256_normalized_lf", "json_assertions"}, "artifact schema")
        artifact = inside(repo_root, specification["path"])
        check(artifact.suffix == ".json", "artifact suffix")
        check(text_sha256(artifact) == specification["sha256_normalized_lf"], "artifact normalized digest")
        package_name = Path(specification["path"]).relative_to(Path(package_rule["root"])).as_posix()
        check(members.get(package_name) == specification["sha256_normalized_lf"], "artifact package binding")
        payload = json_object(artifact)
        loaded[package_name] = payload
        claims = specification["json_assertions"]
        check(isinstance(claims, dict) and claims, "artifact assertions")
        for path, expected in claims.items():
            check(lookup(payload, path) == expected, f"artifact assertion: {path}")
            assertions_checked += 1

    producer = loaded[package_rule["producer_path"]]
    independent = loaded[package_rule["verifier_path"]]
    bindings = loaded[package_rule["bindings_path"]]
    expected = package_rule["required_counts"]
    relation_counts = producer["scientific"]["global_relation_counts"]
    check(sum(relation_counts.values()) == expected["all_rows"], "relation exhaustion")
    check(relation_counts["parent_present_verified_direct_sibling"] == expected["parent_present_verified_direct_sibling"], "direct count")
    check(relation_counts["lineage_verified_orphan_parent_sibling"] == expected["lineage_verified_orphan_parent_sibling"], "orphan count")
    check(relation_counts["same_run_declared_context_non_sibling"] == 0, "same-run non-sibling count")
    check(relation_counts["cross_run_declared_context"] == 0, "cross-run count")
    hard_values = list(producer["scientific"]["hard_integrity_gates"].values())
    check(len(hard_values) == expected["hard_gates_total"] and all(value is True for value in hard_values), "hard gates")
    flattened = [
        (set_name, gate_name, value)
        for set_name, gates in producer["scientific"]["support_gates"].items()
        for gate_name, value in gates.items()
    ]
    check(len(flattened) == expected["support_gates_total"], "support gate total")
    check(sum(value is True for _, _, value in flattened) == expected["support_gates_passed"], "support pass total")
    check(
        [(set_name, gate_name) for set_name, gate_name, value in flattened if value is not True]
        == [("frozen:b2", "maximum_single_run_pair_share")],
        "failed support gate hidden or moved",
    )
    ratio = producer["scientific"]["set_profiles"]["frozen:b2"]["strict_core"]["maximum_single_run_pair_share"]
    check(
        (ratio["numerator"], ratio["denominator"])
        == (
            expected["frozen_b2_max_run_share_numerator"],
            expected["frozen_b2_max_run_share_denominator"],
        ),
        "frozen:b2 run concentration",
    )
    check(independent.get("imports_producer") is False, "verifier independence")
    check(independent.get("all_aggregate_fields_equal") is True, "aggregate equality")
    check(independent.get("producer_result_sha256") == package_rule["producer_sha256"], "verifier producer binding")
    check(bindings.get("status") == package_rule["package_status"], "binding status")
    check(bindings.get("source_commit") == package_rule["source_commit"], "binding source")
    check(bindings.get("protocol_sha256") == package_rule["protocol_sha256"], "binding protocol")
    check(bindings.get("classification") == package_rule["classification"], "binding classification")
    return source_path, source, manifest, members, assertions_checked


def expected_candidate(
    repo_root: Path,
    protocol_path: Path,
    protocol: dict[str, Any],
    source: dict[str, Any],
    manifest: Path,
    members: dict[str, str],
    assertions_checked: int,
) -> dict[str, Any]:
    source_rule = protocol["source_v8"]
    replacement = copy.deepcopy(protocol["replacement_entry"])
    position = source_rule["replacement_entry_index"]
    old_entry = source["entries"][position]
    entries = copy.deepcopy(source["entries"])
    entries[position] = replacement
    check(
        all(entries[index] == source["entries"][index] for index in range(len(entries)) if index != position),
        "unchanged source entries",
    )
    scope_overlap = set(source["scope"]).intersection(protocol["scope_additions"])
    reporting_overlap = set(source["reporting_contract"]).intersection(protocol["reporting_contract_additions"])
    check(not scope_overlap and not reporting_overlap, "v9 overwrites source contract")
    result = copy.deepcopy(source)
    result.update(
        {
            "protocol": "decision_corpus_evidence_index_v9",
            "status": source["status"],
            "source_v8_index": {
                "path": source_rule["path"],
                "sha256": source_rule["sha256"],
                "entry_count": source_rule["entry_count"],
                "entries_preserved_without_modification": source_rule["unchanged_entry_count"],
                "entries_replaced": 1,
            },
            "v9_protocol": {
                "path": protocol_path.relative_to(repo_root).as_posix(),
                "sha256": PROTOCOL_SHA256,
                "post_result_reporting_repair": True,
            },
            "lineage_repair": {
                "replacement_entry_name": source_rule["replacement_entry_name"],
                "replacement_entry_index": position,
                "old_entry_canonical_sha256": canonical_digest(old_entry),
                "new_entry_canonical_sha256": canonical_digest(replacement),
                "lineage_package_manifest_path": manifest.relative_to(repo_root).as_posix(),
                "lineage_package_manifest_sha256": file_sha256(manifest),
                "lineage_package_member_count": len(members),
                "replacement_artifact_count": len(replacement["artifacts"]),
                "replacement_json_assertion_count": assertions_checked,
                "classification": protocol["lineage_package"]["classification"],
                "hard_integrity_gates_passed": protocol["lineage_package"]["required_counts"]["hard_gates_passed"],
                "hard_integrity_gates_total": protocol["lineage_package"]["required_counts"]["hard_gates_total"],
                "support_gates_passed": protocol["lineage_package"]["required_counts"]["support_gates_passed"],
                "support_gates_total": protocol["lineage_package"]["required_counts"]["support_gates_total"],
                "all_support_gates_passed": False,
                "failed_support_gate": "frozen:b2.maximum_single_run_pair_share",
                "source_v8_status_preserved": True,
            },
            "scope": {**copy.deepcopy(source["scope"]), **copy.deepcopy(protocol["scope_additions"])},
            "reporting_contract": {
                **copy.deepcopy(source["reporting_contract"]),
                **copy.deepcopy(protocol["reporting_contract_additions"]),
            },
            "v9_security": copy.deepcopy(protocol["security"]),
            "entries": entries,
        }
    )
    return result


def verify_candidate(repo_root: Path, protocol_path: Path, candidate_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    candidate_path = candidate_path.resolve()
    check(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    check(candidate_path.is_file(), "candidate absent")
    check(file_sha256(protocol_path) == PROTOCOL_SHA256, "protocol digest")
    protocol = json_object(protocol_path)
    check(protocol.get("status") == "POST_RESULT_REPORTING_REPAIR_PROTOCOL_FIXED", "protocol status")
    check(
        protocol.get("security")
        == {
            "prospective_label_grade_outcome_or_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "task_run_card_code_edge_or_row_identities_emitted": False,
            "row_level_release_created": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "security contract",
    )
    _, source, manifest, members, assertions_checked = independently_verify_sources(repo_root, protocol)
    expected = expected_candidate(
        repo_root, protocol_path, protocol, source, manifest, members, assertions_checked
    )
    candidate = json_object(candidate_path)
    check(candidate == expected, "candidate differs from independently reconstructed v9")
    replacement_position = protocol["source_v8"]["replacement_entry_index"]
    check(
        sum(
            candidate["entries"][index] == source["entries"][index]
            for index in range(len(source["entries"]))
            if index != replacement_position
        )
        == protocol["source_v8"]["unchanged_entry_count"],
        "not all 15 non-target entries are unchanged",
    )
    check(candidate["status"] == source["status"], "provisional status was promoted")
    return {
        "protocol": "independent-decision-corpus-evidence-index-v9-verification",
        "status": "INDEPENDENT_LINEAGE_REPAIRED_EVIDENCE_INDEX_V9_VERIFIED",
        "index_sha256": file_sha256(candidate_path),
        "source_v8_sha256": protocol["source_v8"]["sha256"],
        "lineage_package_manifest_sha256": file_sha256(manifest),
        "entry_count": len(candidate["entries"]),
        "entries_replaced": 1,
        "entries_preserved_without_modification": protocol["source_v8"]["unchanged_entry_count"],
        "replacement_artifact_count": len(protocol["replacement_entry"]["artifacts"]),
        "replacement_json_assertion_count": assertions_checked,
        "classification": protocol["lineage_package"]["classification"],
        "hard_integrity_gates_passed": 15,
        "hard_integrity_gates_total": 15,
        "support_gates_passed": 35,
        "support_gates_total": 36,
        "failed_support_gate": "frozen:b2.maximum_single_run_pair_share",
        "source_v8_status_preserved": True,
        "all_aggregate_fields_equal": True,
        "imports_builder": False,
        "prospective_values_read": False,
        "raw_senior_archives_opened": False,
        "row_level_release_created": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    receipt = verify_candidate(arguments.repo_root, arguments.protocol, arguments.candidate)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": receipt["status"], "entries": receipt["entry_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
