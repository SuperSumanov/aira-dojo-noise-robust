#!/usr/bin/env python3
"""Compose verified archived model IDs with the v11 provider inventory."""

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


class CompletionError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CompletionError(message)


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must be an object")
    return value


def fraction_payload(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0 and 0 <= numerator <= denominator, "invalid fraction")
    reduced = Fraction(numerator, denominator)
    return {
        "numerator": reduced.numerator,
        "denominator": reduced.denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def validate_inputs(
    protocol: Mapping[str, Any],
    inventory: Mapping[str, Any],
    inventory_verification: Mapping[str, Any],
    archived: Mapping[str, Any],
    archived_verification: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(protocol.get("protocol") == "decision-corpus-generator-provenance-completion-v1", "protocol")
    require(protocol.get("version") == 1, "protocol version")
    require(protocol.get("status") == "FROZEN_BEFORE_R6_FORMAL_PUBLIC_AGGREGATE_READ", "protocol status")
    rule = protocol.get("completion_rule")
    require(isinstance(rule, Mapping), "completion rule")
    require(rule.get("post_result_rule_change_allowed") is False, "post-result change")
    require(rule.get("provider_family_rows_change_allowed") is False, "provider mutation")
    require(rule.get("service_provider_or_contract_entity_inference_from_model_id_allowed") is False, "provider inference")
    for value in hashes.values():
        require(SHA_RE.fullmatch(value) is not None, "SHA syntax")

    require(inventory.get("protocol") == "release-provider-provenance-inventory-v1", "inventory protocol")
    require(inventory.get("status") == "PARTIAL_NOT_RELEASE_CLEARED", "inventory status")
    require(inventory_verification.get("protocol") == "release-provider-provenance-independent-verification-v1", "inventory verifier")
    require(inventory_verification.get("status") == "PASS", "inventory verification status")
    require(inventory_verification.get("inventory_sha256") == hashes["inventory"], "inventory verification binding")
    require(inventory_verification.get("coverage") == inventory.get("coverage"), "inventory coverage verification")
    require(inventory_verification.get("release") == inventory.get("release"), "inventory release verification")

    baseline = protocol.get("known_baseline")
    require(isinstance(baseline, Mapping), "known baseline")
    coverage = inventory.get("coverage")
    release = inventory.get("release")
    require(isinstance(coverage, Mapping) and isinstance(release, Mapping), "inventory aggregates")
    expected_baseline = {
        "release_rows": release.get("rows"),
        "provider_family_rows": coverage.get("mapped_rows"),
        "configured_model_id_rows": coverage.get("mapped_rows"),
        "exact_version_or_model_rows": coverage.get("exact_version_or_model_rows"),
        "version_boundary_ambiguous_rows": coverage.get("version_boundary_ambiguous_rows"),
        "unmapped_rows": coverage.get("unmapped_rows"),
        "unmapped_batches": coverage.get("unmapped_batches"),
        "inventory_sha256": hashes["inventory"],
        "inventory_verification_sha256": hashes["inventory_verification"],
    }
    require(dict(baseline) == expected_baseline, "frozen baseline mismatch")

    require(archived.get("protocol") == "archived-card-generator-provenance-v1", "archived protocol")
    require(archived.get("status") == "COMPLETE_EXACT", "archived status")
    require(archived_verification.get("protocol") == "archived-card-generator-provenance-independent-verifier-v1", "archived verifier")
    require(archived_verification.get("status") == "PASS", "archived verification status")
    require(archived_verification.get("summary_sha256") == hashes["archived_summary"], "archived summary binding")
    require(archived_verification.get("coverage") == archived.get("coverage"), "archived coverage verification")
    require(archived_verification.get("model_counts") == archived.get("model_counts"), "archived model verification")

    unmapped_names = inventory.get("unmapped_batch_files")
    batch_rows = {
        row["file"]: row["rows"]
        for row in inventory.get("batches", [])
        if row.get("annotation_status") == "unmapped"
    }
    require(isinstance(unmapped_names, list) and set(unmapped_names) == set(batch_rows), "inventory unmapped set")
    archived_batches = archived.get("batches")
    require(isinstance(archived_batches, list), "archived batches")
    require({row.get("batch") for row in archived_batches} == set(unmapped_names), "archived batch set")
    for row in archived_batches:
        batch = row.get("batch")
        target = batch_rows[batch]
        require(row.get("target_rows") == target, f"target rows {batch}")
        require(row.get("exact_rows") == target, f"exact rows {batch}")
        require(row.get("ambiguous_rows") == 0 and row.get("missing_rows") == 0, f"unresolved rows {batch}")
        model_counts = row.get("model_counts")
        require(isinstance(model_counts, Mapping) and sum(model_counts.values()) == target, f"model counts {batch}")
    archived_coverage = archived["coverage"]
    require(archived_coverage.get("batches") == len(unmapped_names), "archived batch count")
    require(archived_coverage.get("target_rows") == coverage.get("unmapped_rows"), "archived target total")
    require(archived_coverage.get("exact_rows") == coverage.get("unmapped_rows"), "archived exact total")
    require(archived_coverage.get("ambiguous_rows") == 0 and archived_coverage.get("missing_rows") == 0, "archived unresolved total")
    require(sum(archived.get("model_counts", {}).values()) == coverage.get("unmapped_rows"), "archived model total")
    return dict(coverage), dict(release)


def compose(
    protocol: Mapping[str, Any],
    inventory: Mapping[str, Any],
    inventory_verification: Mapping[str, Any],
    archived: Mapping[str, Any],
    archived_verification: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    baseline, release = validate_inputs(
        protocol, inventory, inventory_verification, archived, archived_verification, hashes
    )
    total = int(release["rows"])
    recovered = int(archived["coverage"]["exact_rows"])
    configured = int(baseline["mapped_rows"]) + recovered
    exact_version_or_model = int(baseline["exact_version_or_model_rows"]) + recovered
    provider_rows = int(baseline["mapped_rows"])
    ambiguous_version = int(baseline["version_boundary_ambiguous_rows"])
    require(configured == total, "configured model ID completion failed")
    require(exact_version_or_model + ambiguous_version == total, "version/model partition")
    return {
        "protocol": "decision-corpus-generator-provenance-completion-summary-v1",
        "status": "COMPLETE_CONFIGURED_MODEL_ID_PROVIDER_PARTIAL_NOT_RELEASE_CLEARED",
        "input_sha256": dict(hashes),
        "release": {
            "version": release["version"],
            "rows": total,
            "batches": release["batches"],
            "batch_lock_sha256": release["batch_lock_sha256"],
        },
        "coverage": {
            "configured_model_id_rows": configured,
            "configured_model_id_fraction": fraction_payload(configured, total),
            "exact_version_or_model_rows": exact_version_or_model,
            "exact_version_or_model_fraction": fraction_payload(exact_version_or_model, total),
            "version_boundary_ambiguous_rows": ambiguous_version,
            "provider_family_rows": provider_rows,
            "provider_family_fraction": fraction_payload(provider_rows, total),
            "provider_family_unresolved_rows": total - provider_rows,
        },
        "archived_recovery": {
            "batches": archived["coverage"]["batches"],
            "rows": recovered,
            "model_counts": archived["model_counts"],
            "evidence": "exact_archived_dojo_config",
        },
        "interpretation_boundary": {
            "configured_model_id_is_server_side_version": False,
            "configured_model_id_identifies_provider_or_contract_entity": False,
            "provider_family_coverage_changed": False,
            "version_boundary_ambiguity_changed": False,
            "provider_terms_cleared": False,
            "release_cleared": False,
            "counts_as_distinct_scientific_claim_evidence": False,
        },
        "scope": {
            "raw_card_ids_or_archive_values_emitted": False,
            "prospective_resources_read": False,
            "service_provider_or_contract_entity_inferred": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
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
    for name in ("protocol", "inventory", "inventory-verification", "archived-summary", "archived-verification"):
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
    for path, expected in bindings.values():
        require(SHA_RE.fullmatch(expected) is not None and file_sha(path) == expected, "input file SHA")
    result = compose(
        read_object(args.protocol),
        read_object(args.inventory),
        read_object(args.inventory_verification),
        read_object(args.archived_summary),
        read_object(args.archived_verification),
        {key: value[1] for key, value in bindings.items()},
    )
    write_exclusive(args.output, result)
    print(json.dumps({"status": result["status"], "output_sha256": file_sha(args.output), "raw_values_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
