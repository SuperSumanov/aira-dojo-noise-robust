"""Build a metadata-only provider provenance inventory for a corpus release.

The builder binds an immutable release descriptor, ordered batch registry,
ordered manifest, and the historical generator-version annotation.  It never
opens a card payload.  Its purpose is to quantify which release batches can be
routed to a provider/model terms review and which remain provenance-blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ProviderInventoryError(RuntimeError):
    """Raised when provider provenance cannot be inventoried safely."""


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderInventoryError(f"cannot read JSON object: {path}") from exc
    if type(value) is not dict:
        raise ProviderInventoryError(f"expected JSON object: {path}")
    return value


def canonical_batch_lock(records: list[dict[str, Any]]) -> str:
    raw = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_manifest(path: Path) -> list[str]:
    names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not names or len(names) != len(set(names)):
        raise ProviderInventoryError("manifest must be non-empty and duplicate-free")
    return names


def load_release_batches(
    release_path: Path, registry_path: Path, manifest_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    release = read_object(release_path)
    registry = read_object(registry_path)
    if release.get("schema_version") != "aira-dojo-corpus-release-v1":
        raise ProviderInventoryError("unexpected release schema")
    if registry.get("schema_version") != "aira-dojo-corpus-batch-registry-v1":
        raise ProviderInventoryError("unexpected registry schema")
    batches = registry.get("batches")
    if type(batches) is not list or not batches:
        raise ProviderInventoryError("registry batches must be a non-empty list")
    names: list[str] = []
    for index, record in enumerate(batches):
        if type(record) is not dict or set(record) != {"file", "sha256", "bytes", "rows"}:
            raise ProviderInventoryError(f"invalid registry record {index}")
        name = record["file"]
        if type(name) is not str or Path(name).name != name:
            raise ProviderInventoryError(f"unsafe registry filename at {index}")
        if type(record["rows"]) is not int or record["rows"] <= 0:
            raise ProviderInventoryError(f"invalid row count at {index}")
        if type(record["bytes"]) is not int or record["bytes"] <= 0:
            raise ProviderInventoryError(f"invalid byte count at {index}")
        if type(record["sha256"]) is not str or len(record["sha256"]) != 64:
            raise ProviderInventoryError(f"invalid batch hash at {index}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ProviderInventoryError("duplicate registry filename")
    count = release.get("batch_count")
    if type(count) is not int or count <= 0 or count > len(batches):
        raise ProviderInventoryError("invalid release batch_count")
    selected = batches[:count]
    if canonical_batch_lock(selected) != release.get("batch_lock_sha256"):
        raise ProviderInventoryError("release batch lock mismatch")
    manifest = load_manifest(manifest_path)
    if manifest != [record["file"] for record in selected]:
        raise ProviderInventoryError("ordered manifest does not equal selected release prefix")
    output = release.get("output")
    if type(output) is not dict or output.get("rows") != sum(record["rows"] for record in selected):
        raise ProviderInventoryError("release output rows do not equal selected batch rows")
    return release, selected


def load_group_mapping(path: Path, selected_names: set[str]) -> tuple[dict[str, str], dict[str, Any]]:
    annotations = read_object(path)
    if set(annotations) != {"_note", "ds-flash-v1", "ds-flash-v1-boundary-note", "ds-flash-v2", "ds-flash-ambiguous", "qwen3-coder-flash", "glm-5"}:
        raise ProviderInventoryError("unexpected generator annotation keys")
    if type(annotations["_note"]) is not str or type(annotations["ds-flash-v1-boundary-note"]) is not str:
        raise ProviderInventoryError("generator annotation notes must be strings")
    mapping: dict[str, str] = {}
    for group in GROUPS:
        files = annotations[group]
        if type(files) is not list or any(type(name) is not str for name in files):
            raise ProviderInventoryError(f"generator group {group} must be a string list")
        for name in files:
            if name in mapping:
                raise ProviderInventoryError(f"batch mapped more than once: {name}")
            if name not in selected_names:
                raise ProviderInventoryError(f"annotation references batch outside release: {name}")
            mapping[name] = group
    return mapping, annotations


def build_inventory(
    release_path: Path,
    registry_path: Path,
    manifest_path: Path,
    annotations_path: Path,
) -> dict[str, Any]:
    release, batches = load_release_batches(release_path, registry_path, manifest_path)
    selected_names = {record["file"] for record in batches}
    mapping, annotations = load_group_mapping(annotations_path, selected_names)

    groups: dict[str, Any] = {}
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

    batch_records = []
    for record in batches:
        group = mapping.get(record["file"])
        if group is None:
            provider = model = None
            status = "unmapped"
        else:
            provider, model, status = GROUP_METADATA[group]
        batch_records.append(
            {
                **record,
                "annotation_group": group,
                "provider": provider,
                "model": model,
                "annotation_status": status,
            }
        )

    mapped = [record for record in batch_records if record["annotation_group"] is not None]
    exact = [
        record
        for record in batch_records
        if record["annotation_status"] in {"annotated-version", "annotated-model"}
    ]
    unmapped = [record for record in batch_records if record["annotation_group"] is None]
    total_rows = sum(record["rows"] for record in batch_records)
    return {
        "protocol": "release-provider-provenance-inventory-v1",
        "status": "PARTIAL_NOT_RELEASE_CLEARED",
        "release": {
            "version": release.get("version"),
            "release_commit": release.get("release_commit"),
            "batch_lock_sha256": release.get("batch_lock_sha256"),
            "batches": len(batch_records),
            "rows": total_rows,
        },
        "input_sha256": {
            "release_descriptor": sha256(release_path),
            "batch_registry": sha256(registry_path),
            "ordered_manifest": sha256(manifest_path),
            "generator_annotations": sha256(annotations_path),
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
            "mapped_rows": sum(record["rows"] for record in mapped),
            "exact_version_or_model_batches": len(exact),
            "exact_version_or_model_rows": sum(record["rows"] for record in exact),
            "version_boundary_ambiguous_batches": groups["ds-flash-ambiguous"]["batches"],
            "version_boundary_ambiguous_rows": groups["ds-flash-ambiguous"]["rows"],
            "unmapped_batches": len(unmapped),
            "unmapped_rows": sum(record["rows"] for record in unmapped),
        },
        "groups": groups,
        "batches": batch_records,
        "unmapped_batch_files": [record["file"] for record in unmapped],
        "annotation_notes": {
            "general": annotations["_note"],
            "deepseek_version_boundary": annotations["ds-flash-v1-boundary-note"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_inventory(args.release, args.registry, args.manifest, args.annotations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    coverage = payload["coverage"]
    print(
        "RELEASE_PROVIDER_PROVENANCE_INVENTORY=PASS "
        f"batches={payload['release']['batches']} rows={payload['release']['rows']} "
        f"mapped_batches={coverage['mapped_batches']} mapped_rows={coverage['mapped_rows']} "
        f"unmapped_batches={coverage['unmapped_batches']} unmapped_rows={coverage['unmapped_rows']} "
        "release_cleared=false"
    )


if __name__ == "__main__":
    main()
