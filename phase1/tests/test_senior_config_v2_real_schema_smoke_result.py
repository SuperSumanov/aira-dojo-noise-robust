from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "senior_config_v2_real_schema_smoke_20260827_fd8982c"
)


def receipt() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / "receipt.txt").read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        result[key] = value
    return result


def test_real_config_summary_records_only_schema_compatibility() -> None:
    value = json.loads((ROOT / "summary.json").read_text(encoding="utf-8"))
    assert value["status"] == "REAL_CONFIG_SCHEMA_COMPAT_PASS"
    assert value["configs"] == 20
    assert value["candidate_reference_bytes_equal"] == 20
    assert value["distinct_tasks"] == 7
    assert value["distinct_clients"] == 2
    assert value["distinct_solver_fingerprints"] == 2
    assert value["distinct_experiment_strata"] == 9
    assert value["distinct_top_level_schemas"] == 1
    assert value["rows_sha256"] == (
        "fd8982cf75099f71b73d1d5b2ad3e955a89d81efbae941e94705981216ed9e5e"
    )
    assert value["sidecars_before"] == value["sidecars_after"] == 0
    assert value["sidecars_written"] == 0
    assert value["historical_only_not_provenance"] is True


def test_real_config_receipt_preserves_access_boundaries() -> None:
    fields = receipt()
    assert fields["status"] == "REAL_CONFIG_SCHEMA_COMPAT_PASS"
    assert fields["selection_rule"] == "latest_20_regular_dojo_configs_by_mtime"
    assert fields["selection_sha256"] == (
        "6b2f6d904a0ae9278ea920e549fe56d3493fa857f210806c115ad86e66187b7e"
    )
    assert fields["forbidden_path_open_hits"] == "0"
    assert fields["credential_output_hits"] == "0"
    assert fields["gpu_jobs_submitted"] == "0"
    assert fields["env_or_archive_or_outcome_read"] == "false"
    assert fields["historical_only_not_provenance"] == "true"


def test_remote_manifest_hash_is_bound() -> None:
    line = (ROOT / "remote_SHA256SUMS.sha256").read_text(encoding="utf-8").strip()
    digest, path = line.split(maxsplit=1)
    assert digest == "80c8ab4b9ef5c23693aad00c7db75e81d81fd18f7339f65d6dff67e86003c47e"
    assert path.endswith("/real_config_smoke_65896b6_v1/SHA256SUMS")


def test_local_package_manifest_covers_exact_file_set() -> None:
    manifest = ROOT / "SHA256SUMS"
    expected_digest = "8643076ee3ecf1cfad0d6376604e83c8536679a0cb02123876ce5deff1f9d2e6"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == expected_digest
    recorded: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        assert name not in recorded
        recorded[name] = digest
    expected = {path.name for path in ROOT.iterdir() if path.is_file() and path.name != "SHA256SUMS"}
    assert set(recorded) == expected
    for name, digest in recorded.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
