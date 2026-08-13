#!/usr/bin/env python3
"""Frozen validator and route adjudicator for the six-card late-artifact pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


CAPS = [30.0, 60.0, 120.0, 240.0, 360.0, 480.0, 600.0]
MANIFEST_SHA = "f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1"
IMAGE_SHA = "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda"
GRADER_SHA = "2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002"
INPUT_LOCKS = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "runtime": "dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
}


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=Path("phase1/late_artifact_pilot_manifest.jsonl"))
    p.add_argument("--audit", type=Path, default=Path("phase1/late_artifact_pilot_manifest.audit.json"))
    p.add_argument("--out-dir", type=Path, default=Path("phase1/late_artifact_pilot_v1"))
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def route(late_cards: int, late_tasks: int, ambiguous_cards: int = 0) -> str:
    if late_cards >= 2 and late_tasks >= 2:
        return "TASKHAZARD-CANDIDATE"
    if late_cards == 0 and ambiguous_cards == 0:
        return "SCHEMA-FIRST-CANDIDATE"
    return "INCONCLUSIVE"


def atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def self_test() -> None:
    assert route(2, 2) == "TASKHAZARD-CANDIDATE"
    assert route(3, 1) == "INCONCLUSIVE"
    assert route(1, 1) == "INCONCLUSIVE"
    assert route(0, 0) == "SCHEMA-FIRST-CANDIDATE"
    assert route(0, 0, 1) == "INCONCLUSIVE"
    records = [
        {"cap_s": cap, "sub_score": (0.5 if cap >= 240 else None)} for cap in CAPS
    ]
    finite_caps = [float(row["cap_s"]) for row in records if finite(row["sub_score"])]
    assert min(finite_caps) == 240.0
    print("LATE_ARTIFACT_VALIDATOR_SELF_TEST_PASS")


def main() -> None:
    a = cli()
    if a.self_test:
        self_test()
        return
    validation_path = a.out_dir / "late_artifact_validation.json"
    per_card_path = a.out_dir / "per_card_conversion.csv"
    if validation_path.exists() or per_card_path.exists():
        raise RuntimeError("refusing to overwrite pilot validation")
    if digest(a.manifest) != MANIFEST_SHA:
        raise RuntimeError("pilot manifest SHA mismatch")
    manifest = json_lines(a.manifest)
    manifest_by_id = {str(row["card_id"]): row for row in manifest}
    if len(manifest) != 6 or len(manifest_by_id) != 6:
        raise RuntimeError("pilot manifest must contain six unique cards")
    if len({str(row["competition"]) for row in manifest}) != 6:
        raise RuntimeError("pilot manifest tasks are not unique")
    audit = json.loads(a.audit.read_text(encoding="utf-8"))
    if audit.get("output_manifest_sha256") != MANIFEST_SHA or audit.get("inputs") != INPUT_LOCKS:
        raise RuntimeError("manifest audit lock mismatch")
    selected = audit.get("selected_cards")
    if not isinstance(selected, list) or len(selected) != 6:
        raise RuntimeError("bad selected-card audit")
    selected_ids = {str(row["card_id"]) for row in selected}
    if selected_ids != set(manifest_by_id):
        raise RuntimeError("selected audit/manifest identity mismatch")
    if len({str(row["run_id"]) for row in selected}) != 6:
        raise RuntimeError("pilot physical runs are not unique")
    if any(float(row["historical_runtime_s"]) < 600.0 for row in selected):
        raise RuntimeError("pilot contains short historical runtime")
    if audit.get("final_grade_used_for_selection") is not False or audit.get("stdout_used_for_selection") is not False:
        raise RuntimeError("selection audit reports forbidden signal")

    transactions = sorted((a.out_dir / "cards").glob("*/records.json"))
    if len(transactions) != 6:
        raise RuntimeError(f"expected six transactions, found {len(transactions)}")
    all_rows = []
    timing = []
    per_card = []
    stable_copies = racy_copies = finite_grades = 0
    for path in transactions:
        records = json.loads(path.read_text(encoding="utf-8"))
        if len(records) != len(CAPS) or sorted(float(row["cap_s"]) for row in records) != CAPS:
            raise RuntimeError(f"checkpoint mismatch: {path}")
        records = sorted(records, key=lambda row: float(row["cap_s"]))
        card_ids = {str(row["card_id"]) for row in records}
        if len(card_ids) != 1:
            raise RuntimeError(f"mixed card transaction: {path}")
        card_id = next(iter(card_ids))
        if card_id not in manifest_by_id:
            raise RuntimeError(f"unknown card: {card_id}")
        if path.parent.name != hashlib.sha256(card_id.encode("utf-8")).hexdigest():
            raise RuntimeError(f"transaction directory mismatch: {card_id}")
        finite_rows = []
        stable_rows = []
        for row in records:
            if row["manifest_sha256"] != MANIFEST_SHA:
                raise RuntimeError("record manifest SHA mismatch")
            if row["container_sha256"] != IMAGE_SHA or row["grader_sha256"] != GRADER_SHA:
                raise RuntimeError("image/grader provenance mismatch")
            if row.get("competition") != manifest_by_id[card_id]["competition"]:
                raise RuntimeError("record task mismatch")
            cap = float(row["cap_s"])
            elapsed = float(row["snapshot_elapsed_s"])
            completed = float(row["capture_completed_elapsed_s"])
            if row["process_alive"]:
                if not 0 <= elapsed - cap <= 0.5:
                    raise RuntimeError(f"live timing violation {card_id} {cap}")
            elif elapsed > cap + 0.5 or row["process_rc_at_snapshot"] is None:
                raise RuntimeError(f"exit timing/rc violation {card_id} {cap}")
            if not 0 <= completed - elapsed <= 1.0:
                raise RuntimeError(f"capture lag violation {card_id} {cap}")
            timing.append(
                {
                    "card_id": card_id,
                    "cap_s": cap,
                    "snapshot_elapsed_s": elapsed,
                    "capture_lag_s": completed - elapsed,
                    "process_alive": bool(row["process_alive"]),
                }
            )
            changed = bool(row.get("sub_source_changed_during_copy"))
            copy_error = row.get("sub_copy_error") is not None
            if changed or copy_error:
                racy_copies += int(bool(row.get("sub_copied")))
                if row.get("sub_score") is not None or row.get("grade_rc") is not None:
                    raise RuntimeError("racy/error snapshot was graded")
            if row.get("sub_copied"):
                relative = Path(row["snapshot_relpath"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise RuntimeError("unsafe snapshot path")
                snapshot = path.parent / relative
                if snapshot.is_symlink() or not snapshot.is_file():
                    raise RuntimeError(f"missing snapshot {snapshot}")
                if snapshot.stat().st_size != row["sub_size"] or digest(snapshot) != row["sub_sha256"]:
                    raise RuntimeError(f"snapshot hash/size mismatch {snapshot}")
                if not changed and not copy_error:
                    stable_copies += 1
                    stable_rows.append(row)
            elif row.get("sub_score") is not None or row.get("grade_rc") is not None:
                raise RuntimeError("uncopied snapshot was graded")
            if finite(row.get("sub_score")):
                if row.get("grade_rc") != 0 or changed or copy_error or not row.get("sub_copied"):
                    raise RuntimeError("invalid finite grade provenance")
                if not finite(row.get("grade_wall_s")) or float(row["grade_wall_s"]) < 0:
                    raise RuntimeError("invalid grader timing")
                finite_grades += 1
                finite_rows.append(row)
            all_rows.append(row)
        finite_rows.sort(key=lambda row: float(row["cap_s"]))
        early_finite = [row for row in finite_rows if float(row["cap_s"]) <= 120.0]
        early_stable_hashes = {
            str(row["sub_sha256"])
            for row in stable_rows
            if float(row["cap_s"]) <= 120.0 and row.get("sub_sha256")
        }
        genuinely_late = [
            row
            for row in finite_rows
            if float(row["cap_s"]) > 120.0
            and str(row.get("sub_sha256")) not in early_stable_hashes
        ]
        grader_recovery = [
            row
            for row in finite_rows
            if float(row["cap_s"]) > 120.0
            and str(row.get("sub_sha256")) in early_stable_hashes
        ]
        first_row = (
            early_finite[0]
            if early_finite
            else genuinely_late[0]
            if genuinely_late
            else grader_recovery[0]
            if grader_recovery
            else None
        )
        state = (
            "continuous_by_120"
            if early_finite
            else "late_conversion"
            if genuinely_late
            else "grader_recovery_not_conversion"
            if grader_recovery
            else "never_finite_by_600"
        )
        per_card.append(
            {
                "card_id": card_id,
                "task": str(manifest_by_id[card_id]["competition"]),
                "historical_runtime_s": next(
                    float(row["historical_runtime_s"]) for row in selected if row["card_id"] == card_id
                ),
                "state": state,
                "first_finite_checkpoint_s": (
                    float(first_row["cap_s"]) if first_row is not None else None
                ),
                "first_finite_snapshot_elapsed_s": (
                    float(first_row["snapshot_elapsed_s"]) if first_row is not None else None
                ),
                "first_finite_process_alive": (
                    bool(first_row["process_alive"]) if first_row is not None else None
                ),
                "finite_checkpoint_count": len(finite_rows),
                "stable_by_120_hash_count": len(early_stable_hashes),
                "final_rc": records[-1]["final_rc"],
                "wall_s": records[-1]["wall_s"],
            }
        )

    materialized = json_lines(a.out_dir / "trajectory_records.jsonl")
    canonical = lambda values: sorted(
        json.dumps(row, ensure_ascii=False, sort_keys=True) for row in values
    )
    if canonical(materialized) != canonical(all_rows):
        raise RuntimeError("materialized JSONL differs from transactions")
    late = [row for row in per_card if row["state"] == "late_conversion"]
    early = [row for row in per_card if row["state"] == "continuous_by_120"]
    ambiguous = [row for row in per_card if row["state"] == "grader_recovery_not_conversion"]
    never = [row for row in per_card if row["state"] == "never_finite_by_600"]
    decision = route(len(late), len({row["task"] for row in late}), len(ambiguous))

    with per_card_path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_card[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(per_card, key=lambda row: row["card_id"]))
    result = {
        "decision": decision,
        "cards": len(per_card),
        "records": len(all_rows),
        "continuous_by_120_cards": len(early),
        "late_conversion_cards": len(late),
        "late_conversion_tasks": len({row["task"] for row in late}),
        "grader_recovery_not_conversion_cards": len(ambiguous),
        "never_finite_by_600_cards": len(never),
        "stable_copied_snapshots": stable_copies,
        "racy_copied_snapshots": racy_copies,
        "finite_graded_snapshots": finite_grades,
        "manifest_sha256": MANIFEST_SHA,
        "image_sha256": IMAGE_SHA,
        "grader_sha256": GRADER_SHA,
        "per_card": sorted(per_card, key=lambda row: row["card_id"]),
        "timing": timing,
    }
    atomic_json(validation_path, result)
    print("LATE_ARTIFACT_VALIDATION", json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
