"""Synthetic end-to-end tests for the frozen late-artifact validator."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


CAPS = [30.0, 60.0, 120.0, 240.0, 360.0, 480.0, 600.0]
MANIFEST_SHA = "f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1"
IMAGE_SHA = "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda"
GRADER_SHA = "2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002"


def file_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_fixture(root: Path, manifest: list[dict], mode: str) -> Path:
    out = root / mode
    materialized = []
    artifact = b"id,pred\n1,0.5\n"
    artifact_sha = file_sha(artifact)
    for index, card in enumerate(manifest):
        card_dir = out / "cards" / hashlib.sha256(card["card_id"].encode("utf-8")).hexdigest()
        snapshot_dir = card_dir / "snapshots"
        snapshot_dir.mkdir(parents=True)
        records = []
        for cap in CAPS:
            copied = False
            score = None
            grade_rc = None
            grade_wall = None
            relative = None
            if mode == "taskhazard" and index < 2 and cap >= 240:
                copied, score, grade_rc, grade_wall = True, 0.5, 0, 0.1
            if mode == "ambiguous" and index == 0 and cap >= 120:
                copied, grade_rc, grade_wall = True, 0, 0.1
                score = 0.5 if cap >= 240 else None
            if copied:
                relative = f"snapshots/submission_t{int(cap)}.csv"
                (card_dir / relative).write_bytes(artifact)
            record = {
                "card_id": card["card_id"],
                "competition": card["competition"],
                "cap_s": cap,
                "manifest_sha256": MANIFEST_SHA,
                "container_sha256": IMAGE_SHA,
                "grader_sha256": GRADER_SHA,
                "snapshot_elapsed_s": cap + 0.01,
                "capture_completed_elapsed_s": cap + 0.02,
                "process_alive": True,
                "process_rc_at_snapshot": None,
                "sub_copied": copied,
                "snapshot_relpath": relative,
                "sub_size": len(artifact) if copied else None,
                "sub_sha256": artifact_sha if copied else None,
                "sub_source_changed_during_copy": False if copied else None,
                "sub_copy_error": None,
                "sub_score": score,
                "grade_rc": grade_rc,
                "grade_wall_s": grade_wall,
                "final_rc": -9,
                "wall_s": 600.2,
            }
            records.append(record)
            materialized.append(record)
        (card_dir / "records.json").write_text(
            json.dumps(records, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    (out / "trajectory_records.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in materialized
        ),
        encoding="utf-8",
    )
    return out


def main() -> None:
    repo = Path.cwd()
    manifest_path = repo / "phase1/late_artifact_pilot_manifest.jsonl"
    audit_path = repo / "phase1/late_artifact_pilot_manifest.audit.json"
    validator = repo / "phase1/validate_late_artifact_pilot.py"
    manifest = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with tempfile.TemporaryDirectory(prefix="late-validator-fixture-") as temporary:
        root = Path(temporary)
        expected = {
            "never": "SCHEMA-FIRST-CANDIDATE",
            "taskhazard": "TASKHAZARD-CANDIDATE",
            "ambiguous": "INCONCLUSIVE",
        }
        for mode, decision in expected.items():
            out = build_fixture(root, manifest, mode)
            subprocess.run(
                [
                    sys.executable,
                    str(validator),
                    "--manifest",
                    str(manifest_path),
                    "--audit",
                    str(audit_path),
                    "--out-dir",
                    str(out),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(
                (out / "late_artifact_validation.json").read_text(encoding="utf-8")
            )
            assert result["decision"] == decision, (mode, result)
    print("LATE_ARTIFACT_VALIDATOR_INTEGRATION_PASS", "never/taskhazard/ambiguous")


if __name__ == "__main__":
    main()
