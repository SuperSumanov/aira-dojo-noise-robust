from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import phase1.senior_experiment_config_v2 as exporter
import phase1.validate_senior_experiment_config_manifest as v1
import phase1.validate_senior_experiment_config_manifest_v2 as validator


RUN_ID = "family_seed_7_id_abcd1234__2026-08-25"


def dojo_config(
    *,
    prompt: str = "static policy v1",
    exp_name: str = "run-specific-name-a",
    checkpoint_path: str = "/tmp/run-a/checkpoint",
    draft_client: str = "qwen3-coder-flash",
    debug_client: str | None = None,
) -> dict[str, object]:
    if debug_client is None:
        debug_client = draft_client
    return {
        "id": "family_seed_7_id_abcd1234",
        "metadata": {"launch_time": "2026-08-25T01:02:03Z"},
        "solver": {
            "step_limit": 20,
            "available_packages": ["numpy", "pandas"],
            "exp_name": exp_name,
            "checkpoint_path": checkpoint_path,
            "time_limit_secs": 1200,
            "execution_timeout": 600,
            "operators": {
                "draft": {
                    "system_prompt": prompt,
                    "prompt": "dynamic context: {task}",
                    "llm": {"client": {"model_id": draft_client}},
                },
                "debug": {
                    "system_prompt": prompt,
                    "prompt": "dynamic debug: {task}",
                    "llm": {"client": {"model_id": debug_client}},
                },
            },
        },
    }


def write_json(path: Path, value: object) -> str:
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    raw = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def row(config: dict[str, object] | None = None, **overrides):
    value = exporter.make_row(
        config or dojo_config(),
        task="task-a",
        generator_release="qwen-release-2026-08",
        hardware="NVIDIA H200",
    )
    value.update(overrides)
    if overrides:
        value["experiment_stratum_sha256"] = exporter.experiment_stratum_sha256(value)
    return value


def expected_row() -> dict[str, object]:
    return {
        "cards": 3,
        "config_sha256": "a" * 64,
        "curve_order_sha256": "b" * 64,
        "dev_order_sha256": "c" * 64,
        "original_hold": False,
        "role": "train",
        "run_id": RUN_ID,
        "task": "task-a",
    }


def source_row() -> dict[str, object]:
    return {
        "archive_path": "0825/task-a.tar.gz",
        "archive_sha256": "d" * 64,
        "batch_id": "batch-0825-a",
        "producer_commit": "e" * 40,
        "run_id": RUN_ID,
        "source_date": "2026-08-25",
        "task": "task-a",
    }


def full_fixture(tmp_path: Path, config_row: dict[str, object] | None = None):
    expected = tmp_path / "expected.jsonl"
    expected_sha = write_jsonl(expected, [expected_row()])
    source = tmp_path / "source.jsonl"
    source_value = source_row()
    source_sha = write_jsonl(source, [source_value])
    source_mapping = v1.rows_sha256(
        [{field: source_value[field] for field in sorted(v1.SOURCE_FIELDS)}]
    )
    source_receipt = tmp_path / "source-receipt.json"
    source_receipt_sha = write_json(
        source_receipt,
        {
            "protocol": v1.SOURCE_PROTOCOL,
            "formal_status": "PROVENANCE_VERIFIED",
            "inputs": {
                "expected_runs_sha256": expected_sha,
                "provenance_manifest_sha256": source_sha,
            },
            "mapping_sha256": source_mapping,
            "access_attestation": {
                "tar_member_payloads_opened": False,
                "outcomes_or_grades_read": False,
                "model_fit_or_gpu_used": False,
            },
        },
    )
    config = tmp_path / "config-v2.jsonl"
    config_sha = write_jsonl(config, [config_row or row()])
    return (
        expected,
        expected_sha,
        source,
        source_sha,
        source_receipt,
        source_receipt_sha,
        config,
        config_sha,
    )


def run_validate(args):
    return validator.validate(*args)


def test_solver_hash_detects_prompt_change_but_ignores_run_paths() -> None:
    base = exporter.resolved_solver_config_sha256(dojo_config())
    path_changed = exporter.resolved_solver_config_sha256(
        dojo_config(exp_name="run-b", checkpoint_path="/another/run/checkpoint")
    )
    prompt_changed = exporter.resolved_solver_config_sha256(
        dojo_config(prompt="static policy v2")
    )
    assert base == path_changed
    assert base != prompt_changed


def test_exported_row_binds_release_and_solver_hash() -> None:
    first = row()
    second = row(generator_release="qwen-release-2026-09")
    third = row(resolved_solver_config_sha256="f" * 64)
    assert first["run_id"] == RUN_ID
    assert first["solver_projection_schema"] == exporter.SOLVER_PROJECTION_SCHEMA
    assert len({first["experiment_stratum_sha256"], second["experiment_stratum_sha256"], third["experiment_stratum_sha256"]}) == 3


def test_mixed_operator_clients_fail_closed() -> None:
    with pytest.raises(exporter.ExportError, match="clients are mixed"):
        exporter.make_row(
            dojo_config(debug_client="deepseek-v4-flash"),
            task="task-a",
            generator_release="release-a",
            hardware="NVIDIA H200",
        )


def test_raw_config_credential_is_refused_before_parse(tmp_path: Path) -> None:
    config = dojo_config()
    config["solver"]["credential"] = "".join(("sk", "-", "abcdefghijklmnop"))
    path = tmp_path / "dojo_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(exporter.ExportError, match="before dojo config parse"):
        exporter.load_dojo_config(path)


def test_full_v2_composition_is_deterministic_and_prompt_sensitive(tmp_path: Path) -> None:
    args = full_fixture(tmp_path)
    first = run_validate(args)
    second = run_validate(args)
    assert first == second
    assert first["formal_status"] == "PROMPT_SENSITIVE_CONFIG_PROVENANCE_VERIFIED"
    assert first["inventory"]["config_rows"] == 1
    assert first["inventory"]["resolved_solver_configs"] == 1
    assert first["inventory"]["producer_strata"] == 1
    assert first["interaction_metadata_complete"] is True
    assert first["access_attestation"]["dojo_configs_opened_by_this_validator"] is False


def test_tampered_solver_or_stratum_hash_fails_closed(tmp_path: Path) -> None:
    value = row()
    value["resolved_solver_config_sha256"] = "f" * 64
    args = full_fixture(tmp_path, value)
    with pytest.raises(v1.ContractError, match="stratum receipt mismatch"):
        run_validate(args)

    value = row()
    value["experiment_stratum_sha256"] = "f" * 64
    config_sha = write_jsonl(args[6], [value])
    args = (*args[:7], config_sha)
    with pytest.raises(v1.ContractError, match="stratum receipt mismatch"):
        run_validate(args)


def test_unknown_release_preserves_provenance_but_blocks_interaction(tmp_path: Path) -> None:
    args = full_fixture(tmp_path, row(generator_release="unknown"))
    result = run_validate(args)
    assert result["formal_status"] == "PROMPT_SENSITIVE_CONFIG_PROVENANCE_VERIFIED"
    assert result["inventory"]["unknown_generator_release_rows"] == 1
    assert result["interaction_metadata_complete"] is False


def test_export_output_is_immutable(tmp_path: Path) -> None:
    output = tmp_path / "config-v2.jsonl"
    exporter.write_row(output, row())
    assert json.loads(output.read_text())["run_id"] == RUN_ID
    with pytest.raises(exporter.ExportError, match="already exists"):
        exporter.write_row(output, row())


def test_repository_example_is_static_schema_valid_and_credential_safe() -> None:
    path = (
        Path(__file__).parents[1]
        / "examples"
        / "senior_experiment_config_manifest_v2.example.jsonl"
    )
    raw = path.read_bytes()
    assert v1.CREDENTIAL.search(raw) is None
    rows = v1.load_jsonl(path, exporter.CONFIG_FIELDS)
    expected = v1.validate_expected_runs(
        [{"run_id": value["run_id"], "task": value["task"]} for value in rows]
    )
    validated = validator.validate_config_rows(rows, expected)
    assert set(validated) == {"family_seed_7_id_abcd1234__2026-08-25"}
