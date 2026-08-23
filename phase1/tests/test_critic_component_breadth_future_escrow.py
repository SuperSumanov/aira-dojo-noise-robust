from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from phase1 import critic_component_breadth_future_escrow as producer
from phase1 import verify_critic_component_breadth_future_escrow as verifier


ROOT = Path(__file__).parents[2]
CONTRACT = ROOT / "phase1" / "critic_component_breadth_future_escrow_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def blind_row(identifier: str, code: str, *, parent: str = "parent") -> dict:
    journal = hashlib.sha256(b"journal-0").hexdigest()
    return {
        "card_id": identifier,
        "task": "task-0",
        "run_id": f"journal:{journal}",
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {"depth": 1, "step": 1, "n_siblings": 2, "op": "Improve", "parent": parent},
        "generation_started_at_utc": "2026-08-24T00:00:00Z",
        "source_sha256": journal,
    }


def future_fixture(
    tmp_path: Path,
    *,
    status: str = "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD",
    bad_code_sha: bool = False,
    bad_parent: bool = False,
    credential: bool = False,
    missing_scoreable_run: bool = False,
    incomplete_clique: bool = False,
) -> tuple[Path, Path, str]:
    state = tmp_path / "state"
    intake = state / "intakes" / "drop-1"
    cohort = tmp_path / "cohort"
    intake.mkdir(parents=True)
    cohort.mkdir()
    left_code = "print('left')"
    if credential:
        left_code += "\n# sk-abcdefghijklmnop"
    blind = [blind_row("left", left_code), blind_row("right", "print('right')")]
    if incomplete_clique:
        blind.append(blind_row("third", "print('third')"))
    if bad_code_sha:
        blind[0]["code_sha256"] = "0" * 64
    structure = [
        {
            "task": "task-0",
            "run_id": blind[0]["run_id"],
            "parent": "wrong-parent" if bad_parent else "parent",
            "left": "left",
            "right": "right",
        }
    ]
    blind_path = intake / "eligible_blind_manifest.jsonl"
    structure_path = intake / "eligible_structural_pairs.jsonl"
    write_jsonl(blind_path, blind)
    write_jsonl(structure_path, structure)
    # Deliberately invalid; every successful blind test proves it remains unopened.
    (intake / "label_vault.jsonl").write_text("must-not-be-opened\n", encoding="utf-8")
    archive_sha = hashlib.sha256(b"archive").hexdigest()
    intake_summary = {
        "protocol": "prospective_drop_intake_v1",
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "configuration": {
            "archive_selection": "explicit_names",
            "selected_archive_names": ["archive.tar.gz"],
        },
        "security": {
            "credential_shaped_journals": 0,
            "env_members_extracted": False,
            "env_members_read": False,
            "journal_scanned_before_json": True,
            "live_event_journal_members_read": False,
            "precutoff_code_sha256_overlap": 0,
            "precutoff_endpoint_id_overlap": 0,
            "raw_journals_written": False,
        },
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        },
        "inventory": {
            "eligible_runs": 300,
            "eligible_endpoints": len(blind),
            "eligible_structural_pairs": len(structure),
        },
        "outputs": {
            "eligible_blind_manifest_sha256": digest(blind_path),
            "eligible_structural_pairs_sha256": digest(structure_path),
        },
    }
    intake_summary_path = intake / "summary.json"
    write_json(intake_summary_path, intake_summary)
    runs = []
    for index in range(300):
        journal = hashlib.sha256(f"journal-{index}".encode()).hexdigest()
        runs.append(
            {
                "archive_relative_path": "0824/archive.tar.gz",
                "archive_sha256": archive_sha,
                "drop_id": "drop-1",
                "endpoints": (
                    len(blind)
                    if index == 0
                    else 1
                    if index == 1 and missing_scoreable_run
                    else 0
                ),
                "flow_status": (
                    "scoreable"
                    if index == 0 or (index == 1 and missing_scoreable_run)
                    else "no_scoreable_code"
                ),
                "generation_started_at_utc": f"2026-08-24T00:{index // 60:02d}:{index % 60:02d}Z",
                "journal_sha256": journal,
                "run_id": f"journal:{journal}",
                "task": f"task-{index % 50}",
            }
        )
    run_path = cohort / "cohort_runs.jsonl"
    write_jsonl(run_path, runs)
    archive_rows = [
        {
            "archive_relative_path": "0824/archive.tar.gz",
            "archive_sha256": archive_sha,
            "archive_size": 1,
            "cumulative_unique_physical_runs": 300,
            "drop_id": "drop-1",
            "intake_summary_sha256": digest(intake_summary_path),
            "mtime_ns": 1,
            "physical_runs": 300,
            "source_provenance_sha256": hashlib.sha256(b"provenance").hexdigest(),
        }
    ]
    archive_path = cohort / "cohort_archives.jsonl"
    write_jsonl(archive_path, archive_rows)
    task_counts = {f"task-{index}": 6 for index in range(50)}
    summary = {
        "protocol": "score-channel-future-identity-cohort-v1",
        "status": status,
        "inputs": {
            "protocol_sha256": producer.load_contract(CONTRACT)["cohort"]["source_identity_protocol_sha256"],
            "intake_summary_sha256": {"drop-1": digest(intake_summary_path)},
            "source_provenance_sha256": {"drop-1": archive_rows[0]["source_provenance_sha256"]},
        },
        "closure": {
            "accepted_unique_physical_run_target": 300,
            "boundary_archive": "0824/archive.tar.gz" if status.endswith("TRUTH_UNREAD") else None,
            "complete_boundary_archive_included": status.endswith("TRUTH_UNREAD"),
            "remaining_runs_to_target": 0 if status.endswith("TRUTH_UNREAD") else 1,
        },
        "inventory": {
            "selected_physical_runs": 300,
            "selected_archives": 1,
            "selected_tasks": 50,
            "per_task_selected_runs": task_counts,
        },
        "blindness": {
            "label_vault_opened": False,
            "score_or_outcome_opened": False,
            "truth_support_computed": False,
            "replay_submission_authorized": False,
        },
        "outputs": {
            "cohort_runs_sha256": digest(run_path),
            "cohort_archives_sha256": digest(archive_path),
        },
    }
    summary_path = cohort / "summary.json"
    write_json(summary_path, summary)
    return state, cohort, digest(summary_path)


def test_contract_is_exact_and_truth_free() -> None:
    contract = producer.load_contract(CONTRACT)
    assert digest(CONTRACT) == producer.CONTRACT_SHA256 == verifier.CONTRACT_SHA256
    assert contract["prediction_escrow"]["label_vault_path_accepted_by_cli"] is False
    assert contract["claim_boundary"]["known_before_freeze"]["future_cohort_labels_or_scores_read"] is False


def test_independent_verifier_does_not_import_producer() -> None:
    path = ROOT / "phase1" / "verify_critic_component_breadth_future_escrow.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name.endswith("critic_component_breadth_future_escrow") for name in imports)
    assert not any(name.endswith("score_channel_future_truth_support") for name in imports)


def test_closed_cohort_blind_reconstruction_never_opens_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, cohort, summary_sha = future_fixture(tmp_path)
    original = Path.open

    def guarded(self: Path, *args, **kwargs):
        if self.name == "label_vault.jsonl":
            raise AssertionError("label vault was opened")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    runs, archives, _ = producer.load_cohort(cohort, summary_sha)
    cards, pairs, inputs = producer.load_future_blind(state, runs, archives)
    assert set(cards) == {"left", "right"}
    assert len(pairs) == 1
    assert set(inputs["eligible_blind_manifest_sha256"]) == {"drop-1"}


def test_collecting_cohort_fails_before_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state, cohort, summary_sha = future_fixture(tmp_path, status="FUTURE_COHORT_COLLECTING")
    original = Path.open

    def guarded(self: Path, *args, **kwargs):
        if self.name == "label_vault.jsonl":
            raise AssertionError("label vault was opened")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(producer.EscrowError, match="closed and truth-unread"):
        producer.load_cohort(cohort, summary_sha)


def test_formal_entry_rejects_collecting_before_training_open(tmp_path: Path) -> None:
    state, cohort, summary_sha = future_fixture(tmp_path, status="FUTURE_COHORT_COLLECTING")
    args = argparse.Namespace(
        contract=CONTRACT,
        training_cards=tmp_path / "must-not-open-cards",
        train_pairs=tmp_path / "must-not-open-train",
        cohort_dir=cohort,
        expect_cohort_summary_sha256=summary_sha,
        state_root=state,
        repo_root=ROOT,
        output=tmp_path / "output",
    )
    with pytest.raises(producer.EscrowError, match="closed and truth-unread"):
        producer.produce(args)


@pytest.mark.parametrize(
    ("fixture_kwargs", "message"),
    [
        ({"bad_code_sha": True}, "invalid or duplicate blind endpoint"),
        ({"bad_parent": True}, "invalid or duplicate structural pair"),
        ({"credential": True}, "credential-shaped bytes"),
    ],
)
def test_blind_input_attacks_fail_closed(tmp_path: Path, fixture_kwargs: dict, message: str) -> None:
    state, cohort, summary_sha = future_fixture(tmp_path, **fixture_kwargs)
    runs, archives, _ = producer.load_cohort(cohort, summary_sha)
    with pytest.raises(producer.EscrowError, match=message):
        producer.load_future_blind(state, runs, archives)


@pytest.mark.parametrize(
    ("fixture_kwargs", "producer_message", "verifier_message"),
    [
        (
            {"missing_scoreable_run": True},
            "endpoint/run accounting",
            "endpoint/run accounting",
        ),
        (
            {"incomplete_clique": True},
            "sibling pair population",
            "sibling population",
        ),
    ],
)
def test_population_completeness_attacks_fail_in_both_implementations(
    tmp_path: Path,
    fixture_kwargs: dict,
    producer_message: str,
    verifier_message: str,
) -> None:
    state, cohort, summary_sha = future_fixture(tmp_path, **fixture_kwargs)
    runs, archives, _ = producer.load_cohort(cohort, summary_sha)
    with pytest.raises(producer.EscrowError, match=producer_message):
        producer.load_future_blind(state, runs, archives)
    with pytest.raises(verifier.VerificationError, match=verifier_message):
        verifier.load_future(state, cohort, summary_sha)


def test_independent_numerical_refit_matches_producer() -> None:
    selected = []
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    for index in range(4):
        better, worse = f"better-{index}", f"worse-{index}"
        codes[better] = f"common common alpha alpha\nprint({index})"
        codes[worse] = f"common common beta beta\nprint({index})"
        runs[better] = runs[worse] = f"run-{index}"
        selected.append(
            {
                "task": "task",
                "parent": f"parent-{index}",
                "better": better,
                "worse": worse,
                "pair_component_id": f"{index + 1:064x}",
            }
        )
    future = {
        "future-a": {"code": "common alpha alpha\nprint('future')"},
        "future-b": {"code": "common beta beta\nprint('future')"},
    }
    left, left_receipt = producer.fit_and_score(selected, codes, runs, future, {})
    right, right_receipt = verifier.refit_scores(selected, codes, runs, future)
    assert left_receipt == right_receipt
    assert set(left) == set(right)
    assert max(abs(left[key] - right[key]) for key in left) <= 1e-12


def test_artifact_numeric_tamper_is_rejected() -> None:
    with pytest.raises(verifier.VerificationError, match="numeric mismatch"):
        verifier.close_enough({"score": 0.0}, {"score": 1e-4})


def test_stable_artifact_reader_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(verifier.VerificationError, match="symlinked"):
        verifier.stable_file_bytes(link, "synthetic artifact")


def test_manual_runner_has_preflight_and_no_resource_submission() -> None:
    runner = (
        ROOT / "phase1" / "scripts" / "run_critic_component_breadth_future_escrow_20260824.sh"
    ).read_text(encoding="utf-8")
    assert "c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b" in runner
    assert all(f"{index:02d}_" in runner for index in range(1, 13))
    assert "sbatch" not in runner
    assert "srun" not in runner
    assert runner.count("label_vault") == 1  # forbidden-open audit only
    assert "--label-vault" not in runner
