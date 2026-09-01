from __future__ import annotations

import copy
import inspect
import json
import shutil
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v10 as builder
from phase1 import verify_decision_corpus_evidence_index_v10 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_RELATIVE = Path("phase1/decision_corpus_evidence_index_v10_protocol_v1.json")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fixture_repo(tmp_path: Path) -> tuple[Path, Path, dict]:
    root = tmp_path / "repo"
    root.mkdir()
    protocol_target = root / PROTOCOL_RELATIVE
    protocol_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / PROTOCOL_RELATIVE, protocol_target)
    protocol = json.loads(protocol_target.read_text(encoding="utf-8"))
    paths = {protocol["source_v9"]["path"]}
    for record in protocol["distinct_entries"] + protocol["reconstructions"]:
        paths.update(artifact["path"] for artifact in record["artifacts"])
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root, protocol_target, protocol


def build_candidate(root: Path, protocol_path: Path) -> tuple[dict, Path]:
    candidate = builder.build_index(root, protocol_path)
    output = root / "candidate.json"
    write_json(output, candidate)
    return candidate, output


def test_real_v10_appends_four_distinct_entries_and_one_reconstruction(tmp_path: Path) -> None:
    root, protocol_path, _ = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    receipt = verifier.verify_candidate(root, protocol_path, output)
    assert candidate["protocol"] == "decision_corpus_evidence_index_v10"
    assert candidate["claim_accounting"] == {
        "source_distinct_entry_count": 16,
        "distinct_entries_added": 4,
        "reconstruction_records_added": 1,
        "total_distinct_entry_count": 20,
        "duplicate_claims_counted_as_distinct": 0,
        "source_v9_status_preserved": True,
        "shared_numeric_fields_crosschecked": 19,
    }
    assert len(candidate["entries"]) == 20
    assert len(candidate["reconstructions"]) == 1
    assert receipt["total_distinct_entry_count"] == 20
    assert receipt["duplicate_claims_counted_as_distinct"] == 0
    assert receipt["shared_numeric_fields_crosschecked"] == 19


def test_source_v9_entries_and_provisional_status_are_preserved(tmp_path: Path) -> None:
    root, protocol_path, protocol = fixture_repo(tmp_path)
    candidate, _ = build_candidate(root, protocol_path)
    source = json.loads((root / protocol["source_v9"]["path"]).read_text(encoding="utf-8"))
    assert candidate["entries"][:16] == source["entries"]
    assert candidate["status"] == source["status"]
    assert candidate["claim_accounting"]["source_v9_status_preserved"] is True


def test_support_floor_is_not_a_distinct_entry(tmp_path: Path) -> None:
    root, protocol_path, _ = fixture_repo(tmp_path)
    candidate, _ = build_candidate(root, protocol_path)
    distinct_names = {entry["name"] for entry in candidate["entries"]}
    reconstruction = candidate["reconstructions"][0]
    assert reconstruction["name"] not in distinct_names
    assert reconstruction["reproduction_of"] == "archive_granularity_retention"
    assert reconstruction["shared_component_name"] == "prior_support_depth"
    assert reconstruction["counts_as_distinct_claim_evidence"] is False
    target = next(entry for entry in candidate["entries"] if entry["name"] == reconstruction["reproduction_of"])
    assert reconstruction["shared_component_signature"] == target["claim_components"]["prior_support_depth"]
    assert reconstruction["shared_component_signature_sha256"] == builder.canonical_sha256(
        target["claim_components"]["prior_support_depth"]
    )


def test_duplicate_distinct_claim_signature_fails_closed(tmp_path: Path) -> None:
    _, _, protocol = fixture_repo(tmp_path)
    broken = copy.deepcopy(protocol)
    broken["distinct_entries"][1]["claim_signature"] = copy.deepcopy(
        broken["distinct_entries"][0]["claim_signature"]
    )
    with pytest.raises(builder.BuildError, match="duplicate distinct claim signature"):
        builder.validate_claim_contract(broken, set())


def test_reconstruction_shared_component_mismatch_fails_closed(tmp_path: Path) -> None:
    _, _, protocol = fixture_repo(tmp_path)
    broken = copy.deepcopy(protocol)
    broken["reconstructions"][0]["shared_component_signature"]["competition_count"] = 7
    with pytest.raises(builder.BuildError, match="shared component signature mismatch"):
        builder.validate_claim_contract(broken, set())


def test_reconstruction_cannot_be_counted_as_distinct(tmp_path: Path) -> None:
    _, _, protocol = fixture_repo(tmp_path)
    broken = copy.deepcopy(protocol)
    broken["reconstructions"][0]["counts_as_distinct_claim_evidence"] = True
    with pytest.raises(builder.BuildError, match="reconstruction counted as distinct"):
        builder.validate_claim_contract(broken, set())


def test_source_v9_hash_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path, protocol = fixture_repo(tmp_path)
    source = root / protocol["source_v9"]["path"]
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(builder.BuildError, match="source v9 SHA drift"):
        builder.build_index(root, protocol_path)


def test_artifact_hash_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path, protocol = fixture_repo(tmp_path)
    artifact = root / protocol["distinct_entries"][0]["artifacts"][0]["path"]
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(builder.BuildError, match="artifact SHA drift"):
        builder.build_index(root, protocol_path)


def test_candidate_cannot_promote_status_or_recount_reconstruction(tmp_path: Path) -> None:
    root, protocol_path, _ = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    candidate["status"] = "COMPLETE"
    candidate["claim_accounting"]["duplicate_claims_counted_as_distinct"] = 1
    write_json(output, candidate)
    with pytest.raises(verifier.VerificationError, match="candidate differs"):
        verifier.verify_candidate(root, protocol_path, output)


def test_candidate_cannot_change_a_source_entry(tmp_path: Path) -> None:
    root, protocol_path, _ = fixture_repo(tmp_path)
    candidate, output = build_candidate(root, protocol_path)
    candidate["entries"][0]["supported_claim"] = "drift"
    write_json(output, candidate)
    with pytest.raises(verifier.VerificationError, match="candidate differs"):
        verifier.verify_candidate(root, protocol_path, output)


def test_verifier_does_not_import_builder() -> None:
    source = inspect.getsource(verifier)
    assert "build_decision_corpus_evidence_index_v10" not in source
    assert "from phase1 import build" not in source
