from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import score_channel_parent_selector as selector
from phase1 import score_channel_replay_manifest as materializer
from phase1 import verify_score_channel_parent_selection as verifier
from phase1 import verify_score_channel_replay_manifest as replay_verifier


REPO = Path(__file__).resolve().parents[2]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_rows(path: Path, rows: list[dict], *, allow_nan: bool = False) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=allow_nan) + "\n"
            for row in rows
        ),
        encoding="utf-8", newline="\n",
    )


def task_for(index: int) -> str:
    return f"task-{index % 5}"


def build_fixture(tmp_path: Path, run_count: int = 150) -> tuple[Path, Path]:
    intake_root = tmp_path / "intakes"
    intake = intake_root / "drop-a"
    intake.mkdir(parents=True)
    runs: list[dict] = []
    provenance: list[dict] = []
    pairs: list[dict] = []
    vault: list[dict] = []
    blind: list[dict] = []
    for run_index in range(run_count):
        journal = hashlib.sha256(f"journal-{run_index}".encode()).hexdigest()
        run_id = f"journal:{journal}"
        task = task_for(run_index)
        runs.append({
            "archive_name": "drop-a.tar.gz",
            "archive_sha256": "a" * 64,
            "generation_started_at_utc": f"2026-08-13T{run_index % 24:02d}:00:00Z",
            "journal_sha256": journal,
            "run_id": run_id,
            "task": task,
        })
        provenance.append({"run_id": run_id, "task": task})
        for parent_index in range(3):
            parent = f"parent-{run_index:03d}-{parent_index}"
            children = [f"card-{run_index:03d}-{parent_index}-{child}" for child in range(3)]
            for left_index, left in enumerate(children):
                for right in children[left_index + 1:]:
                    pairs.append({
                        "task": task, "run_id": run_id, "parent": parent,
                        "left": left, "right": right,
                    })
            for child_index, card in enumerate(children):
                code = f"print('run={run_index} parent={parent_index} child={child_index}')"
                vault.append({
                    "card_id": card, "task": task, "run_id": run_id,
                    "graded": 0.5, "y_norm": 0.5, "eligible_by_start_time": True,
                })
                blind.append({
                    "card_id": card, "task": task, "run_id": run_id,
                    "code": code, "code_sha256": text_sha(code),
                    "lineage": {
                        "parent": parent, "depth": 1, "step": child_index + 1,
                        "n_siblings": 3, "op": "Improve",
                    },
                    "generation_started_at_utc": runs[-1]["generation_started_at_utc"],
                    "source_sha256": journal,
                })
    provenance_path = intake / "source_provenance.json"
    pair_path = intake / "eligible_structural_pairs.jsonl"
    vault_path = intake / "label_vault.jsonl"
    blind_path = intake / "eligible_blind_manifest.jsonl"
    write_json(provenance_path, provenance)
    write_rows(pair_path, pairs)
    write_rows(vault_path, vault)
    write_rows(blind_path, blind)
    intake_summary = {
        "protocol": "prospective_drop_intake_v1",
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        },
        "security": {
            "env_members_read": False,
            "env_members_extracted": False,
            "live_event_journal_members_read": False,
            "journal_scanned_before_json": True,
            "credential_shaped_journals": 0,
            "raw_journals_written": False,
            "precutoff_endpoint_id_overlap": 0,
            "precutoff_code_sha256_overlap": 0,
        },
        "outputs": {
            "source_provenance_sha256": file_sha(provenance_path),
            "eligible_structural_pairs_sha256": file_sha(pair_path),
            "label_vault_sha256": file_sha(vault_path),
            "eligible_blind_manifest_sha256": file_sha(blind_path),
        },
    }
    intake_summary_path = intake / "summary.json"
    write_json(intake_summary_path, intake_summary)

    registry = tmp_path / "registry"
    registry.mkdir()
    run_path = registry / "eligible_runs.jsonl"
    write_rows(run_path, runs)
    per_task = {task: sum(row["task"] == task for row in runs) for task in sorted({row["task"] for row in runs})}
    dominant = max(per_task.values())
    enough = run_count >= 150
    balanced = dominant / run_count <= 0.25 if run_count else False
    registry_summary = {
        "protocol": "score-channel-run-eligibility-registry-v1",
        "status": "RUN_GATE_PASS_PARENT_GATE_PENDING" if enough and balanced else "RUN_GATE_WAIT",
        "mechanism_commit": selector.MECHANISM_COMMIT,
        "thresholds": {"min_runs": 150, "max_dominant_task_share": 0.25},
        "counts": {"eligible_post_mechanism_runs": run_count},
        "task_balance": {
            "dominant_task": max(per_task, key=per_task.get),
            "dominant_runs": dominant,
            "dominant_share": dominant / run_count,
            "per_task": per_task,
        },
        "gates": {
            "enough_runs": enough,
            "task_balance": balanced,
            "run_gate_pass": enough and balanced,
            "parent_gate_pending": True,
            "replay_submission_authorized": False,
        },
        "input_manifest": [{
            "intake": "drop-a", "runs": run_count,
            "source_provenance_sha256": file_sha(provenance_path),
            "summary_sha256": file_sha(intake_summary_path),
        }],
        "outputs": {"eligible_runs_sha256": file_sha(run_path)},
    }
    write_json(registry / "summary.json", registry_summary)
    return registry, intake_root


def resign_intake_and_registry(registry: Path, intake_root: Path) -> None:
    intake = intake_root / "drop-a"
    summary_path = intake / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["outputs"]["source_provenance_sha256"] = file_sha(intake / "source_provenance.json")
    summary["outputs"]["eligible_structural_pairs_sha256"] = file_sha(intake / "eligible_structural_pairs.jsonl")
    summary["outputs"]["label_vault_sha256"] = file_sha(intake / "label_vault.jsonl")
    summary["outputs"]["eligible_blind_manifest_sha256"] = file_sha(intake / "eligible_blind_manifest.jsonl")
    write_json(summary_path, summary)
    registry_summary_path = registry / "summary.json"
    registry_summary = json.loads(registry_summary_path.read_text(encoding="utf-8"))
    registry_summary["input_manifest"][0]["source_provenance_sha256"] = file_sha(intake / "source_provenance.json")
    registry_summary["input_manifest"][0]["summary_sha256"] = file_sha(summary_path)
    write_json(registry_summary_path, registry_summary)


def run_selector(registry: Path, intake_root: Path, output: Path) -> dict:
    return selector.produce(registry, intake_root, REPO, output)


def test_full_selection_verification_and_replay_freeze(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection = tmp_path / "selection"
    summary = run_selector(registry, intakes, selection)
    assert summary["counts"] == {
        "eligible_runs": 150,
        "runs_with_eligible_parents": 150,
        "runs_without_eligible_parents": 0,
        "eligible_parents": 450,
        "selected_parents": 300,
        "selected_candidates": 900,
        "tasks": 5,
    }
    rows = [json.loads(line) for line in (selection / "selected_parents.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(row["candidate_count"] == 3 for row in rows)
    assert all(not ({"graded", "y_norm", "gap", "winner", "code"} & set(row)) for row in rows)
    receipt_path = tmp_path / "selection_verified.json"
    receipt = verifier.verify(registry, intakes, selection, receipt_path)
    assert receipt["status"] == "PASS_PARENT_SELECTION_REPLAY_APPROVAL_PENDING"
    assert receipt["producer_module_imported"] is False
    assert receipt["replay_submission_authorized"] is False

    replay = tmp_path / "replay"
    replay_summary = materializer.produce(selection, intakes, REPO, replay)
    assert replay_summary["counts"]["planned_candidate_replays"] == 900
    assert replay_summary["budget"]["cap_upper_bound_gpu_hours"] == 30.0
    assert replay_summary["budget"]["gpu_jobs_submitted"] == 0
    assert replay_summary["gates"]["replay_submission_authorized"] is False
    replay_rows = [json.loads(line) for line in (replay / "replay_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    per_run: dict[str, set[int]] = {}
    for row in replay_rows:
        per_run.setdefault(row["run_id"], set()).add(row["shard_id"])
        assert row["cap_seconds"] == 120
        assert not ({"graded", "y_norm", "gap", "winner", "stdout_val", "sub_score"} & set(row))
    assert all(len(shards) == 1 for shards in per_run.values())
    replay_receipt = replay_verifier.verify(
        selection, intakes, replay, tmp_path / "replay_verified.json"
    )
    assert replay_receipt["status"] == "PASS_REPLAY_MANIFEST_APPROVAL_PENDING"
    assert replay_receipt["producer_module_imported"] is False
    assert replay_receipt["label_vault_opened"] is False


def test_run_gate_refuses_before_opening_missing_vault(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path, run_count=149)
    (intakes / "drop-a" / "label_vault.jsonl").unlink()
    with pytest.raises(selector.SelectionError, match="run gate"):
        run_selector(registry, intakes, tmp_path / "selection")


def test_selector_never_opens_blind_code_views(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    (intakes / "drop-a" / "eligible_blind_manifest.jsonl").unlink()
    summary = run_selector(registry, intakes, tmp_path / "selection")
    assert summary["blindness"]["code_opened"] is False
    assert summary["counts"]["selected_parents"] == 300


def test_nonfinite_grade_fails_closed_even_if_hashes_are_resigned(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    vault_path = intakes / "drop-a" / "label_vault.jsonl"
    rows = [json.loads(line) for line in vault_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["graded"] = float("nan")
    write_rows(vault_path, rows, allow_nan=True)
    resign_intake_and_registry(registry, intakes)
    with pytest.raises(selector.SelectionError, match="non-finite"):
        run_selector(registry, intakes, tmp_path / "selection")


def test_irrelevant_ineligible_vault_row_is_ignored_by_both_implementations(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    first_run = json.loads(
        (registry / "eligible_runs.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    vault_path = intakes / "drop-a" / "label_vault.jsonl"
    rows = [json.loads(line) for line in vault_path.read_text(encoding="utf-8").splitlines()]
    rows.append({
        "card_id": "irrelevant-precutoff-card",
        "task": first_run["task"],
        "run_id": first_run["run_id"],
        "graded": 0.1,
        "y_norm": 0.1,
        "eligible_by_start_time": False,
    })
    write_rows(vault_path, rows)
    resign_intake_and_registry(registry, intakes)

    selection = tmp_path / "selection"
    summary = run_selector(registry, intakes, selection)
    assert summary["counts"]["selected_candidates"] == 900
    receipt = verifier.verify(registry, intakes, selection, tmp_path / "receipt.json")
    assert receipt["status"] == "PASS_PARENT_SELECTION_REPLAY_APPROVAL_PENDING"


def test_ineligible_structural_child_still_fails_closed(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    vault_path = intakes / "drop-a" / "label_vault.jsonl"
    rows = [json.loads(line) for line in vault_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["eligible_by_start_time"] = False
    write_rows(vault_path, rows)
    resign_intake_and_registry(registry, intakes)
    with pytest.raises(selector.SelectionError, match="structural child is missing"):
        run_selector(registry, intakes, tmp_path / "selection")


def test_scoreless_physical_run_is_retained_with_zero_parent(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    pair_path = intakes / "drop-a" / "eligible_structural_pairs.jsonl"
    vault_path = intakes / "drop-a" / "label_vault.jsonl"
    first_run = json.loads((registry / "eligible_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])["run_id"]
    pairs = [json.loads(line) for line in pair_path.read_text(encoding="utf-8").splitlines()]
    vault = [json.loads(line) for line in vault_path.read_text(encoding="utf-8").splitlines()]
    write_rows(pair_path, [row for row in pairs if row["run_id"] != first_run])
    write_rows(vault_path, [row for row in vault if row["run_id"] != first_run])
    resign_intake_and_registry(registry, intakes)

    selection = tmp_path / "selection"
    summary = run_selector(registry, intakes, selection)
    assert summary["counts"]["eligible_runs"] == 150
    assert summary["counts"]["runs_with_eligible_parents"] == 149
    assert summary["counts"]["runs_without_eligible_parents"] == 1
    receipt = verifier.verify(registry, intakes, selection, tmp_path / "receipt.json")
    assert receipt["eligible_runs"] == 150


def test_selection_is_byte_deterministic_and_refuses_overwrite(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    first, second = tmp_path / "first", tmp_path / "second"
    run_selector(registry, intakes, first)
    run_selector(registry, intakes, second)
    assert (first / "selected_parents.jsonl").read_bytes() == (second / "selected_parents.jsonl").read_bytes()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_selector(registry, intakes, first)


def test_independent_verifier_rejects_resigned_selection_tamper(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection = tmp_path / "selection"
    run_selector(registry, intakes, selection)
    rows_path = selection / "selected_parents.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["selection_rank_in_run"] = 2
    write_rows(rows_path, rows)
    summary_path = selection / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["outputs"]["selected_parents_sha256"] = file_sha(rows_path)
    write_json(summary_path, summary)
    with pytest.raises(verifier.VerificationError, match="independent reconstruction"):
        verifier.verify(registry, intakes, selection, tmp_path / "receipt.json")


def test_independent_verifier_does_not_import_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection = tmp_path / "selection"
    run_selector(registry, intakes, selection)
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name.endswith("score_channel_parent_selector"):
            raise AssertionError("independent verifier imported producer")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    receipt = verifier.verify(registry, intakes, selection, tmp_path / "receipt.json")
    assert receipt["producer_module_imported"] is False


def test_replay_materializer_rejects_changed_intake_summary(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection = tmp_path / "selection"
    run_selector(registry, intakes, selection)
    intake_summary = intakes / "drop-a" / "summary.json"
    value = json.loads(intake_summary.read_text(encoding="utf-8"))
    value["status"] = "TAMPERED"
    write_json(intake_summary, value)
    with pytest.raises(materializer.ManifestError, match="changed after parent selection"):
        materializer.produce(selection, intakes, REPO, tmp_path / "replay")


def test_replay_verifier_rejects_resigned_candidate_tamper(tmp_path: Path) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection, replay = tmp_path / "selection", tmp_path / "replay"
    run_selector(registry, intakes, selection)
    materializer.produce(selection, intakes, REPO, replay)
    manifest_path = replay / "replay_manifest.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["cap_seconds"] = 119
    write_rows(manifest_path, rows)
    summary_path = replay / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["outputs"]["replay_manifest_sha256"] = file_sha(manifest_path)
    write_json(summary_path, summary)
    with pytest.raises(replay_verifier.ReplayVerificationError, match="independent reconstruction"):
        replay_verifier.verify(selection, intakes, replay, tmp_path / "receipt.json")


def test_replay_verifier_does_not_import_materializer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, intakes = build_fixture(tmp_path)
    selection, replay = tmp_path / "selection", tmp_path / "replay"
    run_selector(registry, intakes, selection)
    materializer.produce(selection, intakes, REPO, replay)
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name.endswith("score_channel_replay_manifest"):
            raise AssertionError("independent verifier imported replay producer")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    receipt = replay_verifier.verify(selection, intakes, replay, tmp_path / "receipt.json")
    assert receipt["producer_module_imported"] is False
