import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def card(card_id: str, step: int, run_id: str | None) -> dict:
    row = {
        "id": card_id,
        "task": {"name": "same-task"},
        "lineage": {"step": step, "parent_id": None},
    }
    if run_id is not None:
        row["run_id"] = run_id
        row["provenance"] = {"run_id_source": "source-journal-path:pre-flattening"}
    return row


def prepare(tmp_path: Path, rows: list[dict]) -> None:
    phase1 = tmp_path / "phase1"
    phase1.mkdir()
    (phase1 / "corpus_manifest.txt").write_text("new.jsonl\n", encoding="utf-8")
    (phase1 / "new.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_explicit_run_ids_prevent_silent_adjacent_run_merge(tmp_path: Path) -> None:
    prepare(
        tmp_path,
        [
            card("a1", 1, "new.jsonl:0"),
            card("a2", 2, "new.jsonl:0"),
            # The old heuristic merged this run because its first labeled step is 6 > 2.
            card("b6", 6, "new.jsonl:1"),
            card("b7", 7, "new.jsonl:1"),
        ],
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "phase1" / "run_segment.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    mapping = json.loads((tmp_path / "phase1" / "card_run_map.json").read_text())
    assert set(mapping.values()) == {"new.jsonl:0", "new.jsonl:1"}
    assert "explicit cards=4; heuristic cards=0" in result.stdout


def test_mixed_explicit_and_heuristic_batch_fails_closed(tmp_path: Path) -> None:
    prepare(
        tmp_path,
        [card("a1", 1, "new.jsonl:0"), card("b2", 2, None)],
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "phase1" / "run_segment.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "mixed explicit/implicit run ids" in result.stderr


def test_add_run_id_preserves_validated_explicit_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    output = tmp_path / "output.jsonl"
    mapping = tmp_path / "map.json"
    row = {
        "id": "a1",
        "task": {"name": "spaceship-titanic", "type": "tabular"},
        "lineage": {"step": 1, "parent_id": None},
        "label": {"graded": 0.8, "y_norm": 0.7, "medal_bucket": "silver"},
        "run_id": "new.jsonl:0",
        "provenance": {"run_id_source": "source-journal-path:pre-flattening"},
    }
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    mapping.write_text(json.dumps({"a1": "new.jsonl:0"}), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "phase1.add_run_id",
            str(source),
            str(output),
            str(mapping),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    restored = json.loads(output.read_text(encoding="utf-8"))
    assert restored["run_id"] == "new.jsonl:0"
    assert restored["provenance"]["run_id_source"] == "source-journal-path:pre-flattening"
    assert "explicit run ids preserved 1" in result.stdout
