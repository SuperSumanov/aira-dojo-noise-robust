import argparse
import hashlib
import json
from pathlib import Path

from phase1.release_content_scan import card_patterns, scan, windows
from phase1.verify_release_content_scan import verify


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_windows_are_fixed_width_and_filter_formatting() -> None:
    value = "abcdefghijklmnopq data-row-12345"
    result = list(windows(value, 16, 6, 10))
    assert result
    assert all(len(pattern) == 16 for pattern in result)
    assert not list(windows("=" * 100, 16, 6, 10))


def test_card_patterns_cover_stdout_literals_and_comments() -> None:
    card = {
        "obs": {"stdout_tail": "stdout-private-record-123456789"},
        "code": (
            "text = 'literal-private-record-987654321'\n"
            "# comment-private-record-246813579\n"
        ),
    }
    fields, parser_ok = card_patterns(card, 16, 6, 10)
    assert parser_ok
    assert fields["stdout_tail"]
    assert fields["code_literal_or_comment"]


def test_aggregate_scan_is_value_free_and_resumable(tmp_path: Path) -> None:
    cards = tmp_path / "cards.jsonl"
    secret_span = "private-record-abc123XYZ789"
    rows = [
        {
            "id": "sensitive-card-id",
            "task": {"name": "covered-task"},
            "code": f"payload = {secret_span!r}\n",
            "obs": {"stdout_tail": "clean-output-only-123456789"},
        },
        {
            "id": "missing-source-card",
            "task": {"name": "missing-task"},
            "code": "x = 1\n",
            "obs": {"stdout_tail": "nothing-sensitive-here-123456"},
        },
    ]
    write_jsonl(cards, rows)
    prepared = tmp_path / "data" / "covered-task" / "prepared"
    prepared.mkdir(parents=True)
    (prepared / "train.csv").write_text(
        f"header\n{secret_span}\n", encoding="utf-8", newline="\n"
    )
    work = tmp_path / "private"
    summary = tmp_path / "summary.json"
    private_manifest = work / "private_manifest.json"
    arguments = argparse.Namespace(
        cards=cards,
        expected_cards_sha256=file_sha256(cards),
        data_root=tmp_path / "data",
        work_dir=work,
        summary=summary,
        private_manifest=private_manifest,
        width=16,
        minimum_distinct=6,
        minimum_nonspace_fraction=0.6,
        task_timeout_s=30,
        matcher="python",
        resume=False,
    )
    result = scan(arguments)
    assert result["status"] == "PARTIAL_COVERAGE_MATCHES_REQUIRE_REVIEW"
    assert result["coverage"]["tasks_scanned"] == 1
    assert result["coverage"]["tasks_unscanned"] == 1
    assert result["totals"]["affected_card_sum_across_tasks"] == 1
    rendered = summary.read_text(encoding="utf-8")
    assert secret_span not in rendered
    assert "sensitive-card-id" not in rendered
    assert str(tmp_path) not in rendered
    private_rendered = private_manifest.read_text(encoding="utf-8")
    assert secret_span not in private_rendered
    assert "sensitive-card-id" not in private_rendered

    verification_path = tmp_path / "verification.json"
    verification = verify(
        argparse.Namespace(
            summary=summary,
            private_manifest=private_manifest,
            cards=cards,
            data_root=tmp_path / "data",
            work_dir=work,
            output=verification_path,
        )
    )
    assert verification["status"] == "PASS"
    assert verification["matched_patterns"] > 0
    assert secret_span not in verification_path.read_text(encoding="utf-8")

    arguments.resume = True
    repeated = scan(arguments)
    assert repeated == result


def test_formal_runner_creates_log_before_process_substitution() -> None:
    runner = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_release_content_scan_v11_20260902.sh"
    ).read_text(encoding="utf-8")
    create = runner.index(': >"${log}"')
    chmod = runner.index('chmod 0600 "${log}"')
    redirect = runner.index('exec > >(tee -a "${log}")')
    assert create < chmod < redirect


def test_formal_runner_pins_pytest_capable_interpreter_for_every_python_step() -> None:
    runner = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_release_content_scan_v11_20260902.sh"
    ).read_text(encoding="utf-8")
    declaration = (
        "readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python"
    )
    capability_gate = '"${python_bin}" -c \'import pytest\''
    assert declaration in runner
    assert capability_gate in runner
    assert runner.index(declaration) < runner.index(capability_gate)
    assert runner.count('"${python_bin}" -m pytest') == 2
    assert runner.count('"${python_bin}" -m phase1.release_content_scan') == 2
    assert runner.count('"${python_bin}" -m phase1.verify_release_content_scan') == 2
    assert '\npython -m ' not in runner
    assert '\npython - ' not in runner
