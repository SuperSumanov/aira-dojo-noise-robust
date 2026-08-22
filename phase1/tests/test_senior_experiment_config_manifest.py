from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import phase1.validate_senior_experiment_config_manifest as contract


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: dict[str, object]) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def expected_row(run_id: str, task: str = "task-a") -> dict[str, object]:
    return {
        "cards": 3,
        "config_sha256": "a" * 64,
        "curve_order_sha256": "b" * 64,
        "dev_order_sha256": "c" * 64,
        "original_hold": False,
        "role": "train",
        "run_id": run_id,
        "task": task,
    }


def source_row(run_id: str, task: str = "task-a") -> dict[str, object]:
    return {
        "archive_path": "0808/task-a.tar.gz",
        "archive_sha256": "d" * 64,
        "batch_id": "batch-a",
        "producer_commit": "e" * 40,
        "run_id": run_id,
        "source_date": "2026-08-08",
        "task": task,
    }


def config_row(
    run_id: str,
    task: str = "task-a",
    *,
    client: str = "deepseek-v4-flash",
    release: str = "ds-flash-v2",
    hardware: str = "RTX 3090",
    time_limit: int | float = 1200,
    execution_timeout: int | float = 600,
) -> dict[str, object]:
    row: dict[str, object] = {
        "client": client,
        "execution_timeout": execution_timeout,
        "experiment_stratum_sha256": "0" * 64,
        "generator_release": release,
        "hardware": hardware,
        "run_id": run_id,
        "task": task,
        "time_limit": time_limit,
    }
    row["experiment_stratum_sha256"] = contract.experiment_stratum_sha256(row)
    return row


def valid_fixture(
    tmp_path: Path,
    *,
    two_runs: bool = False,
) -> tuple[Path, str, Path, str, Path, str, Path, str, list[str]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    run_ids = ["family_seed_7_id_abcd1234__2026-08-08"]
    if two_runs:
        run_ids.insert(0, "aaa_seed_1_id_ef012345__2026-08-08")

    expected = tmp_path / "runs.jsonl"
    expected_sha = write_jsonl(expected, [expected_row(run_id) for run_id in run_ids])
    source = tmp_path / "source.jsonl"
    source_rows = [source_row(run_id) for run_id in run_ids]
    source_sha = write_jsonl(source, source_rows)
    canonical_source = [
        {field: row[field] for field in sorted(contract.SOURCE_FIELDS)}
        for row in source_rows
    ]
    source_receipt = tmp_path / "source_receipt.json"
    source_receipt_sha = write_json(
        source_receipt,
        {
            "protocol": contract.SOURCE_PROTOCOL,
            "formal_status": "PROVENANCE_VERIFIED",
            "inputs": {
                "expected_runs_sha256": expected_sha,
                "provenance_manifest_sha256": source_sha,
            },
            "mapping_sha256": contract.rows_sha256(canonical_source),
            "access_attestation": {
                "tar_member_payloads_opened": False,
                "outcomes_or_grades_read": False,
                "model_fit_or_gpu_used": False,
            },
        },
    )
    config = tmp_path / "config.jsonl"
    config_sha = write_jsonl(config, [config_row(run_id) for run_id in run_ids])
    return (
        expected,
        expected_sha,
        source,
        source_sha,
        source_receipt,
        source_receipt_sha,
        config,
        config_sha,
        run_ids,
    )


def run_validate(fixture: tuple[Path, str, Path, str, Path, str, Path, str, list[str]]):
    expected, expected_sha, source, source_sha, receipt, receipt_sha, config, config_sha, _ = fixture
    return contract.validate(
        expected,
        expected_sha,
        source,
        source_sha,
        receipt,
        receipt_sha,
        config,
        config_sha,
    )


def test_valid_overlay_is_deterministic_and_links_source_receipt(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path, two_runs=True)
    first = run_validate(fixture)
    second = run_validate(fixture)
    assert first == second
    assert first["formal_status"] == "CONFIG_PROVENANCE_VERIFIED"
    assert first["inventory"]["config_rows"] == 2
    assert first["inventory"]["experiment_strata"] == 1
    assert first["criteria"]["source_provenance_receipt_linked"] is True
    assert first["interaction_metadata_complete"] is True
    assert first["access_attestation"]["cards_or_pair_payloads_opened"] is False


def test_unknown_release_is_verified_but_not_interaction_complete(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    config_sha = write_jsonl(config, [config_row(run_id, release="unknown")])
    fixture = (*fixture[:7], config_sha, fixture[8])
    result = run_validate(fixture)
    assert result["formal_status"] == "CONFIG_PROVENANCE_VERIFIED"
    assert result["inventory"]["unknown_generator_release_rows"] == 1
    assert result["interaction_metadata_complete"] is False

    config_sha = write_jsonl(config, [config_row(run_id, client="unknown")])
    fixture = (*fixture[:7], config_sha, fixture[8])
    result = run_validate(fixture)
    assert result["inventory"]["unknown_client_rows"] == 1
    assert result["interaction_metadata_complete"] is False


def test_rejects_tampered_experiment_stratum_hash(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    row = config_row(run_id)
    row["experiment_stratum_sha256"] = "f" * 64
    config_sha = write_jsonl(config, [row])
    fixture = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="stratum receipt mismatch"):
        run_validate(fixture)


def test_rejects_incomplete_config_coverage(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path, two_runs=True)
    config, run_id = fixture[6], fixture[8][0]
    config_sha = write_jsonl(config, [config_row(run_id)])
    fixture = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="does not exactly cover"):
        run_validate(fixture)


def test_rejects_task_mismatch(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    config_sha = write_jsonl(config, [config_row(run_id, task="task-b")])
    fixture = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="task does not match"):
        run_validate(fixture)


def test_rejects_tampered_source_receipt_mapping(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    receipt = fixture[4]
    value = json.loads(receipt.read_text())
    value["mapping_sha256"] = "f" * 64
    receipt_sha = write_json(receipt, value)
    fixture = (*fixture[:5], receipt_sha, *fixture[6:])
    with pytest.raises(contract.ContractError, match="mapping binding mismatch"):
        run_validate(fixture)


def test_rejects_credential_shaped_config_before_json_use(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    credential_shape = "".join(("sk", "-", "abcdefghijklmnop"))
    config_sha = write_jsonl(config, [config_row(run_id, client=credential_shape)])
    fixture = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="credential-shaped bytes refused"):
        run_validate(fixture)


def test_rejects_nonpublic_identifier_and_nonpositive_timeout(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    config_sha = write_jsonl(config, [config_row(run_id, client="model?key=value")])
    bad_identifier = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="public identifier"):
        run_validate(bad_identifier)

    config_sha = write_jsonl(config, [config_row(run_id, execution_timeout=0)])
    bad_timeout = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="positive finite"):
        run_validate(bad_timeout)


def test_rejects_extra_field_and_unsorted_rows(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config, run_id = fixture[6], fixture[8][0]
    row = config_row(run_id)
    row["grade"] = 1.0
    config_sha = write_jsonl(config, [row])
    extra_field = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="schema mismatch"):
        run_validate(extra_field)

    fixture = valid_fixture(tmp_path / "second", two_runs=True)
    config, run_ids = fixture[6], fixture[8]
    config_sha = write_jsonl(config, [config_row(run_ids[1]), config_row(run_ids[0])])
    unsorted = (*fixture[:7], config_sha, fixture[8])
    with pytest.raises(contract.ContractError, match="sorted by run_id"):
        run_validate(unsorted)


def test_output_receipt_is_immutable(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    result = run_validate(fixture)
    output = tmp_path / "receipt.json"
    contract.write_receipt(output, result)
    assert json.loads(output.read_text())["joined_mapping_sha256"] == result["joined_mapping_sha256"]
    with pytest.raises(contract.ContractError, match="already exists"):
        contract.write_receipt(output, result)


def test_input_and_output_symlinks_fail_closed(tmp_path: Path) -> None:
    fixture = valid_fixture(tmp_path)
    config_link = tmp_path / "config-link.jsonl"
    output_link = tmp_path / "receipt-link.json"
    try:
        config_link.symlink_to(fixture[6])
        output_link.symlink_to(tmp_path / "receipt-target.json")
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    linked_fixture = (*fixture[:6], config_link, *fixture[7:])
    with pytest.raises(contract.ContractError, match="symlinked"):
        run_validate(linked_fixture)
    with pytest.raises(contract.ContractError, match="must not be a symlink"):
        contract.write_receipt(output_link, run_validate(fixture))
