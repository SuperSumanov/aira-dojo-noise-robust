import json
from argparse import Namespace
from pathlib import Path

from phase1.audit_prospective_operator_support import collect, run, sha256_file, summarize
from phase1.verify_prospective_operator_support import verify


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_collect_and_summarize(tmp_path: Path) -> None:
    state = tmp_path / "state"
    intake = state / "intakes" / "drop-a"
    intake.mkdir(parents=True)
    rows = [
        {"card_id": "a", "task": "t", "run_id": "r", "code": "x", "lineage": {"parent": "p", "op": "Debug"}},
        {"card_id": "b", "task": "t", "run_id": "r", "code": "y", "lineage": {"parent": "p", "op": "Improve"}},
    ]
    manifest = intake / "eligible_blind_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    summary = {
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "blindness": {"labels_used_for_endpoint_selection": False, "labels_used_for_run_selection": False, "metrics_computed": []},
        "security": {"env_members_read": False, "credential_shaped_journals": 0},
        "outputs": {"eligible_blind_manifest_sha256": sha256_file(manifest)},
    }
    summary_path = intake / "summary.json"
    write_json(summary_path, summary)
    transaction = {"drop_id": "drop-a", "intake_dir": str(intake.resolve()), "intake_summary_sha256": sha256_file(summary_path)}
    transactions = tmp_path / "transactions.jsonl"
    transactions.write_text(json.dumps(transaction) + "\n", encoding="utf-8")
    args = Namespace(transactions=str(transactions), expect_transactions_sha256=sha256_file(transactions), expect_transactions=1, state_root=str(state))
    parents, metadata = collect(args)
    result = summarize(parents, metadata, "0" * 40)
    assert result["inventory"]["mixed_operator_parents"] == 1
    assert result["inventory"]["exact_two_mixed_operator_parents"] == 1
    assert result["status"] == "INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT"

    output = tmp_path / "artifact"
    producer_args = Namespace(**vars(args), source_commit="0" * 40, output=str(output))
    assert run(producer_args) == 0
    verification = verify(Namespace(artifact=str(output)))
    assert verification["status"] == "INDEPENDENT_OPERATOR_SUPPORT_ARTIFACT_VERIFIED"
    assert verification["producer_status"] == "INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT"
