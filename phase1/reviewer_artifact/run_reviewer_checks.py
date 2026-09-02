#!/usr/bin/env python3
"""Self-check the anonymous aggregate-only reviewer package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SHA256_RE = re.compile(r"^([0-9a-f]{64})  \./(.+)$")


class ReviewerCheckError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReviewerCheckError(f"expected a JSON object: {path.name}")
    return value


def verify_package_manifest(root: Path) -> tuple[int, int]:
    manifest_path = root / "MANIFEST.sha256"
    package_path = root / "PACKAGE_MANIFEST.json"
    if not manifest_path.is_file() or not package_path.is_file():
        raise ReviewerCheckError("package manifests are missing")
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="ascii").splitlines():
        match = SHA256_RE.fullmatch(line)
        if match is None or match.group(2) in entries:
            raise ReviewerCheckError("invalid or duplicate SHA-256 manifest entry")
        relative = match.group(2)
        if relative.startswith("/") or ".." in Path(relative).parts or "\\" in relative:
            raise ReviewerCheckError("unsafe manifest path")
        entries[relative] = match.group(1)
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256"
    }
    if set(entries) != observed:
        raise ReviewerCheckError("manifest file set mismatch")
    total_bytes = 0
    for relative, expected in entries.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256(path) != expected:
            raise ReviewerCheckError(f"manifest hash mismatch: {relative}")
        total_bytes += path.stat().st_size
    package = load_json(package_path)
    if package.get("status") != "ANONYMOUS_AGGREGATE_PREVIEW_NOT_DATASET_RELEASE":
        raise ReviewerCheckError("unexpected package status")
    if package.get("public_source_commit_included") is not False:
        raise ReviewerCheckError("source identity must be absent from package")
    return len(entries), total_bytes


def render_figures(root: Path, temporary: Path) -> dict[str, bool]:
    figure_dir = root / "phase1/figures/decision_corpus_20260902"
    receipt1 = load_json(figure_dir / "figure1_receipt.json")
    receipt2 = load_json(figure_dir / "figure2_receipt.json")
    output1 = temporary / "figure1"
    output2 = temporary / "figure2"
    command1 = [
        sys.executable,
        str(root / "phase1/plot_paper_figure1_protocol.py"),
        "--output-dir",
        str(output1),
    ]
    command2 = [
        sys.executable,
        str(root / "phase1/plot_paper_figure2_weighting.py"),
        "--input",
        str(
            root
            / "phase1/results/structural_weight_trajectory_7cda_20260826/trajectory.json"
        ),
        "--output-dir",
        str(output2),
    ]
    for command in (command1, command2):
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise ReviewerCheckError(
                f"figure command failed with rc={completed.returncode}"
            )
    checks = {
        "figure1_png": sha256(output1 / "figure1_corpus_and_sealed_protocol.png")
        == receipt1["outputs"]["figure1_corpus_and_sealed_protocol.png"],
        "figure1_svg": sha256(output1 / "figure1_corpus_and_sealed_protocol.svg")
        == receipt1["outputs"]["figure1_corpus_and_sealed_protocol.svg"],
        "figure2_png": sha256(output2 / "figure2_run_to_pair_weighting.png")
        == receipt2["outputs"]["figure2_run_to_pair_weighting.png"],
        "figure2_svg": sha256(output2 / "figure2_run_to_pair_weighting.svg")
        == receipt2["outputs"]["figure2_run_to_pair_weighting.svg"],
    }
    if not all(checks.values()):
        raise ReviewerCheckError("one or more regenerated figure hashes differ")
    return checks


def verify_aggregate_claim_inputs(root: Path) -> dict[str, bool]:
    table = load_json(
        root / "phase1/results/historical_table4a_extract_20260902/table4a.json"
    )
    release = load_json(root / "phase1/corpus_releases/v11.json")
    population = table.get("population", {})
    scope = table.get("scope", {})
    checks = {
        "table_status": table.get("status")
        == "HISTORICAL_DEVELOPMENT_TABLE_AUTHORIZED_WITH_SCOPE_BOUNDARY",
        "table_support": population.get("pairs") == 931
        and population.get("tasks") == 28
        and population.get("decision_parents") == 550,
        "table_panel": len(table.get("accuracy_panel", [])) == 6
        and all(row.get("pairs") == 931 for row in table.get("accuracy_panel", [])),
        "cost_panel": table.get("cost_panel", {}).get("accuracy_computed") is False
        and len(table.get("cost_panel", {}).get("rows", [])) == 3,
        "scope": scope.get("historical_development_only") is True
        and scope.get("prospective_confirmation") is False
        and scope.get("search_utility") is False,
        "v11_descriptor": release.get("version") == "v11"
        and release.get("batch_count") == 29
        and release.get("output", {}).get("rows") == 16012
        and release.get("output", {}).get("bytes") == 305750663,
    }
    if not all(checks.values()):
        raise ReviewerCheckError("aggregate claim-input invariant failed")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    files, total_bytes = verify_package_manifest(root)
    with tempfile.TemporaryDirectory(prefix="decision-corpus-review-") as directory:
        figure_checks = render_figures(root, Path(directory))
    aggregate_checks = verify_aggregate_claim_inputs(root)
    result = {
        "protocol": "decision-corpus-anonymous-reviewer-self-check-v0",
        "status": "PASS",
        "manifest_files": files,
        "manifest_bytes": total_bytes,
        "figure_checks": figure_checks,
        "aggregate_checks": aggregate_checks,
        "scientific_recompute_from_row_level_inputs": False,
        "prospective_values_or_identities_read": False,
        "network_gpu_paid_api_model_fit_base_update": [0, 0, 0, 0, 0],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
