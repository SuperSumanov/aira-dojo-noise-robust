from __future__ import annotations

import hashlib
import json

import pytest

from phase1.build_failure_risk_pair_registry import jsonl_bytes
from phase1.verify_failure_risk_pair_registry import VerificationError, read_registry


def registry_row() -> dict[str, str]:
    digest = hashlib.sha256(b"failure").hexdigest()
    success_digest = hashlib.sha256(b"success").hexdigest()
    return {
        "failure_category": "RESOURCE_TIMEOUT",
        "failure_child_id": "failure-child",
        "failure_code_sha256": digest,
        "failure_source_journal_sha256": hashlib.sha256(b"journal").hexdigest(),
        "parent_id": "parent",
        "physical_run_id": "run",
        "role": "train_only",
        "success_child_id": "success-child",
        "success_code_sha256": success_digest,
        "task": "task",
    }


def test_jsonl_is_canonical_and_contains_no_raw_code() -> None:
    blob = jsonl_bytes([registry_row()])
    assert blob.endswith(b"\n")
    assert b"failure_code\"" not in blob
    assert b"success_code\"" not in blob
    assert json.loads(blob) == registry_row()


def test_reader_rejects_any_extra_code_field(tmp_path) -> None:
    row = registry_row()
    row["failure_code"] = "raw secret-bearing code"
    path = tmp_path / "registry.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(VerificationError, match="schema mismatch"):
        read_registry(path)
