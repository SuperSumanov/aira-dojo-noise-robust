#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


state = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
if output.exists():
    raise SystemExit("output already exists")
latest_before = (state / "LATEST").read_text(encoding="ascii").strip()
snapshot = state / "snapshots" / latest_before
transactions = [
    json.loads(line)
    for line in (snapshot / "transactions.jsonl").read_text(encoding="utf-8").splitlines()
]
temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
manifest = []
try:
    for row in transactions:
        intake = Path(row["intake_dir"]).resolve()
        if intake.parent != (state / "intakes").resolve():
            raise RuntimeError("intake path escapes the production intake root")
        target = temporary / intake.name
        target.mkdir()
        summary = intake / "summary.json"
        provenance = intake / "source_provenance.json"
        if digest(summary) != row["intake_summary_sha256"]:
            raise RuntimeError("transaction intake summary hash mismatch")
        summary_value = json.loads(summary.read_text(encoding="utf-8"))
        provenance_sha = digest(provenance)
        if (
            (summary_value.get("outputs") or {}).get("source_provenance_sha256")
            != provenance_sha
        ):
            raise RuntimeError("intake provenance hash mismatch")
        shutil.copyfile(summary, target / "summary.json")
        shutil.copyfile(provenance, target / "source_provenance.json")
        manifest.append(
            {
                "archive_relative_path": row["archive_relative_path"],
                "archive_sha256": row["archive_sha256"],
                "intake": intake.name,
                "source_provenance_sha256": provenance_sha,
                "summary_sha256": row["intake_summary_sha256"],
            }
        )
    latest_after = (state / "LATEST").read_text(encoding="ascii").strip()
    if latest_after != latest_before:
        raise RuntimeError("LATEST advanced while freezing safe sidecars")
    receipt = {
        "input_snapshot_sha256": latest_before,
        "intakes": len(manifest),
        "labels_or_outcomes_read": False,
        "manifest": manifest,
        "protocol": "score_channel_safe_sidecar_snapshot_v1",
    }
    (temporary / "SNAPSHOT_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
except Exception:
    shutil.rmtree(temporary)
    raise
print(
    json.dumps(
        {"intakes": len(manifest), "snapshot_sha256": latest_before},
        sort_keys=True,
    )
)
