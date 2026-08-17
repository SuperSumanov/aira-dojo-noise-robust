from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from phase1 import source_opportunity_failure_taxonomy as module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def make_fixture(tmp_path: Path, diagnostics: list[tuple[int, str]]) -> tuple[Path, Path]:
    root = tmp_path / "journals"
    journal = root / "run-a" / "checkpoint" / "journal.jsonl"
    nodes = [
        {
            "step": 0,
            "id": "root",
            "parents": [],
            "exit_code": 0,
            "metric_info": {"competition_id": "task-a"},
        }
    ]
    for index, (exit_code, diagnostic) in enumerate(diagnostics, 1):
        nodes.append(
            {
                "step": index,
                "id": f"c{index}",
                "parents": [0],
                "exit_code": exit_code,
                "term_out": diagnostic,
                "metric_info": {"competition_id": "task-a"},
            }
        )
    write_jsonl(journal, nodes)
    journal_sha = hashlib.sha256(journal.read_bytes()).hexdigest()
    status = tmp_path / "status.jsonl"
    write_jsonl(
        status,
        [
            {
                "child_id": f"task-a__c{index}",
                "role": "train",
                "status": "UNIQUE_NODE_RECOVERED",
                "category": "EXECUTION_ERROR",
                "parent_match": True,
                "source_journal_sha256": journal_sha,
            }
            for index in range(1, len(diagnostics) + 1)
        ],
    )
    return root, status


def args(root: Path, status: Path, output: Path, count: int) -> argparse.Namespace:
    return argparse.Namespace(
        status_per_child=str(status),
        expect_status_sha256=hashlib.sha256(status.read_bytes()).hexdigest(),
        expect_targets=count,
        root=[f"synthetic={root}"],
        source_commit="a" * 40,
        output=str(output),
    )


def test_fixed_taxonomy_and_no_raw_text_output(tmp_path: Path) -> None:
    diagnostics = [
        (1, "submission.csv missing required column"),
        (1, "RuntimeError: CUDA out of memory"),
        (1, "TimeoutError: timed out"),
        (1, "ModuleNotFoundError: no module named x"),
        (1, "SyntaxError: invalid syntax"),
        (1, "FileNotFoundError: no such file or directory"),
        (1, "AttributeError: object has no attribute x"),
        (1, "ValueError: shape mismatch"),
        (137, ""),
        (1, "Traceback: RuntimeError: opaque"),
        (1, "ordinary nonempty output"),
        (1, ""),
    ]
    root, status = make_fixture(tmp_path, diagnostics)
    output = tmp_path / "out"
    assert module.run(args(root, status, output, len(diagnostics))) == 0
    rows = [json.loads(line) for line in (output / "per_child.jsonl").read_text().splitlines()]
    by_child = {row["child_id"]: row["category"] for row in rows}
    assert by_child == {
        "task-a__c1": "ARTIFACT_OUTPUT_CONTRACT",
        "task-a__c2": "RESOURCE_OOM",
        "task-a__c3": "RESOURCE_TIMEOUT",
        "task-a__c4": "DEPENDENCY_IMPORT",
        "task-a__c5": "PYTHON_SYNTAX",
        "task-a__c6": "FILESYSTEM_INPUT_PATH",
        "task-a__c7": "LIBRARY_API_ATTRIBUTE",
        "task-a__c8": "DATA_SCHEMA_SHAPE_TYPE",
        "task-a__c9": "PROCESS_SIGNAL",
        "task-a__c10": "OTHER_TRACEBACK",
        "task-a__c11": "NON_TRACEBACK_TEXT",
        "task-a__c12": "NO_DIAGNOSTIC_TEXT",
    }
    rendered = "".join(path.read_text() for path in output.iterdir())
    assert "submission.csv missing required column" not in rendered


def test_credential_is_skipped_before_parse(tmp_path: Path) -> None:
    root, status = make_fixture(tmp_path, [(1, "not json")])
    journal = root / "run-a" / "checkpoint" / "journal.jsonl"
    journal.write_bytes(journal.read_bytes() + b"sk-" + b"A" * 20)
    new_sha = hashlib.sha256(journal.read_bytes()).hexdigest()
    row = json.loads(status.read_text())
    row["source_journal_sha256"] = new_sha
    write_jsonl(status, [row])
    output = tmp_path / "out"

    assert module.run(args(root, status, output, 1)) == 0
    result = json.loads((output / "per_child.jsonl").read_text())
    assert result["category"] == "CREDENTIAL_JOURNAL_SKIPPED"
    assert result["diagnostic_text_sha256"] is None


def test_outputs_are_byte_identical_across_output_roots(tmp_path: Path) -> None:
    root, status = make_fixture(tmp_path, [(1, "ValueError: shape mismatch")])
    first, second = tmp_path / "first", tmp_path / "second"
    assert module.run(args(root, status, first, 1)) == 0
    assert module.run(args(root, status, second, 1)) == 0
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_module_cli_entrypoint(tmp_path: Path) -> None:
    root, status = make_fixture(tmp_path, [(1, "ValueError: shape mismatch")])
    output = tmp_path / "cli-out"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "phase1.source_opportunity_failure_taxonomy",
            "--status-per-child",
            str(status),
            "--expect-status-sha256",
            hashlib.sha256(status.read_bytes()).hexdigest(),
            "--expect-targets",
            "1",
            "--root",
            f"synthetic={root}",
            "--source-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert (output / "command.txt").read_text().startswith(
        "python -m phase1.source_opportunity_failure_taxonomy "
    )
