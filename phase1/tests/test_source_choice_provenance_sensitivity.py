import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import source_choice_provenance_sensitivity as sensitivity


def identity(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_bytes(b"".join(sensitivity.canonical(row) + b"\n" for row in rows))


def write_root_manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        rows.append(f"{sensitivity.digest(path)}  ./{path.relative_to(root).as_posix()}\n")
    (root / "SHA256SUMS").write_text("".join(rows), encoding="utf-8")


def fixture(tmp_path: Path):
    commit = "1" * 40
    raw_rows = []
    model_rows = []
    prediction_rows = []
    for task_index in range(5):
        task = f"task-{task_index}"
        group_id = identity(task + "-group")
        winner_id = identity(task + "-winner")
        loser_id = identity(task + "-loser")
        candidates = []
        for candidate_id, label, step in ((winner_id, "winner", 2), (loser_id, "loser", 1)):
            code = f"print('{task}-{label}')"
            candidates.append({
                "candidate_id_sha256": candidate_id,
                "code": code,
                "code_sha256": identity(code),
                "operator": "improve",
                "step": step,
                "depth": 1,
                "provenance": "card",
                "source_journal_sha256": None,
            })
        candidates.sort(key=lambda item: item["candidate_id_sha256"])
        run_id = identity(task + "-run")
        raw_rows.append({
            "schema_version": sensitivity.RAW_SCHEMA,
            "group_id": group_id,
            "role": "train",
            "task": task,
            "run_id_sha256": run_id,
            "parent_id_sha256": identity(task + "-parent"),
            "source_size": 2,
            "candidates": candidates,
            "winner_candidate_sha256": winner_id,
        })
        prediction_rows.append({
            "split": "task_loto", "fold": task, "arm": "tfidf_pairwise_lr",
            "group_id": group_id, "task": task, "run_id_sha256": run_id,
            "source_size": 2, "selected_candidate_sha256": winner_id,
            "hit": 1, "winner_rank": 1,
        })

    task = "task-0"
    group_id = identity("mixed-group")
    winner_id = identity("mixed-winner")
    card_loser_id = identity("mixed-card-loser")
    recovered_id = identity("mixed-recovered")
    mixed_candidates = []
    for candidate_id, label, provenance in (
        (winner_id, "winner", "card"),
        (card_loser_id, "card-loser", "card"),
        (recovered_id, "recovered", "journal_recovered"),
    ):
        code = f"print('mixed-{label}')"
        mixed_candidates.append({
            "candidate_id_sha256": candidate_id,
            "code": code,
            "code_sha256": identity(code),
            "operator": "Improve",
            "step": 3,
            "depth": 2,
            "provenance": provenance,
            "source_journal_sha256": identity("journal") if provenance == "journal_recovered" else None,
        })
    mixed_candidates.sort(key=lambda item: item["candidate_id_sha256"])
    run_id = identity("mixed-run")
    raw_rows.append({
        "schema_version": sensitivity.RAW_SCHEMA,
        "group_id": group_id,
        "role": "train",
        "task": task,
        "run_id_sha256": run_id,
        "parent_id_sha256": identity("mixed-parent"),
        "source_size": 3,
        "candidates": mixed_candidates,
        "winner_candidate_sha256": winner_id,
    })
    prediction_rows.append({
        "split": "task_loto", "fold": task, "arm": "tfidf_pairwise_lr",
        "group_id": group_id, "task": task, "run_id_sha256": run_id,
        "source_size": 3, "selected_candidate_sha256": recovered_id,
        "hit": 0, "winner_rank": 2,
    })

    raw_rows.sort(key=lambda item: item["group_id"])
    for raw in raw_rows:
        model_rows.append({
            "schema_version": sensitivity.MODEL_SCHEMA,
            "group_id": raw["group_id"],
            "task": raw["task"],
            "source_size": raw["source_size"],
            "candidates": [
                {
                    "candidate_id_sha256": item["candidate_id_sha256"],
                    "code": item["code"],
                    "code_sha256": item["code_sha256"],
                    "operator": sensitivity.OPERATOR_MAP[item["operator"].casefold()],
                    "step": item["step"],
                    "depth": item["depth"],
                }
                for item in raw["candidates"]
            ],
            "winner_candidate_sha256": raw["winner_candidate_sha256"],
        })
    raw_path = tmp_path / "raw.jsonl"
    model_path = tmp_path / "model.jsonl"
    write_jsonl(raw_path, raw_rows)
    write_jsonl(model_path, model_rows)

    oof_root = tmp_path / "oof"
    result_a = oof_root / "result_a"
    result_b = oof_root / "result_b"
    result_a.mkdir(parents=True)
    result_b.mkdir()
    prediction_fields = [
        "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "hit", "winner_rank",
    ]
    with (result_a / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=prediction_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(prediction_rows)
    (result_a / "per_task.csv").write_text("placeholder\n", encoding="utf-8")
    write_json(result_a / "fold_receipts.json", {})
    result_outputs = {
        name: sensitivity.digest(result_a / name)
        for name in ("predictions.csv", "per_task.csv", "fold_receipts.json")
    }
    summary = {
        "protocol": "source-choice-oof-tfidf-v1",
        "status": "SOURCE_CHOICE_OOF_TFIDF_COMPLETE",
        "verdict": "GO_CROSS_TASK",
        "outputs": result_outputs,
    }
    write_json(result_a / "summary.json", summary)
    result_manifest = {
        name: sensitivity.digest(result_a / name)
        for name in ("predictions.csv", "per_task.csv", "fold_receipts.json", "summary.json")
    }
    write_json(result_a / "sha256_manifest.json", result_manifest)
    write_json(result_b / "summary.json", summary)
    (oof_root / "COMPLETE").write_text("SOURCE_CHOICE_OOF_TFIDF_FORMAL_COMPLETE\n", encoding="utf-8")
    (oof_root / "control_commit.txt").write_text(commit + "\n", encoding="utf-8")
    (oof_root / "result_reproducibility.diff").write_bytes(b"")
    (oof_root / "producer_a.stderr").write_bytes(b"")
    (oof_root / "producer_b.stderr").write_bytes(b"")
    (oof_root / "trace_audit.txt").write_text("forbidden_scientific_model_or_vault_path_hits=0\n", encoding="utf-8")
    (oof_root / "credential_filename_hits.txt").write_text("0\n", encoding="utf-8")
    (oof_root / "credential_content_hits.txt").write_text("0\n", encoding="utf-8")
    write_root_manifest(oof_root)

    verification_root = tmp_path / "verification"
    verification_root.mkdir()
    verification = {
        "status": "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED",
        "producer_imported": False,
        "model_refit_by_verifier": False,
        "verdict": "GO_CROSS_TASK",
        "summary_sha256": sensitivity.digest(result_a / "summary.json"),
    }
    write_json(verification_root / "verification_a.json", verification)
    write_json(verification_root / "verification_b.json", verification)
    (verification_root / "COMPLETE").write_text(
        "SOURCE_CHOICE_OOF_TFIDF_INDEPENDENT_VERIFICATION_COMPLETE\n", encoding="utf-8"
    )
    (verification_root / "result_commit.txt").write_text(commit + "\n", encoding="utf-8")
    (verification_root / "verification_reproducibility.diff").write_bytes(b"")
    (verification_root / "verifier_a.stderr").write_bytes(b"")
    (verification_root / "verifier_b.stderr").write_bytes(b"")
    (verification_root / "trace_audit.txt").write_text("forbidden_scientific_model_or_vault_path_hits=0\n", encoding="utf-8")
    (verification_root / "credential_filename_hits.txt").write_text("0\n", encoding="utf-8")
    (verification_root / "credential_content_hits.txt").write_text("0\n", encoding="utf-8")
    write_root_manifest(verification_root)

    exact_root = tmp_path / "exact"
    exact_root.mkdir()
    exact = {
        "protocol": "source-choice-oof-exact-sign-audit-v1",
        "status": "SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_COMPLETE",
        "reported_verdict": "GO_CROSS_TASK",
        "exact_sign_verdict": "GO_CROSS_TASK",
        "summary_sha256": sensitivity.digest(result_a / "summary.json"),
        "predictions_sha256": sensitivity.digest(result_a / "predictions.csv"),
        "model_refit": False,
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
    }
    write_json(exact_root / "audit_a.json", exact)
    write_json(exact_root / "audit_b.json", exact)
    (exact_root / "COMPLETE").write_text(
        "SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_FORMAL_COMPLETE\n", encoding="utf-8"
    )
    (exact_root / "result_commit.txt").write_text(commit + "\n", encoding="utf-8")
    (exact_root / "audit_commit.txt").write_text("2" * 40 + "\n", encoding="utf-8")
    (exact_root / "audit_reproducibility.diff").write_bytes(b"")
    (exact_root / "audit_a.stderr").write_bytes(b"")
    (exact_root / "audit_b.stderr").write_bytes(b"")
    (exact_root / "trace_audit.txt").write_text("forbidden_scientific_model_or_vault_path_hits=0\n", encoding="utf-8")
    (exact_root / "credential_filename_hits.txt").write_text("0\n", encoding="utf-8")
    (exact_root / "credential_content_hits.txt").write_text("0\n", encoding="utf-8")
    write_root_manifest(exact_root)

    protocol = {
        "protocol": sensitivity.PROTOCOL,
        "activation": {
            "required_formal_result_commit": commit,
            "required_independent_verification_status": "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED",
            "allowed_verdicts": ["GO_CROSS_TASK", "GO_RUN_ONLY"],
            "blocked_verdict": "NO_NARROW_POSITIVE",
        },
        "inputs": {
            "raw_train_groups_sha256": sensitivity.digest(raw_path),
            "decision_view_train_sha256": sensitivity.digest(model_path),
            "expected_oof_protocol": "source-choice-oof-tfidf-v1",
            "expected_oof_split": "task_loto",
            "expected_oof_arm": "tfidf_pairwise_lr",
        },
        "support": {
            "train_groups": 6, "card_candidates": 12, "journal_recovered_candidates": 1,
            "all_card_groups": 5, "all_card_tasks": 5,
            "all_card_source_size_counts": {"2": 5},
            "mixed_groups": 1, "mixed_tasks": 1,
            "mixed_source_size_counts": {"3": 1},
            "all_winners_have_card_provenance": True,
            "minimum_all_card_groups": 5, "minimum_all_card_tasks": 5,
        },
        "analysis": {
            "model_refit": False, "predictions_reused_without_change": True,
            "primary_subset": "all candidates have provenance card",
            "primary_estimand": "task_macro_top1_delta_over_exact_subset_uniform",
            "primary_bootstrap_unit": "task", "bootstrap_replicates": 1000,
            "bootstrap_seed": 20260824,
            "task_sign_test": "one_sided_exact_positive_ignoring_exact_zero",
            "secondary": ["mixed"],
        },
        "gate": {
            "minimum_absolute_all_card_task_macro_delta": 0.03,
            "maximum_one_sided_task_sign_p": 0.05,
            "pass": "fixed", "outcomes": [
                "ROBUST_BEYOND_RECOVERY_MIX", "RECOVERY_MIX_SENSITIVE",
                "ABORT_SUPPORT_OR_BINDING",
            ],
        },
        "interpretation": {"pass_allows": "fixed", "fail_requires": "fixed", "pass_does_not_allow": "fixed"},
        "scope": {
            "train_only": True, "frozen_or_extension_model_read": False,
            "frozen_or_extension_label_vault_read": False,
            "new_model_or_hyperparameter": False, "gpu": 0, "api_calls": 0,
            "base_llm_updated": False,
        },
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return protocol_path, raw_path, model_path, oof_root, verification_root, exact_root


def test_all_card_signal_survives_recovery_sensitivity(tmp_path: Path):
    inputs = fixture(tmp_path)
    result = sensitivity.analyze(*inputs, tmp_path / "output")
    assert result["verdict"] == "ROBUST_BEYOND_RECOVERY_MIX"
    assert result["primary_all_card"]["groups"] == 5
    assert result["primary_all_card"]["task_macro_delta"] == 0.5
    assert result["primary_all_card"]["task_sign"]["one_sided_p"] == 0.03125
    assert result["secondary_mixed"]["card_only_uniform_micro_expected_accuracy"] == 0.5
    assert result["secondary_mixed"]["selected_card_rate"] == 0.0
    assert result["model_refit"] is False


def test_blocked_oof_verdict_cannot_activate(tmp_path: Path):
    inputs = list(fixture(tmp_path))
    verification_root = inputs[4]
    for name in ("verification_a.json", "verification_b.json"):
        value = json.loads((verification_root / name).read_text(encoding="utf-8"))
        value["verdict"] = "NO_NARROW_POSITIVE"
        write_json(verification_root / name, value)
    write_root_manifest(verification_root)
    with pytest.raises(sensitivity.SensitivityError, match="not activated"):
        sensitivity.analyze(*inputs, tmp_path / "output")


def test_sign_test_uses_mathematical_exact_zero():
    result = sensitivity.exact_sign(
        [Fraction(1, 3), Fraction(-1, 3), Fraction(1, 3) - Fraction(1, 3)]
    )
    assert result == {"positive": 1, "negative": 1, "zero": 1, "one_sided_p": 0.75}


def test_exact_sign_no_blocks_recovery_sensitivity(tmp_path: Path):
    inputs = list(fixture(tmp_path))
    exact_root = inputs[5]
    for name in ("audit_a.json", "audit_b.json"):
        value = json.loads((exact_root / name).read_text(encoding="utf-8"))
        value["exact_sign_verdict"] = "NO_NARROW_POSITIVE"
        write_json(exact_root / name, value)
    write_root_manifest(exact_root)
    with pytest.raises(sensitivity.SensitivityError, match="exact-sign activation"):
        sensitivity.analyze(*inputs, tmp_path / "output")
