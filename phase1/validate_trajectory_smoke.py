#!/usr/bin/env python3
"""Frozen validator for the two-card continuous-fidelity infrastructure smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_CAPS = [30.0, 60.0, 120.0]
EXPECTED_IMAGE = "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda"
EXPECTED_GRADER = "2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def atomic_json(path: Path, value: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifest = root / "manifest.jsonl"
        manifest_rows = [
            {"card_id": "card-a", "competition": "task-a"},
            {"card_id": "card-b", "competition": "task-b"},
        ]
        manifest.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest_rows),
            encoding="utf-8",
        )
        manifest_hash = sha256(manifest)
        out = root / "out"
        all_rows = []
        for card in manifest_rows:
            card_dir = out / "cards" / hashlib.sha256(card["card_id"].encode()).hexdigest()
            card_dir.mkdir(parents=True)
            records = []
            for cap in EXPECTED_CAPS:
                records.append({
                    "card_id": card["card_id"],
                    "cap_s": cap,
                    "manifest_sha256": manifest_hash,
                    "container_sha256": EXPECTED_IMAGE,
                    "grader_sha256": EXPECTED_GRADER,
                    "snapshot_elapsed_s": cap + 0.01,
                    "capture_completed_elapsed_s": cap + 0.02,
                    "process_alive": True,
                    "process_rc_at_snapshot": None,
                    "sub_copied": False,
                })
            (card_dir / "records.json").write_text(
                json.dumps(records, indent=2) + "\n", encoding="utf-8"
            )
            all_rows.extend(records)
        (out / "trajectory_records.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in all_rows),
            encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, __file__, "--manifest", str(manifest), "--out-dir", str(out)],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads((out / "smoke_validation.json").read_text(encoding="utf-8"))
        assert result["decision"] == "SMOKE-INCONCLUSIVE" and result["records"] == 6
        print("TRAJECTORY_VALIDATOR_SELF_TEST_PASS", result["records"], result["decision"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.manifest or not args.out_dir:
        ap.error("--manifest and --out-dir are required")
    validation_path = args.out_dir / "smoke_validation.json"
    if validation_path.exists():
        raise RuntimeError("refusing to overwrite smoke validation")
    manifest_sha = sha256(args.manifest)
    manifest = jsonl(args.manifest)
    expected_ids = {str(row["card_id"]) for row in manifest}
    if len(manifest) != 2 or len(expected_ids) != 2:
        raise RuntimeError("smoke manifest must contain two unique cards")

    card_files = sorted((args.out_dir / "cards").glob("*/records.json"))
    if len(card_files) != 2:
        raise RuntimeError(f"expected two card transactions, found {len(card_files)}")
    transaction_rows = []
    timing = []
    stable_copied = 0
    finite_graded = 0
    racy_copied = 0
    for path in card_files:
        records = json.loads(path.read_text(encoding="utf-8"))
        if len(records) != 3 or sorted(float(row["cap_s"]) for row in records) != EXPECTED_CAPS:
            raise RuntimeError(f"checkpoint mismatch: {path}")
        card_ids = {str(row["card_id"]) for row in records}
        if len(card_ids) != 1 or next(iter(card_ids)) not in expected_ids:
            raise RuntimeError(f"card identity mismatch: {path}")
        if path.parent.name != hashlib.sha256(next(iter(card_ids)).encode("utf-8")).hexdigest():
            raise RuntimeError(f"transaction directory name mismatch: {path}")
        for row in records:
            if row["manifest_sha256"] != manifest_sha:
                raise RuntimeError("manifest SHA mismatch in record")
            if row["container_sha256"] != EXPECTED_IMAGE or row["grader_sha256"] != EXPECTED_GRADER:
                raise RuntimeError("image/grader provenance mismatch")
            cap = float(row["cap_s"])
            elapsed = float(row["snapshot_elapsed_s"])
            completed = float(row["capture_completed_elapsed_s"])
            if row["process_alive"]:
                if not (0 <= elapsed - cap <= 0.5):
                    raise RuntimeError(f"live checkpoint timing violation card={row['card_id']} cap={cap}")
            elif elapsed > cap + 0.5 or row["process_rc_at_snapshot"] is None:
                raise RuntimeError(f"exited checkpoint timing/rc violation card={row['card_id']} cap={cap}")
            if not (0 <= completed - elapsed <= 1.0):
                raise RuntimeError(f"capture lag violation card={row['card_id']} cap={cap}")
            timing.append({
                "card_id": row["card_id"],
                "cap_s": cap,
                "snapshot_elapsed_s": elapsed,
                "capture_lag_s": completed - elapsed,
                "process_alive": bool(row["process_alive"]),
            })
            if row["sub_copied"]:
                rel = Path(row["snapshot_relpath"])
                if rel.is_absolute() or ".." in rel.parts:
                    raise RuntimeError("unsafe snapshot path")
                snapshot = path.parent / rel
                if not snapshot.is_file():
                    raise RuntimeError(f"snapshot missing: {snapshot}")
                if snapshot.stat().st_size != row["sub_size"] or sha256(snapshot) != row["sub_sha256"]:
                    raise RuntimeError(f"snapshot hash/size mismatch: {snapshot}")
                if row["sub_source_changed_during_copy"] or row["sub_copy_error"] is not None:
                    racy_copied += 1
                    if row["sub_score"] is not None or row["grade_rc"] is not None:
                        raise RuntimeError("racy snapshot was graded")
                else:
                    stable_copied += 1
                    score = row["sub_score"]
                    if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(float(score)):
                        finite_graded += 1
                        if row["grade_rc"] != 0:
                            raise RuntimeError("finite score with nonzero grader rc")
            transaction_rows.append(row)

    materialized = jsonl(args.out_dir / "trajectory_records.jsonl")
    canonical = lambda rows: sorted(
        [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    )
    if canonical(materialized) != canonical(transaction_rows):
        raise RuntimeError("materialized JSONL differs from atomic transactions")

    decision = "PASS" if finite_graded >= 1 else "SMOKE-INCONCLUSIVE"
    result = {
        "decision": decision,
        "cards": len(card_files),
        "records": len(transaction_rows),
        "stable_copied_snapshots": stable_copied,
        "racy_copied_snapshots": racy_copied,
        "finite_graded_snapshots": finite_graded,
        "manifest_sha256": manifest_sha,
        "image_sha256": EXPECTED_IMAGE,
        "grader_sha256": EXPECTED_GRADER,
        "timing": timing,
    }
    atomic_json(validation_path, result)
    print("TRAJECTORY_SMOKE_VALIDATION", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
