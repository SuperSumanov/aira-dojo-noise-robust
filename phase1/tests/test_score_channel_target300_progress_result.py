from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "score_channel_target300_progress_ad0b_20260827_ab59a01"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _manifest(name: str, *, remote: bool) -> dict[str, str]:
    rows: dict[str, str] = {}
    prefix = r"\./" if remote else ""
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(rf"([0-9a-f]{{64}})  {prefix}(.+)", line)
        assert match is not None
        rows[match.group(2)] = match.group(1)
    return rows


def test_target300_progress_is_collecting_and_truth_unread() -> None:
    summary = _json("summary.json")
    verifier = _json("independent_verification.json")

    assert summary["status"] == "FUTURE_COHORT_COLLECTING"
    assert summary["source_commit"] == "ab59a011d945e4a96daf7dbbbc927a59027da077"
    assert summary["inputs"]["latest_sha256"] == (
        "ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e"
    )
    assert summary["inventory"]["selected_physical_runs"] == verifier["selected_physical_runs"] == 129
    assert summary["inventory"]["selected_archives"] == verifier["selected_archives"] == 41
    assert summary["inventory"]["selected_tasks"] == verifier["selected_tasks"] == 21
    assert summary["closure"]["remaining_runs_to_target"] == 171
    assert summary["closure"]["accepted_unique_physical_run_target"] == 300
    assert summary["closure"]["complete_boundary_archive_included"] is False
    assert summary["closure"]["boundary_archive"] is None
    assert summary["closure"]["append_only_previous"]["exact_prefix_survived"] is True
    assert summary["closure"]["append_only_previous"]["previous_runs"] == 64
    assert summary["closure"]["append_only_previous"]["previous_archives"] == 21
    assert summary["blindness"]["truth_support_computed"] is False
    assert summary["blindness"]["score_or_outcome_opened"] is False
    assert summary["blindness"]["replay_submission_authorized"] is False

    assert verifier["status"] == "PASS_COLLECTING_TRUTH_UNREAD"
    assert verifier["implementation_independent_of_producer"] is True
    assert verifier["producer_module_imported"] is False
    assert verifier["append_only_previous_reconstructed"] is True
    assert verifier["complete_boundary_archive_reconstructed"] is True
    assert verifier["truth_support_computed"] is False
    assert verifier["score_or_outcome_opened"] is False


def test_downloaded_artifacts_match_remote_manifest() -> None:
    rows = _manifest("remote_SHA256SUMS", remote=True)
    mapping = {
        "producer_a/summary.json": "summary.json",
        "verification_a.json": "independent_verification.json",
        "preflight_matrix.txt": "preflight_matrix.txt",
        "focused_tests.stdout": "focused_tests.txt",
        "phase1_tests.stdout": "full_tests.txt",
        "latest_before.txt": "latest_before.txt",
        "latest_after.txt": "latest_after.txt",
        "observations_before_sha256.txt": "observations_before_sha256.txt",
        "observations_after_sha256.txt": "observations_after_sha256.txt",
        "content_scan_count.txt": "content_scan_count.txt",
        "filename_scan_count.txt": "filename_scan_count.txt",
        "forbidden_open_count.txt": "forbidden_open_count.txt",
        "production_state_advanced_after_verification.txt": (
            "production_state_advanced_after_verification.txt"
        ),
        "completed_at_utc.txt": "completed_at_utc.txt",
    }
    for remote_name, local_name in mapping.items():
        assert _sha(ROOT / local_name) == rows[remote_name]
    assert _sha(ROOT / "summary.json") == (
        "4b3a17aeb6ee0212ec7811d7992930f8467d0ec1aa8b624c5978b2a865834fb6"
    )
    assert _sha(ROOT / "independent_verification.json") == (
        "5269d14887b37a34ab19cf8dc2b1dc4e664e9e08babce97d308dae2c5d42b3b7"
    )


def test_public_package_manifest_is_complete() -> None:
    expected = _manifest("SHA256SUMS", remote=False)
    actual = {
        path.name: _sha(path)
        for path in ROOT.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == actual
