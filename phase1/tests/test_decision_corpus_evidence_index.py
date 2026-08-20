import hashlib
import json
from pathlib import Path

import pytest

from phase1 import verify_decision_corpus_evidence_index as verifier


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_index(tmp_path: Path) -> Path:
    entries = []
    for index, name in enumerate(sorted(verifier.REQUIRED_ENTRIES)):
        artifact = tmp_path / f"artifact-{index}.json"
        artifact.write_text(json.dumps({"status": f"ok-{name}"}) + "\n", encoding="utf-8")
        entries.append(
            {
                "name": name,
                "estimand": f"estimand-{name}",
                "does_not_prove": f"boundary-{name}",
                "artifacts": [
                    {
                        "path": artifact.name,
                        "sha256": digest(artifact),
                        "json_assertions": {"status": f"ok-{name}"},
                    }
                ],
            }
        )
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "protocol": verifier.PROTOCOL,
                "status": verifier.INDEX_STATUS,
                "scope": verifier.REQUIRED_SCOPE,
                "entries": entries,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return index_path


def test_verify_index_binds_five_distinct_attestations(tmp_path: Path):
    receipt = verifier.verify_index(tmp_path, fixture_index(tmp_path))
    assert receipt["status"] == "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_EVIDENCE_INDEX"
    assert receipt["entry_count"] == 5
    assert receipt["artifact_count"] == 5
    assert not receipt["producer_imported"]


def test_verify_index_detects_artifact_tampering(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    (tmp_path / "artifact-0.json").write_text('{"status":"changed"}\n', encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="SHA mismatch"):
        verifier.verify_index(tmp_path, index_path)


def test_verify_index_checks_claim_after_hash_is_updated(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    artifact_path = tmp_path / payload["entries"][0]["artifacts"][0]["path"]
    artifact_path.write_text('{"status":"changed"}\n', encoding="utf-8")
    payload["entries"][0]["artifacts"][0]["sha256"] = digest(artifact_path)
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="JSON assertion mismatch"):
        verifier.verify_index(tmp_path, index_path)


def test_verify_index_rejects_path_escape(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["entries"][0]["artifacts"][0]["path"] = "../outside.json"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="escapes repository root"):
        verifier.verify_index(tmp_path, index_path)


def test_verify_index_rejects_missing_required_entry(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["entries"].pop()
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="entry names"):
        verifier.verify_index(tmp_path, index_path)


def test_verify_index_rejects_duplicate_estimand(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["entries"][1]["estimand"] = payload["entries"][0]["estimand"]
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="estimands must remain distinct"):
        verifier.verify_index(tmp_path, index_path)


def test_verify_index_rejects_duplicate_artifact_path(tmp_path: Path):
    index_path = fixture_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["entries"][1]["artifacts"][0] = payload["entries"][0]["artifacts"][0]
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="artifact path is duplicated"):
        verifier.verify_index(tmp_path, index_path)
