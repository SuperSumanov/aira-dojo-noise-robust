"""Independent raw-record verifier for the frozen late-artifact pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


CAPS = [30.0, 60.0, 120.0, 240.0, 360.0, 480.0, 600.0]
LOCKS = {
    "manifest": "f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1",
    "image": "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda",
    "grader": "2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002",
}


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/late_artifact_pilot_manifest.jsonl")
    parser.add_argument("--out-dir", default="phase1/late_artifact_pilot_v1")
    return parser.parse_args()


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def main() -> None:
    args = cli()
    manifest_path = Path(args.manifest)
    out_dir = Path(args.out_dir)
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != LOCKS["manifest"]:
        raise AssertionError("manifest hash changed")
    manifest_rows = jsonl(manifest_path)
    manifest = {str(row["card_id"]): row for row in manifest_rows}
    if len(manifest) != 6 or len(manifest_rows) != 6:
        raise AssertionError("manifest cardinality/uniqueness")
    if len({row["competition"] for row in manifest_rows}) != 6:
        raise AssertionError("task uniqueness")

    transactions = sorted((out_dir / "cards").glob("*/records.json"))
    if len(transactions) != 6:
        raise AssertionError(f"transaction count {len(transactions)}")
    raw_rows: list[dict] = []
    early_exits = full_cap_alive = stable = finite_scores = racy = 0
    final_rc_counts: dict[str, int] = {}
    per_card = []
    for transaction in transactions:
        rows = json.loads(transaction.read_text(encoding="utf-8"))
        if sorted(float(row["cap_s"]) for row in rows) != CAPS or len(rows) != 7:
            raise AssertionError(f"checkpoint grid {transaction}")
        rows.sort(key=lambda row: float(row["cap_s"]))
        card_ids = {str(row["card_id"]) for row in rows}
        if len(card_ids) != 1:
            raise AssertionError("mixed card transaction")
        card = next(iter(card_ids))
        if card not in manifest:
            raise AssertionError(card)
        if transaction.parent.name != hashlib.sha256(card.encode()).hexdigest():
            raise AssertionError("transaction path hash")
        card_finite = 0
        for row in rows:
            if row["manifest_sha256"] != LOCKS["manifest"]:
                raise AssertionError("record manifest hash")
            if row["container_sha256"] != LOCKS["image"] or row["grader_sha256"] != LOCKS["grader"]:
                raise AssertionError("record provenance hash")
            if str(row["competition"]) != str(manifest[card]["competition"]):
                raise AssertionError("record task")
            cap = float(row["cap_s"])
            elapsed = float(row["snapshot_elapsed_s"])
            completed = float(row["capture_completed_elapsed_s"])
            if row["process_alive"]:
                if not 0.0 <= elapsed - cap <= 0.5:
                    raise AssertionError("live timing")
            elif row["process_rc_at_snapshot"] is None or elapsed > cap + 0.5:
                raise AssertionError("exited timing")
            if not 0.0 <= completed - elapsed <= 1.0:
                raise AssertionError("capture lag")
            is_racy = bool(row.get("sub_source_changed_during_copy")) or row.get("sub_copy_error") is not None
            racy += int(is_racy and bool(row.get("sub_copied")))
            is_stable = bool(row.get("sub_copied")) and not is_racy
            stable += int(is_stable)
            if finite(row.get("sub_score")):
                if not is_stable or row.get("grade_rc") != 0:
                    raise AssertionError("finite score provenance")
                finite_scores += 1
                card_finite += 1
            elif row.get("sub_score") is not None:
                raise AssertionError("nonfinite numeric/string sub score")
            raw_rows.append(row)
        final = rows[-1]
        full_cap_alive += int(bool(final["process_alive"]))
        early_exits += int(not bool(final["process_alive"]))
        final_rc = str(final["final_rc"])
        final_rc_counts[final_rc] = final_rc_counts.get(final_rc, 0) + 1
        per_card.append((card, card_finite, bool(final["process_alive"]), final_rc))

    materialized = jsonl(out_dir / "trajectory_records.jsonl")
    normalize = lambda rows: sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)
    if normalize(raw_rows) != normalize(materialized):
        raise AssertionError("materialized rows differ")
    validation = json.loads((out_dir / "late_artifact_validation.json").read_text(encoding="utf-8"))
    expected = {
        "decision": "SCHEMA-FIRST-CANDIDATE",
        "cards": 6,
        "records": 42,
        "continuous_by_120_cards": 0,
        "late_conversion_cards": 0,
        "late_conversion_tasks": 0,
        "grader_recovery_not_conversion_cards": 0,
        "never_finite_by_600_cards": 6,
        "stable_copied_snapshots": 0,
        "racy_copied_snapshots": 0,
        "finite_graded_snapshots": 0,
    }
    for key, value in expected.items():
        if validation.get(key) != value:
            raise AssertionError(f"validation {key}: {validation.get(key)} != {value}")
    if stable != 0 or finite_scores != 0 or racy != 0:
        raise AssertionError("unexpected artifact counters")
    if full_cap_alive != 2 or early_exits != 4 or final_rc_counts != {"-9": 2, "1": 4}:
        raise AssertionError((full_cap_alive, early_exits, final_rc_counts))
    print(
        "LATE_ARTIFACT_RAW_INDEPENDENT_VERIFY_PASS",
        f"cards={len(per_card)}",
        f"records={len(raw_rows)}",
        f"stable={stable}",
        f"finite={finite_scores}",
        f"full_cap_alive={full_cap_alive}",
        f"early_exit={early_exits}",
        f"final_rc={json.dumps(final_rc_counts, sort_keys=True)}",
        f"decision={validation['decision']}",
    )


if __name__ == "__main__":
    main()
