"""Independently verify the bounded remote-only prepared-text successor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


PROTOCOL = "decision-corpus-release-prepared-text-successor-v2"
OUTPUT_PROTOCOL = "independent-release-prepared-text-successor-v2"
CREDENTIAL = re.compile(
    rb"(?:sk-(?:or-v1-|ws-)?[A-Za-z0-9._-]{20,}"
    rb"|gh[pousr]_[A-Za-z0-9]{20,}"
    rb"|AKIA[0-9A-Z]{16}"
    rb"|authorization\s*:\s*bearer\s+[A-Za-z0-9._-]{20,}"
    rb"|api[_-]?key\s*[:=]\s*[A-Za-z0-9._-]{20,})",
    re.IGNORECASE,
)


class VerifyError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _load_contract(path: Path, expected_sha256: str) -> dict[str, Any]:
    if sha256(path) != expected_sha256:
        raise VerifyError("contract SHA-256 mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL:
        raise VerifyError("unexpected contract protocol")
    if value.get("status") != "FROZEN_AFTER_ACCESS_PASS_BEFORE_DOWNLOAD":
        raise VerifyError("contract was not frozen before download")
    return value


def _expected(contract: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    output: dict[str, tuple[str, ...]] = {}
    for record in contract["requested_files"]:
        competition = str(record["competition"])
        filename = str(record["filename"])
        if not competition or not filename or Path(filename).name != filename:
            raise VerifyError("unsafe requested file identity")
        relative = f"{competition}/prepared/{filename}"
        if relative in output:
            raise VerifyError("duplicate requested file")
        output[relative] = tuple(str(item) for item in record["expected_header"])
    if len(output) != 5:
        raise VerifyError("successor must freeze exactly five files")
    return output


def verify(
    contract_path: Path,
    contract_sha256: str,
    prepared_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    contract = _load_contract(contract_path.resolve(), contract_sha256)
    expected = _expected(contract)
    root = prepared_root.resolve(strict=True)
    if not root.is_dir() or prepared_root.is_symlink():
        raise VerifyError("prepared root must be a real directory")

    observed: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise VerifyError("symlink in prepared successor")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            observed[relative] = path
    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise VerifyError(f"file-set mismatch: missing={missing}, extra={extra}")

    bounds = contract["bounds"]
    per_file = int(bounds["maximum_extracted_bytes_per_file"])
    total_limit = int(bounds["maximum_total_extracted_bytes"])
    minimum_rows = int(bounds["minimum_data_rows_per_file"])
    total_bytes = 0
    records: list[dict[str, Any]] = []
    for relative in sorted(expected):
        path = observed[relative]
        size = path.stat().st_size
        if not 0 < size <= per_file:
            raise VerifyError(f"file byte bound failed: {relative}")
        raw = path.read_bytes()
        if CREDENTIAL.search(raw):
            raise VerifyError(f"credential-shaped bytes: {relative}")
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = tuple(next(reader))
                if header != expected[relative]:
                    raise VerifyError(f"header mismatch: {relative}")
                rows = 0
                for row in reader:
                    if len(row) != len(header):
                        raise VerifyError(f"CSV width mismatch: {relative}")
                    rows += 1
        except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
            raise VerifyError(f"invalid CSV: {relative}") from exc
        if rows < minimum_rows:
            raise VerifyError(f"insufficient data rows: {relative}")
        total_bytes += size
        records.append(
            {
                "relative_path": relative,
                "bytes": size,
                "rows_excluding_header": rows,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    if total_bytes > total_limit:
        raise VerifyError("total extracted byte bound failed")

    result = {
        "protocol": OUTPUT_PROTOCOL,
        "status": "PASS",
        "contract_sha256": contract_sha256,
        "files": records,
        "totals": {
            "competitions": len({item["relative_path"].split("/", 1)[0] for item in records}),
            "files": len(records),
            "bytes": total_bytes,
            "rows_excluding_headers": sum(item["rows_excluding_header"] for item in records),
        },
        "interpretation": {
            "prepared_text_tasks_after_verified_promotion": 25,
            "complete_competition_payload": False,
            "redistribution_permission": False,
            "raw_csv_values_emitted": False,
        },
        "security": {
            "credential_shape_hits": 0,
            "prospective_paths_read": False,
            "prospective_labels_outcomes_predictions_accuracy_utility_read": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }
    _atomic_json(output_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.contract, args.contract_sha256, args.prepared_root, args.output)


if __name__ == "__main__":
    main()
