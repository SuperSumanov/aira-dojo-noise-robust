"""Independent verifier for the release provider provenance inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ProviderVerificationError(RuntimeError):
    pass


GROUPS = (
    "ds-flash-v1",
    "ds-flash-v2",
    "ds-flash-ambiguous",
    "qwen3-coder-flash",
    "glm-5",
)

GROUP_METADATA = {
    "ds-flash-v1": ("DeepSeek", "deepseek-v4-flash", "annotated-version"),
    "ds-flash-v2": ("DeepSeek", "deepseek-v4-flash", "annotated-version"),
    "ds-flash-ambiguous": ("DeepSeek", "deepseek-v4-flash", "version-boundary-ambiguous"),
    "qwen3-coder-flash": ("Alibaba Cloud Model Studio", "qwen3-coder-flash", "annotated-model"),
    "glm-5": ("Zhipu AI", "glm-5", "annotated-model"),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


def object_from(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProviderVerificationError(f"unreadable JSON: {path}") from exc
    if type(value) is not dict:
        raise ProviderVerificationError(f"not an object: {path}")
    return value


def recompute(
    release_path: Path,
    registry_path: Path,
    manifest_path: Path,
    annotations_path: Path,
) -> dict[str, Any]:
    release = object_from(release_path)
    registry = object_from(registry_path)
    annotations = object_from(annotations_path)
    all_batches = registry.get("batches")
    count = release.get("batch_count")
    if type(all_batches) is not list or type(count) is not int or not 0 < count <= len(all_batches):
        raise ProviderVerificationError("invalid release prefix")
    batches = all_batches[:count]
    names = []
    for record in batches:
        if type(record) is not dict or set(record) != {"file", "sha256", "bytes", "rows"}:
            raise ProviderVerificationError("invalid batch record")
        names.append(record["file"])
    if len(names) != len(set(names)):
        raise ProviderVerificationError("duplicate selected batch")
    raw_lock = json.dumps(
        batches, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    if hashlib.sha256(raw_lock).hexdigest() != release.get("batch_lock_sha256"):
        raise ProviderVerificationError("batch lock mismatch")
    manifest_names = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if manifest_names != names:
        raise ProviderVerificationError("manifest mismatch")
    if set(annotations) != {"_note", "ds-flash-v1", "ds-flash-v1-boundary-note", "ds-flash-v2", "ds-flash-ambiguous", "qwen3-coder-flash", "glm-5"}:
        raise ProviderVerificationError("unexpected annotation keys")

    mapping: dict[str, str] = {}
    selected = set(names)
    for group in GROUPS:
        members = annotations[group]
        if type(members) is not list:
            raise ProviderVerificationError("annotation group is not a list")
        for name in members:
            if type(name) is not str or name not in selected or name in mapping:
                raise ProviderVerificationError("invalid or duplicate annotation member")
            mapping[name] = group

    groups = {}
    for group in GROUPS:
        provider, model, status = GROUP_METADATA[group]
        members = [record for record in batches if mapping.get(record["file"]) == group]
        groups[group] = {
            "provider": provider,
            "model": model,
            "annotation_status": status,
            "batches": len(members),
            "rows": sum(record["rows"] for record in members),
            "bytes": sum(record["bytes"] for record in members),
        }
    batch_rows = []
    for record in batches:
        group = mapping.get(record["file"])
        if group is None:
            provider = model = None
            status = "unmapped"
        else:
            provider, model, status = GROUP_METADATA[group]
        batch_rows.append(
            {
                **record,
                "annotation_group": group,
                "provider": provider,
                "model": model,
                "annotation_status": status,
            }
        )
    mapped = [row for row in batch_rows if row["annotation_group"] is not None]
    exact = [row for row in batch_rows if row["annotation_status"] in {"annotated-version", "annotated-model"}]
    unmapped = [row for row in batch_rows if row["annotation_group"] is None]
    return {
        "protocol": "release-provider-provenance-inventory-v1",
        "status": "PARTIAL_NOT_RELEASE_CLEARED",
        "release": {
            "version": release.get("version"),
            "release_commit": release.get("release_commit"),
            "batch_lock_sha256": release.get("batch_lock_sha256"),
            "batches": len(batch_rows),
            "rows": sum(row["rows"] for row in batch_rows),
        },
        "input_sha256": {
            "release_descriptor": digest(release_path),
            "batch_registry": digest(registry_path),
            "ordered_manifest": digest(manifest_path),
            "generator_annotations": digest(annotations_path),
        },
        "scope": {
            "card_payloads_read": False,
            "labels_or_predictions_read": False,
            "prospective_resources_read": False,
            "provider_terms_interpreted": False,
            "release_cleared": False,
            "counts_as_distinct_claim_evidence": False,
        },
        "coverage": {
            "mapped_batches": len(mapped),
            "mapped_rows": sum(row["rows"] for row in mapped),
            "exact_version_or_model_batches": len(exact),
            "exact_version_or_model_rows": sum(row["rows"] for row in exact),
            "version_boundary_ambiguous_batches": groups["ds-flash-ambiguous"]["batches"],
            "version_boundary_ambiguous_rows": groups["ds-flash-ambiguous"]["rows"],
            "unmapped_batches": len(unmapped),
            "unmapped_rows": sum(row["rows"] for row in unmapped),
        },
        "groups": groups,
        "batches": batch_rows,
        "unmapped_batch_files": [row["file"] for row in unmapped],
        "annotation_notes": {
            "general": annotations["_note"],
            "deepseek_version_boundary": annotations["ds-flash-v1-boundary-note"],
        },
    }


def verify(inventory: dict[str, Any], recomputed: dict[str, Any]) -> None:
    if inventory != recomputed:
        raise ProviderVerificationError("inventory differs from independent reconstruction")
    if inventory["scope"] != {
        "card_payloads_read": False,
        "labels_or_predictions_read": False,
        "prospective_resources_read": False,
        "provider_terms_interpreted": False,
        "release_cleared": False,
        "counts_as_distinct_claim_evidence": False,
    }:
        raise ProviderVerificationError("unsafe scope")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = object_from(args.inventory)
    rebuilt = recompute(args.release, args.registry, args.manifest, args.annotations)
    verify(inventory, rebuilt)
    receipt = {
        "protocol": "release-provider-provenance-independent-verification-v1",
        "status": "PASS",
        "inventory_sha256": digest(args.inventory),
        "release": inventory["release"],
        "coverage": inventory["coverage"],
        "card_payloads_read": False,
        "release_cleared": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "RELEASE_PROVIDER_PROVENANCE_VERIFIER=PASS "
        f"batches={inventory['release']['batches']} rows={inventory['release']['rows']} "
        f"unmapped_batches={inventory['coverage']['unmapped_batches']} "
        f"unmapped_rows={inventory['coverage']['unmapped_rows']} release_cleared=false"
    )


if __name__ == "__main__":
    main()
