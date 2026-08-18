"""Build a post-outcome, schema-only diagnostic view of a Probe Contract A/B result.

This never repairs the formal experiment status.  It creates a separate root in
which immutable inputs are symlinked and the one stale V2 gate label is renamed,
so the already-frozen independent verifier can finish comparing its scientific
reconstruction against the primary result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


OLD_GATE = "quality_pairs_at_least_3"
NEW_GATE = "quality_pairs_at_least_4"
LINKS = (
    "generation_manifest.json",
    "replay_manifest.audit.json",
    "replay_manifest.jsonl",
    "replay",
    "status",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def build(source_root: Path, diagnostic_root: Path) -> dict:
    if diagnostic_root.exists():
        raise RuntimeError(f"refusing existing diagnostic root: {diagnostic_root}")
    primary_path = source_root / "probe_contract_ab_result.json"
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    if primary.get("version") != "v2" or primary.get("schema_version") != 2:
        raise RuntimeError("expected Probe Contract A/B V2 primary result")
    gates = primary.get("gates")
    if not isinstance(gates, dict) or OLD_GATE not in gates or NEW_GATE in gates:
        raise RuntimeError("source does not have the exact stale V2 gate schema")
    expected = int(primary["summary"]["paired_full_scores"]) >= 4
    if gates[OLD_GATE] is not expected:
        raise RuntimeError("stale gate value does not equal the frozen V2 threshold")

    diagnostic_root.mkdir(parents=True)
    for name in LINKS:
        source = (source_root / name).resolve()
        if not source.exists():
            raise RuntimeError(f"missing immutable source: {source}")
        destination = diagnostic_root / name
        try:
            destination.symlink_to(source, target_is_directory=source.is_dir())
        except OSError:
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)

    corrected = json.loads(json.dumps(primary))
    corrected["gates"][NEW_GATE] = corrected["gates"].pop(OLD_GATE)
    corrected["postoutcome_diagnostic"] = {
        "formal_experiment_status": "INVALID_INDEPENDENT_VERIFIER",
        "scientific_scalars_changed": False,
        "schema_only_rename": f"gates.{OLD_GATE} -> gates.{NEW_GATE}",
        "source_primary_sha256": sha256_file(primary_path),
    }
    corrected_path = diagnostic_root / "probe_contract_ab_result.json"
    atomic_json(corrected_path, corrected)
    receipt = {
        "diagnostic_root": str(diagnostic_root.resolve()),
        "formal_experiment_status": "INVALID_INDEPENDENT_VERIFIER",
        "scientific_scalars_changed": False,
        "source_primary_sha256": sha256_file(primary_path),
        "corrected_primary_sha256": sha256_file(corrected_path),
    }
    atomic_json(diagnostic_root / "schema_diagnostic_receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_root, args.diagnostic_root), sort_keys=True))


if __name__ == "__main__":
    main()
