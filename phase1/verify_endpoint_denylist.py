"""Independent verifier for the label-free pre-cutoff endpoint denylist."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


PROTOCOL = "precutoff_endpoint_denylist_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--denylist", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-denylist-sha256", required=True)
    parser.add_argument("--expect-endpoints", required=True, type=int)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite endpoint denylist verification")
    if sha256(args.cards) != args.expect_cards_sha256.lower():
        raise RuntimeError("cards SHA mismatch")
    if sha256(args.denylist) != args.expect_denylist_sha256.lower():
        raise RuntimeError("denylist SHA mismatch")

    expected = []
    seen = set()
    with args.cards.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            card_id = str(value["id"])
            if card_id in seen:
                raise RuntimeError("duplicate card ID in source")
            seen.add(card_id)
            expected.append(
                (card_id, hashlib.sha256(str(value.get("code") or "").encode("utf-8")).hexdigest())
            )
    expected.sort()
    actual = []
    with args.denylist.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        if next(reader, None) != ["card_id", "code_sha256"]:
            raise RuntimeError("denylist header mismatch")
        for row in reader:
            if len(row) != 2:
                raise RuntimeError("denylist row width mismatch")
            actual.append((row[0], row[1]))
    if expected != actual or len(actual) != args.expect_endpoints:
        raise RuntimeError("independent denylist reconstruction differs")
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    if (
        summary.get("status") != "PRECUTOFF_ENDPOINT_DENYLIST_COMPLETE"
        or summary.get("protocol") != PROTOCOL
        or summary.get("outputs", {}).get("endpoint_denylist_sha256") != sha256(args.denylist)
    ):
        raise RuntimeError("producer summary mismatch")
    result = {
        "status": "VERIFIED_PRECUTOFF_ENDPOINT_DENYLIST_COMPLETE",
        "protocol": PROTOCOL,
        "endpoints": len(actual),
        "unique_code_sha256": len({row[1] for row in actual}),
        "cards_sha256": sha256(args.cards),
        "endpoint_denylist_sha256": sha256(args.denylist),
        "exact_rows": True,
        "source_contains_label_fields": True,
        "selected_source_keys": ["id", "code"],
        "labels_used": False,
        "label_values_printed": False,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(
        result["status"],
        f"endpoints={result['endpoints']}",
        f"unique_code_sha256={result['unique_code_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
