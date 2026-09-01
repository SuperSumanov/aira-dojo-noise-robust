#!/usr/bin/env python3
"""Independent verifier for the v11 generator-provenance completion summary."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping


SHA_RE = re.compile(r"[0-9a-f]{64}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), "JSON object")
    return value


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    value = Fraction(numerator, denominator)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def verify(
    protocol: Mapping[str, Any],
    inventory: Mapping[str, Any],
    inventory_verification: Mapping[str, Any],
    archived: Mapping[str, Any],
    archived_verification: Mapping[str, Any],
    hashes: Mapping[str, str],
    claimed: Mapping[str, Any],
    claimed_sha: str,
) -> dict[str, Any]:
    check(all(SHA_RE.fullmatch(value) for value in (*hashes.values(), claimed_sha)), "SHA syntax")
    check(protocol.get("protocol") == "decision-corpus-generator-provenance-completion-v1", "protocol")
    check(protocol.get("version") == 1, "protocol version")
    check(protocol.get("status") == "FROZEN_BEFORE_R6_FORMAL_PUBLIC_AGGREGATE_READ", "protocol status")
    rule = protocol["completion_rule"]
    check(rule["post_result_rule_change_allowed"] is False, "post-result change")
    check(rule["provider_family_rows_change_allowed"] is False, "provider mutation")
    check(rule["service_provider_or_contract_entity_inference_from_model_id_allowed"] is False, "provider inference")
    check(inventory.get("protocol") == "release-provider-provenance-inventory-v1", "inventory protocol")
    check(inventory.get("status") == "PARTIAL_NOT_RELEASE_CLEARED", "inventory status")
    check(inventory_verification.get("protocol") == "release-provider-provenance-independent-verification-v1", "inventory verifier")
    check(inventory_verification.get("status") == "PASS", "inventory verifier status")
    check(inventory_verification["inventory_sha256"] == hashes["inventory"], "inventory SHA")
    check(inventory_verification["coverage"] == inventory["coverage"], "inventory coverage")
    check(inventory_verification["release"] == inventory["release"], "inventory release")
    baseline = protocol["known_baseline"]
    coverage = inventory["coverage"]
    release = inventory["release"]
    check(baseline["release_rows"] == release["rows"], "baseline rows")
    check(baseline["provider_family_rows"] == coverage["mapped_rows"], "baseline provider")
    check(baseline["configured_model_id_rows"] == coverage["mapped_rows"], "baseline model")
    check(baseline["exact_version_or_model_rows"] == coverage["exact_version_or_model_rows"], "baseline exact")
    check(baseline["version_boundary_ambiguous_rows"] == coverage["version_boundary_ambiguous_rows"], "baseline ambiguity")
    check(baseline["unmapped_rows"] == coverage["unmapped_rows"], "baseline unmapped")
    check(baseline["unmapped_batches"] == coverage["unmapped_batches"], "baseline batches")
    check(baseline["inventory_sha256"] == hashes["inventory"], "baseline inventory SHA")
    check(baseline["inventory_verification_sha256"] == hashes["inventory_verification"], "baseline verifier SHA")
    check(archived["protocol"] == "archived-card-generator-provenance-v1" and archived["status"] == "COMPLETE_EXACT", "archived summary")
    check(archived_verification.get("protocol") == "archived-card-generator-provenance-independent-verifier-v1", "archived verifier")
    check(archived_verification["status"] == "PASS", "archived verifier status")
    check(archived_verification["summary_sha256"] == hashes["archived_summary"], "archived SHA")
    check(archived_verification["coverage"] == archived["coverage"], "archived coverage")
    check(archived_verification["model_counts"] == archived["model_counts"], "archived models")

    unmapped = {
        row["file"]: row["rows"]
        for row in inventory["batches"]
        if row["annotation_status"] == "unmapped"
    }
    check(set(unmapped) == set(inventory["unmapped_batch_files"]), "unmapped set")
    batch_receipts = archived["batches"]
    check({row["batch"] for row in batch_receipts} == set(unmapped), "archived set")
    for row in batch_receipts:
        target = unmapped[row["batch"]]
        check(row["target_rows"] == target and row["exact_rows"] == target, "batch exact")
        check(row["ambiguous_rows"] == 0 and row["missing_rows"] == 0, "batch unresolved")
        check(sum(row["model_counts"].values()) == target, "batch model counts")
    recovered = archived["coverage"]["exact_rows"]
    check(recovered == coverage["unmapped_rows"], "recovered rows")
    check(archived["coverage"]["ambiguous_rows"] == 0 and archived["coverage"]["missing_rows"] == 0, "recovered unresolved")
    check(sum(archived["model_counts"].values()) == recovered, "recovered model total")
    total = release["rows"]
    configured = coverage["mapped_rows"] + recovered
    exact = coverage["exact_version_or_model_rows"] + recovered
    provider = coverage["mapped_rows"]
    ambiguous = coverage["version_boundary_ambiguous_rows"]
    expected_coverage = {
        "configured_model_id_rows": configured,
        "configured_model_id_fraction": fraction(configured, total),
        "exact_version_or_model_rows": exact,
        "exact_version_or_model_fraction": fraction(exact, total),
        "version_boundary_ambiguous_rows": ambiguous,
        "provider_family_rows": provider,
        "provider_family_fraction": fraction(provider, total),
        "provider_family_unresolved_rows": total - provider,
    }
    check(configured == total and exact + ambiguous == total, "completion partition")
    check(claimed.get("protocol") == "decision-corpus-generator-provenance-completion-summary-v1", "claimed protocol")
    check(claimed.get("status") == "COMPLETE_CONFIGURED_MODEL_ID_PROVIDER_PARTIAL_NOT_RELEASE_CLEARED", "claimed status")
    check(claimed.get("input_sha256") == dict(hashes), "claimed inputs")
    check(claimed.get("release") == {
        "version": release["version"],
        "rows": total,
        "batches": release["batches"],
        "batch_lock_sha256": release["batch_lock_sha256"],
    }, "claimed release")
    check(claimed.get("coverage") == expected_coverage, "claimed coverage")
    check(claimed.get("archived_recovery") == {
        "batches": archived["coverage"]["batches"],
        "rows": recovered,
        "model_counts": archived["model_counts"],
        "evidence": "exact_archived_dojo_config",
    }, "claimed recovery")
    boundary = claimed["interpretation_boundary"]
    check(boundary["configured_model_id_identifies_provider_or_contract_entity"] is False, "boundary provider")
    check(boundary["configured_model_id_is_server_side_version"] is False, "boundary version")
    check(boundary["provider_family_coverage_changed"] is False, "boundary coverage")
    check(boundary["version_boundary_ambiguity_changed"] is False, "boundary ambiguity")
    check(boundary["release_cleared"] is False, "boundary release")
    check(boundary["provider_terms_cleared"] is False, "boundary terms")
    check(boundary["counts_as_distinct_scientific_claim_evidence"] is False, "boundary evidence")
    scope = claimed["scope"]
    check(scope["raw_card_ids_or_archive_values_emitted"] is False, "raw values")
    check(scope["prospective_resources_read"] is False, "prospective")
    check(scope["service_provider_or_contract_entity_inferred"] is False, "provider inference")
    check(scope["gpu_paid_api_model_fit_base_update"] == "0/0/0/0", "resource scope")
    return {
        "protocol": "decision-corpus-generator-provenance-completion-independent-verification-v1",
        "status": "PASS_EXACT_RECONSTRUCTION",
        "claimed_summary_sha256": claimed_sha,
        "input_sha256": dict(hashes),
        "coverage": expected_coverage,
        "service_provider_or_contract_entity_inferred": False,
        "release_cleared": False,
        "prospective_resources_read": False,
    }


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "inventory", "inventory-verification", "archived-summary", "archived-verification", "claimed-summary"):
        parser.add_argument(f"--{name}", type=Path, required=True)
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bindings = {
        "protocol": (args.protocol, args.protocol_sha256),
        "inventory": (args.inventory, args.inventory_sha256),
        "inventory_verification": (args.inventory_verification, args.inventory_verification_sha256),
        "archived_summary": (args.archived_summary, args.archived_summary_sha256),
        "archived_verification": (args.archived_verification, args.archived_verification_sha256),
    }
    for path, expected in (*bindings.values(), (args.claimed_summary, args.claimed_summary_sha256)):
        check(SHA_RE.fullmatch(expected) is not None and file_hash(path) == expected, "file SHA")
    result = verify(
        read(args.protocol), read(args.inventory), read(args.inventory_verification),
        read(args.archived_summary), read(args.archived_verification),
        {key: value[1] for key, value in bindings.items()},
        read(args.claimed_summary), args.claimed_summary_sha256,
    )
    write_exclusive(args.output, result)
    print(json.dumps({"status": result["status"], "output_sha256": file_hash(args.output), "raw_values_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
