"""Build a value-free schema inventory for release JSONL resources.

The inventory records only field paths, JSON types, presence/null counts, array
length bounds, row counts, byte counts, and hashes.  It never serializes source
values.  This makes schema drift auditable without copying candidate identities,
labels, code, or observations into the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


class InventoryError(RuntimeError):
    """Raised when a release resource cannot be inventoried safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf_sha256(path: Path) -> str:
    """Hash text after CRLF/CR canonicalization without loading it all at once."""

    digest = hashlib.sha256()
    carry = b""
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            data = carry + block
            carry = b""
            if data.endswith(b"\r"):
                data, carry = data[:-1], b"\r"
            digest.update(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    if carry:
        digest.update(b"\n")
    return digest.hexdigest()


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    raise InventoryError(f"unsupported decoded JSON type: {type(value).__name__}")


def new_stat() -> dict[str, Any]:
    return {
        "occurrences": 0,
        "presence_rows": 0,
        "null_occurrences": 0,
        "type_counts": Counter(),
        "array_length_min": None,
        "array_length_max": None,
    }


def walk(
    value: Any,
    path: str,
    stats: dict[str, dict[str, Any]],
    seen_in_row: set[str],
) -> None:
    kind = json_type(value)
    entry = stats.setdefault(path, new_stat())
    entry["occurrences"] += 1
    entry["type_counts"][kind] += 1
    if kind == "null":
        entry["null_occurrences"] += 1
    if path not in seen_in_row:
        entry["presence_rows"] += 1
        seen_in_row.add(path)

    if kind == "object":
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
            walk(child, child_path, stats, seen_in_row)
    elif kind == "array":
        length = len(value)
        low = entry["array_length_min"]
        high = entry["array_length_max"]
        entry["array_length_min"] = length if low is None else min(low, length)
        entry["array_length_max"] = length if high is None else max(high, length)
        for child in value:
            walk(child, f"{path}[]", stats, seen_in_row)


def inventory_jsonl(path: Path) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = {}
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InventoryError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise InventoryError(f"non-object row at {path}:{line_number}")
            rows += 1
            walk(value, "$", stats, set())
    if rows == 0:
        raise InventoryError(f"empty JSONL resource: {path}")

    fields: dict[str, Any] = {}
    for field_path in sorted(stats):
        entry = stats[field_path]
        fields[field_path] = {
            "occurrences": entry["occurrences"],
            "presence_rows": entry["presence_rows"],
            "missing_rows": rows - entry["presence_rows"],
            "null_occurrences": entry["null_occurrences"],
            "type_counts": dict(sorted(entry["type_counts"].items())),
            "array_length_min": entry["array_length_min"],
            "array_length_max": entry["array_length_max"],
        }
    return {
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256_raw": sha256(path),
        "sha256_normalized_lf": normalized_lf_sha256(path),
        "fields": fields,
    }


def parse_resource(specification: str) -> tuple[str, Path]:
    if "=" not in specification:
        raise InventoryError("--resource must be LABEL=PATH")
    label, path_text = specification.split("=", 1)
    if not label or not path_text:
        raise InventoryError("--resource must contain non-empty LABEL and PATH")
    return label, Path(path_text)


def build_inventory(resources: list[tuple[str, Path]]) -> dict[str, Any]:
    if not resources:
        raise InventoryError("at least one --resource is required")
    labels = [label for label, _ in resources]
    if len(labels) != len(set(labels)):
        raise InventoryError("resource labels must be unique")
    payload: dict[str, Any] = {
        "protocol": "release-schema-inventory-v1",
        "scope": {
            "source_values_emitted": False,
            "candidate_identities_emitted": False,
            "labels_or_predictions_emitted": False,
            "prospective_resources_read": False,
        },
        "resources": {},
    }
    for label, path in resources:
        if not path.is_file():
            raise InventoryError(f"missing resource: {path}")
        result = inventory_jsonl(path)
        result["path"] = path.as_posix()
        payload["resources"][label] = result
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resources = [parse_resource(specification) for specification in args.resource]
    payload = build_inventory(resources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "RELEASE_SCHEMA_INVENTORY=PASS "
        f"resources={len(resources)} rows={sum(v['rows'] for v in payload['resources'].values())} "
        "source_values_emitted=false"
    )


if __name__ == "__main__":
    main()
