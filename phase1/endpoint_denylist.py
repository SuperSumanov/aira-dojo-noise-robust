"""Build and load a label-free pre-cutoff endpoint/code denylist."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


PROTOCOL = "precutoff_endpoint_denylist_v1"
FIELDS = ("card_id", "code_sha256")
SHA256_RX = re.compile(r"[0-9a-f]{64}")


class DenylistError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_endpoint_denylist(
    path: Path,
    expected_sha256: str,
    expected_endpoints: int | None = None,
) -> tuple[set[str], set[str], dict[str, int]]:
    if sha256(path) != expected_sha256.lower():
        raise DenylistError("endpoint denylist SHA mismatch")
    card_ids: list[str] = []
    code_shas: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise DenylistError("endpoint denylist schema mismatch")
        for line_number, row in enumerate(reader, 2):
            if set(row) != set(FIELDS):
                raise DenylistError(f"endpoint denylist row schema mismatch at line {line_number}")
            card_id = str(row["card_id"])
            code_sha = str(row["code_sha256"])
            if not card_id or any(character in card_id for character in "\r\n\t"):
                raise DenylistError(f"invalid endpoint ID at line {line_number}")
            if not SHA256_RX.fullmatch(code_sha):
                raise DenylistError(f"invalid code SHA at line {line_number}")
            card_ids.append(card_id)
            code_shas.append(code_sha)
    if not card_ids:
        raise DenylistError("empty endpoint denylist")
    if card_ids != sorted(card_ids) or len(set(card_ids)) != len(card_ids):
        raise DenylistError("endpoint denylist IDs must be unique and sorted")
    if expected_endpoints is not None and len(card_ids) != expected_endpoints:
        raise DenylistError("endpoint denylist inventory mismatch")
    return set(card_ids), set(code_shas), {
        "endpoint_ids": len(card_ids),
        "unique_code_sha256": len(set(code_shas)),
    }


def build(args: argparse.Namespace) -> int:
    if args.output.exists() or args.summary.exists():
        raise FileExistsError("refusing to overwrite endpoint denylist artifacts")
    if sha256(args.cards) != args.expect_cards_sha256.lower():
        raise DenylistError("cards SHA mismatch")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with args.cards.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value: dict[str, Any] = json.loads(line)
            card_id = str(value.get("id") or "")
            if not card_id or card_id in seen:
                raise DenylistError(f"missing/duplicate endpoint ID at source line {line_number}")
            code = str(value.get("code") or "")
            rows.append(
                {
                    "card_id": card_id,
                    "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                }
            )
            seen.add(card_id)
    rows.sort(key=lambda row: row["card_id"])
    if args.expect_endpoints is not None and len(rows) != args.expect_endpoints:
        raise DenylistError("endpoint inventory mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, args.output)
    output_sha = sha256(args.output)
    _, _, audit = load_endpoint_denylist(args.output, output_sha)
    summary = {
        "status": "PRECUTOFF_ENDPOINT_DENYLIST_COMPLETE",
        "protocol": PROTOCOL,
        "inputs": {"cards_sha256": sha256(args.cards)},
        "inventory": audit,
        "outputs": {
            "endpoint_denylist": str(args.output),
            "endpoint_denylist_sha256": output_sha,
        },
        "source_contains_label_fields": True,
        "selected_source_keys": ["id", "code"],
        "labels_used": False,
        "label_values_printed": False,
    }
    atomic_json(args.summary, summary)
    print(
        summary["status"],
        f"endpoints={audit['endpoint_ids']}",
        f"unique_code_sha256={audit['unique_code_sha256']}",
        "labels_used=false",
        flush=True,
    )
    return 0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-endpoints", type=int)
    return parser.parse_args()


def main() -> int:
    return build(arguments())


if __name__ == "__main__":
    raise SystemExit(main())
