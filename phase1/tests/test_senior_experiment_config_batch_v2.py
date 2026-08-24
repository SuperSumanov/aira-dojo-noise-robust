import copy
import json
import sys
from pathlib import Path

import pytest

import phase1.senior_experiment_config_batch_v2 as batch
import phase1.senior_experiment_config_v2 as single
import phase1.validate_senior_experiment_config_manifest as v1


def dojo_config(run_name: str, *, model: str = "qwen3-coder-flash") -> dict:
    return {
        "id": run_name,
        "metadata": {"launch_time": "2026-08-25T01:02:03Z"},
        "solver": {
            "exp_name": f"outputs/{run_name}",
            "checkpoint_path": f"checkpoints/{run_name}",
            "time_limit_secs": 1200,
            "execution_timeout": 600,
            "operators": {
                "draft": {
                    "llm": {"client": {"model_id": model}},
                    "system_message": "static policy",
                    "prompt": "dynamic context: {task}",
                },
                "improve": {
                    "llm": {"client": {"model_id": model}},
                    "system_message": "static improve policy",
                    "prompt": "dynamic improve: {task}",
                },
            },
            "search": {"max_depth": 20, "max_children": 8},
        },
    }


def write_config(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_rows(paths: list[Path]) -> list[dict]:
    return batch.make_rows(
        paths,
        task="task-a",
        generator_release="qwen-release-2026-08",
        hardware="NVIDIA H200",
    )


def test_argument_order_does_not_change_batch_bytes(tmp_path: Path):
    first = write_config(
        tmp_path / "run-a" / "dojo_config.json",
        dojo_config("family_seed_1_id_aaaa1111"),
    )
    second = write_config(
        tmp_path / "run-b" / "dojo_config.json",
        dojo_config("family_seed_2_id_bbbb2222"),
    )
    rows_ab = make_rows([first, second])
    rows_ba = make_rows([second, first])
    assert rows_ab == rows_ba
    assert [row["run_id"] for row in rows_ab] == sorted(
        row["run_id"] for row in rows_ab
    )
    assert batch.encoded_rows(rows_ab) == batch.encoded_rows(rows_ba)


def test_batch_output_is_canonical_and_hash_bound(tmp_path: Path):
    paths = [
        write_config(
            tmp_path / f"run-{index}" / "dojo_config.json",
            dojo_config(f"family_seed_{index}_id_abcd{index:04d}"),
        )
        for index in range(4)
    ]
    rows = make_rows(paths)
    output = tmp_path / "task-a.config_v2.jsonl"
    manifest_sha256 = batch.write_batch(output, rows)
    raw = output.read_bytes()
    assert manifest_sha256 == batch.hashlib.sha256(raw).hexdigest()
    parsed = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    assert parsed == rows
    assert all(set(row) == single.CONFIG_FIELDS for row in parsed)
    assert all(
        row["experiment_stratum_sha256"] == single.experiment_stratum_sha256(row)
        for row in parsed
    )
    assert v1.CREDENTIAL.search(raw) is None


def test_duplicate_run_id_fails_before_output(tmp_path: Path):
    first = write_config(
        tmp_path / "a" / "dojo_config.json",
        dojo_config("family_seed_7_id_abcd1234"),
    )
    second = write_config(
        tmp_path / "b" / "dojo_config.json",
        dojo_config("family_seed_7_id_abcd1234"),
    )
    output = tmp_path / "batch.jsonl"
    with pytest.raises(batch.BatchExportError, match="duplicate"):
        rows = make_rows([first, second])
        batch.write_batch(output, rows)
    assert not output.exists()


def test_one_credential_shaped_config_leaves_no_partial_output(tmp_path: Path):
    good = write_config(
        tmp_path / "good" / "dojo_config.json",
        dojo_config("family_seed_5_id_abcd1234"),
    )
    bad_payload = copy.deepcopy(dojo_config("family_seed_6_id_abcd5678"))
    bad_payload["solver"]["operators"]["draft"]["prompt"] = (
        "sk" + "-" + "abcdefghijklmnopqrstuv"
    )
    bad = write_config(tmp_path / "bad" / "dojo_config.json", bad_payload)
    output = tmp_path / "batch.jsonl"
    with pytest.raises(single.ExportError, match="credential-shaped"):
        rows = make_rows([good, bad])
        batch.write_batch(output, rows)
    assert not output.exists()


def test_mixed_operator_client_leaves_no_partial_output(tmp_path: Path):
    payload = dojo_config("family_seed_8_id_abcd1234")
    payload["solver"]["operators"]["improve"]["llm"]["client"]["model_id"] = "other-model"
    config = write_config(tmp_path / "mixed" / "dojo_config.json", payload)
    output = tmp_path / "batch.jsonl"
    with pytest.raises(single.ExportError, match="mixed"):
        rows = make_rows([config])
        batch.write_batch(output, rows)
    assert not output.exists()


def test_existing_output_and_non_jsonl_suffix_fail_closed(tmp_path: Path):
    config = write_config(
        tmp_path / "run" / "dojo_config.json",
        dojo_config("family_seed_9_id_abcd1234"),
    )
    rows = make_rows([config])
    existing = tmp_path / "existing.jsonl"
    existing.write_text("keep\n", encoding="utf-8")
    with pytest.raises(batch.BatchExportError, match="already exists"):
        batch.write_batch(existing, rows)
    assert existing.read_text(encoding="utf-8") == "keep\n"
    with pytest.raises(batch.BatchExportError, match=".jsonl"):
        batch.write_batch(tmp_path / "wrong.json", rows)


def test_empty_batch_fails_closed(tmp_path: Path):
    with pytest.raises(batch.BatchExportError, match="at least one"):
        make_rows([])
    with pytest.raises(batch.BatchExportError, match="empty"):
        batch.write_batch(tmp_path / "empty.jsonl", [])


def test_cli_exports_complete_batch(tmp_path: Path, monkeypatch, capsys):
    first = write_config(
        tmp_path / "one" / "dojo_config.json",
        dojo_config("family_seed_10_id_abcd1234"),
    )
    second = write_config(
        tmp_path / "two" / "dojo_config.json",
        dojo_config("family_seed_11_id_abcd5678"),
    )
    output = tmp_path / "task-a.config_v2.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "senior_experiment_config_batch_v2.py",
            "--dojo-config",
            str(second),
            "--dojo-config",
            str(first),
            "--task",
            "task-a",
            "--generator-release",
            "qwen-release-2026-08",
            "--hardware",
            "NVIDIA H200",
            "--output",
            str(output),
        ],
    )
    assert batch.main() == 0
    stdout = capsys.readouterr().out
    assert "SENIOR_CONFIG_V2_BATCH_EXPORT_PASS rows=2 manifest_sha256=" in stdout
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == [
        "family_seed_10_id_abcd1234__2026-08-25",
        "family_seed_11_id_abcd5678__2026-08-25",
    ]
