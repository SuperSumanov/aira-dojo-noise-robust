from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import phase1.verify_balanced_continuation_real_worker as verifier


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_commitment_verifier_does_not_import_worker_or_parse_sealed_receipt() -> None:
    path = Path(verifier.__file__).resolve()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert "phase1.balanced_continuation_real_worker" not in imported
    assert "validate_sealed_label_receipt" not in source
    assert "checked(sealed_path)" not in source
    assert "file_sha256(sealed_path)" in source


def test_process_intent_command_is_hash_bound_and_tamper_fails(tmp_path: Path) -> None:
    assignment = {"rollout_id": "a" * 64}
    command = ["singularity", "exec", "--network", "none"]
    value = {
        "schema_version": verifier.INTENT_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": 0,
        "process_kind": "candidate",
        "process_will_start": True,
        "command": command,
        "command_sha256": hashlib.sha256("\0".join(command).encode()).hexdigest(),
        "created_utc": "2026-08-14T00:00:00Z",
        "retry_count": 0,
    }
    path = tmp_path / "intent.json"
    write_json(path, value)
    assert verifier.validate_intent(path, assignment, 0, "candidate", True) == command
    value["command"].append("unexpected")
    write_json(path, value)
    with pytest.raises(verifier.VerifyError, match="process intent differs"):
        verifier.validate_intent(path, assignment, 0, "candidate", True)
