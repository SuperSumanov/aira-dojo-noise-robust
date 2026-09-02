from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1/anonymous_reviewer_artifact_v0.json"
BUILDER = ROOT / "phase1/build_anonymous_reviewer_artifact_v0.py"
VERIFIER = ROOT / "phase1/verify_anonymous_reviewer_artifact_v0.py"
REPORT = ROOT / "phase1/ANONYMOUS_REVIEWER_ARTIFACT_V0_20260902.md"
RECEIPT = ROOT / "phase1/anonymous_reviewer_artifact_v0_build_receipt_20260902.json"
DIRECTION = ROOT / "phase1/CURRENT_DIRECTION.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_source_hash(path: Path, source: str, policy: dict) -> str:
    payload = path.read_bytes()
    if Path(source).suffix.lower() not in policy["binary_exact_suffixes"]:
        text = payload.decode("utf-8")
        payload = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def run_builder(package_root: Path, zip_path: Path) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--package-root",
            str(package_root),
            "--zip",
            str(zip_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return json.loads(completed.stdout)


def run_verifier(package_root: Path, zip_path: Path, *, check: bool = True):
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--package-root",
            str(package_root),
            "--zip",
            str(zip_path),
        ],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=180,
    )


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_contract_is_anonymous_aggregate_only_and_has_explicit_claim_boundaries():
    contract = load_contract()
    assert contract["status"] == "ANONYMOUS_AGGREGATE_PREVIEW_NOT_DATASET_RELEASE"
    assert contract["security"] == {
        "anonymous": True,
        "aggregate_only": True,
        "public_source_commit_included": False,
        "git_history_included": False,
        "prospective_content_included": False,
        "network_required": False,
        "gpu_required": False,
        "paid_api_required": False,
        "model_fit_required": False,
        "base_model_update_required": False,
    }
    assert contract["source_byte_policy"] == {
        "default": "canonical_lf_utf8_text",
        "binary_exact_suffixes": [".png"],
    }
    claims = {row["claim"]: row for row in contract["capability_matrix"]}
    assert claims["protocol_figure"]["artifact_operation"] == "PAPER_EXACT_REGEN"
    assert "FROZEN_AGGREGATE" in claims["run_to_pair_weighting_figure"]["artifact_operation"]
    assert claims["historical_table4a_and_cost_panel"]["scientific_recompute"].startswith(
        "BLOCKED_931_ROW_LEVEL"
    )
    assert claims["historical_v11_corpus"]["scientific_recompute"].startswith(
        "BLOCKED_16012_CARD"
    )
    assert claims["sealed_prospective_confirmation"]["artifact_operation"] == "EXCLUDED_AND_SEALED"


def test_allowlist_has_24_hash_bound_files_and_no_sensitive_or_ambiguous_paths():
    contract = load_contract()
    resources = contract["resources"]
    assert len(resources) == 24
    assert len({row["source"] for row in resources}) == 24
    assert len({row["destination"] for row in resources}) == 24
    forbidden = re.compile(
        rb"(?i)(?:/(?:research|uac)/|C:\\Users\\|\blinux[0-9]+\b|"
        rb"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])|"
        rb"sk-(?:or-v1-)?[A-Za-z0-9._-]{20,}|"
        rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    )
    for row in resources:
        assert ".git" not in Path(row["destination"]).parts
        assert "CURRENT_DIRECTION" not in row["destination"]
        source = ROOT / row["source"]
        assert source.is_file() and not source.is_symlink()
        assert canonical_source_hash(
            source, row["source"], contract["source_byte_policy"]
        ) == row["sha256"]
        assert forbidden.search(source.read_bytes()) is None


def test_builder_and_independent_verifier_are_separate_implementations():
    builder_source = BUILDER.read_text(encoding="utf-8")
    verifier_source = VERIFIER.read_text(encoding="utf-8")
    assert "verify_anonymous_reviewer_artifact_v0" not in builder_source
    assert "build_anonymous_reviewer_artifact_v0" not in verifier_source
    assert "from phase1" not in verifier_source


def test_two_builds_are_byte_identical_and_packaged_self_check_passes(tmp_path: Path):
    package_a = tmp_path / "package-a"
    package_b = tmp_path / "package-b"
    zip_a = tmp_path / "artifact-a.zip"
    zip_b = tmp_path / "artifact-b.zip"
    build_a = run_builder(package_a, zip_a)
    build_b = run_builder(package_b, zip_b)
    assert build_a["status"] == build_b["status"] == "PASS"
    assert build_a["resource_files"] == build_b["resource_files"] == 24
    assert build_a["package_files"] == build_b["package_files"] == 26
    assert build_a["zip_sha256"] == build_b["zip_sha256"] == sha256(zip_a) == sha256(zip_b)
    assert zip_a.read_bytes() == zip_b.read_bytes()
    assert tree_hashes(package_a) == tree_hashes(package_b)

    verified_a = json.loads(run_verifier(package_a, zip_a).stdout)
    verified_b = json.loads(run_verifier(package_b, zip_b).stdout)
    assert verified_a["status"] == verified_b["status"] == "PASS"
    assert verified_a["package_files"] == verified_b["package_files"] == 26
    assert verified_a["credential_identity_hits"] == 0
    assert verified_a["prospective_values_or_identities_read"] is False

    self_check = subprocess.run(
        [sys.executable, str(package_a / "tools/run_reviewer_checks.py")],
        cwd=package_a,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    self_result = json.loads(self_check.stdout)
    assert self_result["status"] == "PASS"
    assert self_result["manifest_files"] == 25
    assert all(self_result["figure_checks"].values())
    assert all(self_result["aggregate_checks"].values())
    assert self_result["scientific_recompute_from_row_level_inputs"] is False


def test_independent_verifier_fails_closed_after_payload_tampering(tmp_path: Path):
    package_root = tmp_path / "package"
    zip_path = tmp_path / "artifact.zip"
    run_builder(package_root, zip_path)
    readme = package_root / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\ntampered\n")
    completed = run_verifier(package_root, zip_path, check=False)
    assert completed.returncode != 0
    assert "mismatch" in completed.stderr.lower()


def test_builder_fails_closed_on_contract_hash_drift(tmp_path: Path):
    contract = load_contract()
    contract["resources"][0]["sha256"] = "0" * 64
    bad_contract = tmp_path / "bad-contract.json"
    bad_contract.write_text(json.dumps(contract), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--contract",
            str(bad_contract),
            "--package-root",
            str(tmp_path / "package"),
            "--zip",
            str(tmp_path / "artifact.zip"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode != 0
    assert "hash drift" in completed.stderr.lower()
    assert not (tmp_path / "package").exists()
    assert not (tmp_path / "artifact.zip").exists()


def test_report_receipt_and_direction_preserve_preview_not_release_boundary():
    report = REPORT.read_text(encoding="utf-8")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    direction = DIRECTION.read_text(encoding="utf-8")
    expected_zip = "91a74b50a3d1aacdbcb875236c007ec9db62a8126c45b89e927ce192b3112bce"
    assert "not a dataset release" in report
    assert "cannot be scientifically recomputed" in report
    assert receipt["build_a_b"]["zip_sha256"] == expected_zip
    assert receipt["build_a_b"]["zip_byte_identical"] is True
    assert receipt["packaged_self_check"]["scientific_recompute_from_row_level_inputs"] is False
    assert receipt["security"]["prospective_values_or_identities_read"] is False
    assert receipt["implementation"]["focused_test_sha256"] == sha256(Path(__file__))
    assert "## 0L0q." in direction
    assert expected_zip in direction
    assert "counts_as_distinct_claim_evidence=false" in direction
