from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v9 as builder
from phase1 import verify_decision_corpus_evidence_index_v9 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_RELATIVE = Path("phase1/decision_corpus_evidence_index_v9_protocol_v1.json")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    protocol_target = root / PROTOCOL_RELATIVE
    protocol_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / PROTOCOL_RELATIVE, protocol_target)
    protocol = json.loads(protocol_target.read_text(encoding="utf-8"))
    source = Path(protocol["source_v8"]["path"])
    (root / source).parent.mkdir(parents=True)
    shutil.copy2(ROOT / source, root / source)
    package = Path(protocol["lineage_package"]["root"])
    shutil.copytree(ROOT / package, root / package)
    return root, protocol_target


def build_candidate(root: Path, protocol_path: Path) -> tuple[dict, Path]:
    candidate = builder.build_index(root, protocol_path)
    output = root / "candidate.json"
    write_json(output, candidate)
    return candidate, output


def test_real_v9_replaces_only_decision_entry_and_verifies(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    source = json.loads((root / candidate["source_v8_index"]["path"]).read_text(encoding="utf-8"))
    assert candidate["protocol"] == "decision_corpus_evidence_index_v9"
    assert candidate["status"] == source["status"]
    assert candidate["entries"][0]["name"] == "decision_corpus"
    assert candidate["entries"][0] != source["entries"][0]
    assert candidate["entries"][1:] == source["entries"][1:]
    receipt = verifier.verify_candidate(root, protocol_path, output)
    assert receipt["entries_replaced"] == 1
    assert receipt["entries_preserved_without_modification"] == 15
    assert receipt["all_aggregate_fields_equal"] is True


def test_limited_support_and_b2_failure_are_preserved(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, _ = build_candidate(root, protocol_path)
    repair = candidate["lineage_repair"]
    assert repair["classification"] == "HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT"
    assert repair["support_gates_passed"] == 35
    assert repair["support_gates_total"] == 36
    assert repair["all_support_gates_passed"] is False
    assert repair["failed_support_gate"] == "frozen:b2.maximum_single_run_pair_share"
    assert candidate["reporting_contract"]["parent_complete_all_support_gates_pass_language_allowed"] is False
    assert candidate["reporting_contract"]["frozen_b2_run_concentration_limitation_required"] is True


def test_source_v8_hash_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source = root / protocol["source_v8"]["path"]
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(builder.BuildError, match="source v8 SHA"):
        builder.build_index(root, protocol_path)


def test_lineage_manifest_member_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    producer = root / protocol["lineage_package"]["root"] / protocol["lineage_package"]["producer_path"]
    producer.write_text(producer.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(builder.BuildError, match="manifest hash mismatch"):
        builder.build_index(root, protocol_path)


def test_candidate_cannot_hide_failed_support_gate(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    candidate["lineage_repair"]["all_support_gates_passed"] = True
    write_json(output, candidate)
    with pytest.raises(verifier.VerificationError, match="candidate differs"):
        verifier.verify_candidate(root, protocol_path, output)


def test_candidate_cannot_promote_provisional_status(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    candidate["status"] = "COMPLETE"
    write_json(output, candidate)
    with pytest.raises(verifier.VerificationError, match="candidate differs"):
        verifier.verify_candidate(root, protocol_path, output)


def test_candidate_cannot_change_an_unrelated_entry(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    candidate["entries"][1]["supported_claim"] = "drift"
    write_json(output, candidate)
    with pytest.raises(verifier.VerificationError, match="candidate differs"):
        verifier.verify_candidate(root, protocol_path, output)


def test_verifier_does_not_import_builder() -> None:
    source = inspect.getsource(verifier)
    assert "build_decision_corpus_evidence_index_v9" not in source
    assert "from phase1 import build" not in source
