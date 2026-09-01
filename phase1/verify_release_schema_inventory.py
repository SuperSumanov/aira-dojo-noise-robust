"""Independent verifier for a value-free release schema inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    pass


def digest_raw(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def digest_lf(path: Path) -> str:
    digest = hashlib.sha256()
    pending_cr = False
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            if pending_cr:
                block = b"\r" + block
                pending_cr = False
            if block.endswith(b"\r"):
                block = block[:-1]
                pending_cr = True
            digest.update(block.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    if pending_cr:
        digest.update(b"\n")
    return digest.hexdigest()


def kind(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if type(value) is str:
        return "string"
    if type(value) is dict:
        return "object"
    if type(value) is list:
        return "array"
    raise VerificationError(f"unsupported type {type(value).__name__}")


def independently_inventory(path: Path) -> dict[str, Any]:
    occurrences: Counter[str] = Counter()
    presence: Counter[str] = Counter()
    nulls: Counter[str] = Counter()
    type_counts: dict[str, Counter[str]] = {}
    array_bounds: dict[str, list[int]] = {}
    rows = 0

    def visit(value: Any, field_path: str, seen: set[str]) -> None:
        value_kind = kind(value)
        occurrences[field_path] += 1
        type_counts.setdefault(field_path, Counter())[value_kind] += 1
        if value is None:
            nulls[field_path] += 1
        if field_path not in seen:
            presence[field_path] += 1
            seen.add(field_path)
        if type(value) is dict:
            for key, child in value.items():
                visit(child, f"{field_path}.{key}" if field_path != "$" else f"$.{key}", seen)
        elif type(value) is list:
            array_bounds.setdefault(field_path, []).append(len(value))
            for child in value:
                visit(child, f"{field_path}[]", seen)

    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid JSON at {path}:{line_number}") from exc
            if type(row) is not dict:
                raise VerificationError(f"non-object row at {path}:{line_number}")
            rows += 1
            visit(row, "$", set())
    fields = {}
    for field_path in sorted(occurrences):
        lengths = array_bounds.get(field_path, [])
        fields[field_path] = {
            "occurrences": occurrences[field_path],
            "presence_rows": presence[field_path],
            "missing_rows": rows - presence[field_path],
            "null_occurrences": nulls[field_path],
            "type_counts": dict(sorted(type_counts[field_path].items())),
            "array_length_min": min(lengths) if lengths else None,
            "array_length_max": max(lengths) if lengths else None,
        }
    return {
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256_raw": digest_raw(path),
        "sha256_normalized_lf": digest_lf(path),
        "fields": fields,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.inventory.read_text(encoding="utf-8"))
    if payload.get("protocol") != "release-schema-inventory-v1":
        raise VerificationError("unexpected inventory protocol")
    expected_scope = {
        "source_values_emitted": False,
        "candidate_identities_emitted": False,
        "labels_or_predictions_emitted": False,
        "prospective_resources_read": False,
    }
    if payload.get("scope") != expected_scope:
        raise VerificationError("unsafe or incomplete inventory scope")

    root = args.root.resolve()
    checked = {}
    total_rows = 0
    for label, recorded in sorted(payload.get("resources", {}).items()):
        resource = (root / recorded["path"]).resolve()
        if root not in resource.parents:
            raise VerificationError(f"resource escapes root: {recorded['path']}")
        recomputed = independently_inventory(resource)
        expected = {key: recorded[key] for key in recomputed}
        if recomputed != expected:
            raise VerificationError(f"inventory mismatch for {label}")
        total_rows += recomputed["rows"]
        checked[label] = {
            "rows": recomputed["rows"],
            "field_paths": len(recomputed["fields"]),
            "sha256_normalized_lf": recomputed["sha256_normalized_lf"],
        }

    receipt = {
        "protocol": "release-schema-inventory-independent-verification-v1",
        "status": "PASS",
        "inventory_sha256": digest_raw(args.inventory),
        "resources": checked,
        "total_rows": total_rows,
        "source_values_emitted": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "RELEASE_SCHEMA_INVENTORY_VERIFIER=PASS "
        f"resources={len(checked)} rows={total_rows} source_values_emitted=false"
    )


if __name__ == "__main__":
    main()
