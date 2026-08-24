import hashlib
import json
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).parents[1] / "audit_transition_task_balance.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(pair_id: str, task: str, run_id: str, eligible: bool) -> dict:
    return {
        "pair_id": pair_id,
        "task": task,
        "run_id": run_id,
        "parent": f"p-{pair_id}",
        "left": f"l-{pair_id}",
        "right": f"r-{pair_id}",
        "generation_started_at_utc": "2026-08-24T00:00:00Z",
        "temporal_stratum": "strict_post_activation_primary",
        "parent_source_present": True,
        "left_code_sha256": "a" * 64,
        "right_code_sha256": "b" * 64,
        "parent_code_sha256": "c" * 64,
        "training_endpoint_id_overlap": False,
        "training_run_id_overlap": False,
        "training_code_sha_overlap": False,
        "source_novel": True,
        "finite_all_arms": eligible,
        "nontie_all_arms": eligible,
        "strict_effect_eligible": eligible,
        "child_code": 0.1,
        "transition_only": 0.2,
        "child_plus_transition": 0.3,
    }


def _fixture(tmp_path: Path, *, extra_field: bool = False) -> tuple[Path, Path]:
    rows = [
        _row("1", "z-task", "run-1", True),
        _row("2", "a-task", "run-2", True),
        _row("3", "b-task", "run-3", True),
        _row("4", "z-task", "run-4", True),
        _row("5", "a-task", "run-5", True),
        _row("6", "ignored-task", "run-6", False),
    ]
    if extra_field:
        rows[0]["unexpected"] = "blocked"
    pairs = tmp_path / "pairs.jsonl"
    pairs.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "outputs": {"pairs_sha256": _sha256(pairs)},
                "support": {
                    "inventory": {
                        "all_pairs": 6,
                        "eligible_pairs": 5,
                        "eligible_runs": 5,
                        "eligible_tasks": 3,
                    }
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return pairs, summary


def _run(pairs: Path, summary: Path, output: Path, pairs_sha: str | None = None):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pairs",
            str(pairs),
            "--expect-pairs-sha256",
            pairs_sha or _sha256(pairs),
            "--summary",
            str(summary),
            "--expect-summary-sha256",
            _sha256(summary),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_counts_tasks_and_uses_deterministic_tie_break(tmp_path: Path) -> None:
    pairs, summary = _fixture(tmp_path)
    output = tmp_path / "output"

    completed = _run(pairs, summary, output)

    assert completed.returncode == 0, completed.stderr
    result = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert result["eligible_pairs"] == 5
    assert result["eligible_runs"] == 5
    assert result["eligible_tasks"] == 3
    assert result["dominant_task"] == "a-task"
    assert result["dominant_count"] == 2
    assert result["dominant_share"] == 0.4
    assert result["non_dominant_pairs_needed_if_dominant_count_stays_fixed"] == 3
    assert result["outcomes_read"] is False
    assert result["effect_metrics_computed"] == []
    assert (output / "task_counts.tsv").read_text(encoding="utf-8") == (
        "a-task\t2\nb-task\t1\nz-task\t2\n"
    )


def test_fails_closed_on_input_hash_mismatch(tmp_path: Path) -> None:
    pairs, summary = _fixture(tmp_path)
    output = tmp_path / "output"

    completed = _run(pairs, summary, output, pairs_sha="0" * 64)

    assert completed.returncode != 0
    assert "pairs SHA mismatch" in completed.stderr
    assert not output.exists()


def test_fails_closed_on_schema_extension(tmp_path: Path) -> None:
    pairs, summary = _fixture(tmp_path, extra_field=True)
    output = tmp_path / "output"

    completed = _run(pairs, summary, output)

    assert completed.returncode != 0
    assert "schema mismatch at line 1" in completed.stderr
    assert not output.exists()
