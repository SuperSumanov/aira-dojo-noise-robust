from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from phase1.audit_public_artifact_contract import audit


def _manifest(path: Path) -> None:
    path.write_text("task\ttask_type\ntask-a\tnlp\ntask-b\ttabular\n", encoding="utf-8")


def _public(root: Path, task: str) -> Path:
    path = root / task / "prepared" / "public"
    path.mkdir(parents=True)
    (path / "description.md").write_text(f"description for {task}", encoding="utf-8")
    return path


def test_audit_plain_and_zip_without_emitting_values(tmp_path: Path) -> None:
    data = tmp_path / "data"
    manifest = tmp_path / "tasks.tsv"
    _manifest(manifest)
    public_a = _public(data, "task-a")
    with (public_a / "sample_submission.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows([["id", "score"], ["private-row-id", "0.5"], ["other", ""]])
    public_b = _public(data, "task-b")
    with zipfile.ZipFile(public_b / "x_sample_submission_2.csv.zip", "w") as archive:
        archive.writestr("sample.csv", "id,a,b\n1,true,7\n2,false,8\n")

    result = audit(data, manifest)
    rendered = json.dumps(result)

    assert result["summary"]["contracts_found"] == 2
    assert result["tasks"][0]["row_count"] == 2
    assert result["tasks"][0]["observed_types"] == [["string"], ["empty", "float"]]
    assert result["tasks"][1]["archive_member"] == "sample.csv"
    assert "private-row-id" not in rendered
    assert result["input_contract"]["official_labels_or_outcomes_read"] is False


def test_private_sample_submission_is_never_discovered(tmp_path: Path) -> None:
    data = tmp_path / "data"
    manifest = tmp_path / "tasks.tsv"
    _manifest(manifest)
    (data / "task-a" / "prepared" / "private").mkdir(parents=True)
    (data / "task-a" / "prepared" / "private" / "sample_submission.csv").write_text(
        "id,score\n1,0.5\n", encoding="utf-8"
    )

    result = audit(data, manifest)

    assert result["tasks"][0]["contract_present"] is False
    assert result["input_contract"]["private_paths_allowed"] is False
