import argparse
import hashlib
import json
import shlex
from pathlib import Path

import pytest

from phase1 import build_prediction_receipt_common_support as producer
from phase1 import verify_prediction_receipt_common_support as independent


ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "phase1/scripts/monitor_prediction_coverage_snapshot_chain_20260826.sh"
PROTOCOL = ROOT / "phase1/prediction_receipt_common_support_protocol_v1.json"
BUILDER = ROOT / "phase1/build_prediction_receipt_common_support.py"
VERIFIER = ROOT / "phase1/verify_prediction_receipt_common_support.py"
SNAPSHOT = "1" * 64


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(module: str, snapshot: str, artifact: Path, output: Path) -> str:
    words = [
        "env",
        "PYTHONPATH=/frozen/source",
        "/usr/bin/python3",
        "-m",
        module,
        "--expect-snapshot-sha256",
        snapshot,
        "--artifact",
        str(artifact),
        "--output",
        str(output),
    ]
    return " ".join(shlex.quote(word) for word in words) + "\n"


def fixture(tmp_path: Path) -> argparse.Namespace:
    wl_parent = tmp_path / "wl"
    tr_parent = tmp_path / "transition"
    wl_artifact = wl_parent / "artifact"
    tr_artifact = tr_parent / "artifact"
    wl_artifact.mkdir(parents=True)
    tr_artifact.mkdir(parents=True)
    # Deliberately invalid JSON: the implementation may hash summary bytes but never parse them.
    (wl_artifact / "summary.json").write_bytes(b"WL SUMMARY BYTES, NOT JSON\n")
    (tr_artifact / "summary.json").write_bytes(b"TRANSITION SUMMARY BYTES, NOT JSON\n")

    wl_source = tmp_path / "wl_verifier.py"
    tr_source = tmp_path / "transition_verifier.py"
    wl_source.write_text("# frozen wl verifier\n", encoding="utf-8")
    tr_source.write_text("# frozen transition verifier\n", encoding="utf-8")
    protocol_path = tmp_path / "protocol.json"
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    protocol["verifier_contracts"]["wl"]["source_sha256"] = sha(wl_source)
    protocol["verifier_contracts"]["transition"]["source_sha256"] = sha(tr_source)
    protocol_path.write_text(json.dumps(protocol, sort_keys=True) + "\n", encoding="utf-8")

    wl_receipt = wl_parent / "independent_verification.json"
    tr_receipt = tr_parent / "verification.json"
    wl_receipt.write_text(
        json.dumps(
            {
                "status": "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED",
                "artifact_summary_sha256": sha(wl_artifact / "summary.json"),
                "snapshot_sha256": SNAPSHOT,
                "pairs": 17,
                "prospective_outcomes_read": False,
                "effect_metrics_computed": [],
                "maximum_absolute_score_difference": {"ignored_not_exposed": 123.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    tr_receipt.write_text(
        json.dumps(
            {
                "status": "INDEPENDENT_PROSPECTIVE_TRANSITION_FUTURE_ESCROW_VERIFIED",
                "artifact_summary_sha256": sha(tr_artifact / "summary.json"),
                "pairs": 17,
                "scope": {"prospective_outcomes_read": False, "effect_metrics_computed": []},
                "maximum_future_margin_difference": 987.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    wl_command = wl_parent / "independent_verifier_command.txt"
    tr_command = tr_parent / "verifier_command.txt"
    wl_command.write_text(
        command("phase1.verify_prospective_wl_graph_escrow", SNAPSHOT, wl_artifact, wl_receipt),
        encoding="utf-8",
    )
    tr_command.write_text(
        command("phase1.verify_prospective_transition_future_escrow", SNAPSHOT, tr_artifact, tr_receipt),
        encoding="utf-8",
    )
    wl_state = tmp_path / "wl_state.tsv"
    tr_state = tmp_path / "transition_state.tsv"
    wl_state.write_text(f"{SNAPSHOT}\t{wl_artifact}\t{sha(wl_artifact / 'summary.json')}\t20\n", encoding="utf-8")
    tr_state.write_text(f"{SNAPSHOT}\t{tr_artifact}\t{sha(tr_artifact / 'summary.json')}\n", encoding="utf-8")
    return argparse.Namespace(
        protocol=protocol_path,
        expect_protocol_sha256=sha(protocol_path),
        expect_snapshot_sha256=SNAPSHOT,
        wl_state=wl_state,
        transition_state=tr_state,
        wl_independent_receipt=wl_receipt,
        transition_independent_receipt=tr_receipt,
        wl_verifier_command=wl_command,
        transition_verifier_command=tr_command,
        wl_verifier_source=wl_source,
        transition_verifier_source=tr_source,
        output=tmp_path / "unused.json",
    )


def build_and_verify(args: argparse.Namespace, tmp_path: Path) -> tuple[dict, dict]:
    receipt = producer.build(args)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_args = argparse.Namespace(**vars(args), candidate=candidate)
    verification = independent.verify(verify_args)
    return receipt, verification


def test_receipt_only_positive_path_never_needs_parseable_summaries(tmp_path: Path) -> None:
    receipt, verification = build_and_verify(fixture(tmp_path), tmp_path)
    assert receipt["receipt_certified_common_support"]["pairs"] == 17
    assert receipt["receipt_certified_common_support"]["pair_identity_or_orientation_reopened"] is False
    assert verification["status"] == "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED"
    assert verification["prediction_values_accessed"] is False
    assert "maximum_future_margin_difference" not in json.dumps(receipt)
    assert "maximum_absolute_score_difference" not in json.dumps(receipt)


def test_mismatched_pair_counts_fail_closed(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    value = json.loads(args.transition_independent_receipt.read_text(encoding="utf-8"))
    value["pairs"] = 18
    args.transition_independent_receipt.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(producer.ReceiptSupportError, match="pair counts differ"):
        producer.build(args)


def test_command_snapshot_mismatch_fails_closed(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    args.transition_verifier_command.write_text(
        command(
            "phase1.verify_prospective_transition_future_escrow",
            "2" * 64,
            Path(str(args.transition_state.read_text().split("\t")[1])),
            args.transition_independent_receipt,
        ),
        encoding="utf-8",
    )
    with pytest.raises(producer.ReceiptSupportError, match="command snapshot mismatch"):
        producer.build(args)


def test_summary_tamper_fails_before_receipt_join(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    artifact = Path(args.wl_state.read_text(encoding="utf-8").split("\t")[1])
    (artifact / "summary.json").write_bytes(b"tampered\n")
    with pytest.raises(producer.ReceiptSupportError, match="state summary hash mismatch"):
        producer.build(args)


def test_source_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    args.wl_verifier_source.write_text("# mutated\n", encoding="utf-8")
    with pytest.raises(producer.ReceiptSupportError, match="source hash mismatch"):
        producer.build(args)


def test_independent_verifier_rejects_candidate_mutation(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    receipt = producer.build(args)
    receipt["receipt_certified_common_support"]["pairs"] += 1
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    with pytest.raises(independent.VerificationError, match="independent reconstruction"):
        independent.verify(argparse.Namespace(**vars(args), candidate=candidate))


def test_monitor_uses_receipts_only_and_runs_deterministic_ab() -> None:
    text = MONITOR.read_text(encoding="utf-8")
    assert "build_prediction_receipt_common_support" in text
    assert "verify_prediction_receipt_common_support" in text
    assert "receipt_a.json" in text and "receipt_b.json" in text
    assert "verification_a.json" in text and "verification_b.json" in text
    assert text.count("cmp ") >= 2
    assert "strace -ff -e trace=file" in text
    assert "prediction_pair_file_open_hits" in text
    assert "stable_count >= stable_polls" in text
    assert "run_prediction_coverage_generic" not in text
    assert "prediction_escrow_coverage_matrix" not in text


def test_monitor_is_cpu_only_fail_closed_and_atomic() -> None:
    text = MONITOR.read_text(encoding="utf-8")
    for variable in (
        "PYTHONHASHSEED=0",
        "OMP_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "NUMEXPR_NUM_THREADS=1",
        "VECLIB_MAXIMUM_THREADS=1",
        "BLIS_NUM_THREADS=1",
    ):
        assert variable in text
    assert "gpu=0,api=0,model fit=0,base LLM updates=0" in text
    assert 'mv "${state_file}.next" "${state_file}"' in text
    assert "any failure prevents receipt state promotion" in text


def test_builder_and_verifier_do_not_name_or_open_prediction_pair_files() -> None:
    builder_text = BUILDER.read_text(encoding="utf-8")
    verifier_text = VERIFIER.read_text(encoding="utf-8")
    for forbidden in ("pair_predictions.jsonl", 'artifact / "pairs.jsonl"'):
        assert forbidden not in builder_text
        assert forbidden not in verifier_text
    assert "from phase1 import build_prediction_receipt_common_support" not in verifier_text
    assert "import build_prediction_receipt_common_support" not in verifier_text


def test_checked_in_protocol_forbids_prediction_access() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert value["claim"]["same_pair_count_alone_is_sufficient"] is False
    assert value["inputs"]["prediction_pair_files_opened"] is False
    assert value["inputs"]["artifact_summary_content_parsed"] is False
    assert value["scope"]["prediction_values_accessed"] is False
    assert value["scope"]["prediction_value_aggregates_computed"] == []
