import hashlib
import json

import pytest

from phase1 import audit_source_choice_step_structure as audit


def candidate(stem: str, step: int, depth: int = 2, operator: str = "Improve"):
    return {
        "candidate_id_sha256": stem * 64,
        "code": f"print('{stem}')",
        "code_sha256": (stem.upper() if stem.isalpha() else "a") * 64,
        "depth": depth,
        "operator": operator,
        "step": step,
    }


def row(stem: str, steps: list[int]):
    items = [candidate(str(index + 1), step) for index, step in enumerate(steps)]
    return {
        "schema_version": "source-choice-decision-group-v2",
        "group_id": stem * 64,
        "task": "task",
        "source_size": len(items),
        "candidates": items,
        "winner_candidate_sha256": items[-1]["candidate_id_sha256"],
    }


def write_rows(path, rows):
    payload = "".join(json.dumps(value, sort_keys=True) + "\n" for value in rows).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def test_structure_counts_do_not_depend_on_winner(tmp_path):
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"
    rows_a = [row("a", [1, 2]), row("b", [3, 5, 6])]
    rows_b = json.loads(json.dumps(rows_a))
    rows_b[0]["winner_candidate_sha256"] = rows_b[0]["candidates"][0]["candidate_id_sha256"]
    sha_a = write_rows(path_a, rows_a)
    sha_b = write_rows(path_b, rows_b)

    result_a = audit.audit(
        path_a, expected_sha256=sha_a, expected_groups=2, expected_candidates=5
    )
    result_b = audit.audit(
        path_b, expected_sha256=sha_b, expected_groups=2, expected_candidates=5
    )
    result_a.pop("input_sha256")
    result_b.pop("input_sha256")
    assert result_a == result_b
    assert result_a["groups_all_candidate_steps_unique"] == 2
    assert result_a["groups_candidate_steps_contiguous"] == 1
    assert result_a["groups_candidate_steps_noncontiguous"] == 1
    assert result_a["winner_field_used_in_statistics"] is False


def test_schema_and_hash_fail_closed(tmp_path):
    path = tmp_path / "rows.jsonl"
    rows = [row("a", [1, 2])]
    sha = write_rows(path, rows)
    with pytest.raises(audit.StepStructureError, match="input SHA mismatch"):
        audit.audit(path, expected_sha256="0" * 64, expected_groups=1, expected_candidates=2)

    rows[0]["role"] = "train"
    sha = write_rows(path, rows)
    with pytest.raises(audit.StepStructureError, match="unexpected group schema"):
        audit.audit(path, expected_sha256=sha, expected_groups=1, expected_candidates=2)
