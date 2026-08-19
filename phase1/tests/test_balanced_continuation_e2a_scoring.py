from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from phase1.balanced_continuation_e2a_scoring import analysis_utility, score_submission
from phase1.balanced_continuation_real_worker import evaluator_module_names
from phase1 import balanced_continuation_e2a_dsearch_eval as dsearch
from phase1 import balanced_continuation_e2a_dval_sealer as dval
from phase1.balanced_continuation_e2a_scoring import evaluator_bundle_sha256


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def scored(
    tmp_path: Path, task: str, label_header: list[str], labels: list[list[object]],
    submission_header: list[str], predictions: list[list[object]],
) -> float:
    private = tmp_path / f"{task}.csv"
    public = tmp_path / f"{task}.sample.csv"
    artifact = tmp_path / f"{task}.submission.csv"
    write_csv(private, label_header, labels)
    write_csv(public, submission_header, predictions)
    write_csv(artifact, submission_header, predictions)
    result = score_submission(artifact, private, public, task)
    assert result["submission_valid"] is True
    return result["score"]


def test_six_metric_reference_values(tmp_path: Path) -> None:
    assert scored(
        tmp_path, "spaceship-titanic", ["PassengerId", "Transported"],
        [["a", "True"], ["b", "False"]], ["PassengerId", "Transported"],
        [["a", "True"], ["b", "True"]],
    ) == 0.5
    assert scored(
        tmp_path, "tabular-playground-series-may-2022", ["id", "target"],
        [["a", 0], ["b", 0], ["c", 1], ["d", 1]], ["id", "target"],
        [["a", 0.1], ["b", 0.4], ["c", 0.35], ["d", 0.8]],
    ) == 0.75
    loss = scored(
        tmp_path, "spooky-author-identification", ["id", "author"],
        [["a", "EAP"], ["b", "HPL"]], ["id", "EAP", "HPL", "MWS"],
        [["a", 0.8, 0.1, 0.1], ["b", 0.2, 0.7, 0.1]],
    )
    assert loss == pytest.approx(-(math.log(0.8) + math.log(0.7)) / 2)
    assert scored(
        tmp_path, "us-patent-phrase-to-phrase-matching", ["id", "score"],
        [["a", 0.0], ["b", 0.5], ["c", 1.0]], ["id", "score"],
        [["a", 0.0], ["b", 0.5], ["c", 1.0]],
    ) == pytest.approx(1.0)
    assert scored(
        tmp_path, "nomad2018-predict-transparent-conductors",
        ["id", "formation_energy_ev_natom", "bandgap_energy_ev"],
        [["a", 0.0, 1.0], ["b", 3.0, 8.0]],
        ["id", "formation_energy_ev_natom", "bandgap_energy_ev"],
        [["a", 0.0, 1.0], ["b", 3.0, 8.0]],
    ) == pytest.approx(0.0)
    assert scored(
        tmp_path, "learning-agency-lab-automated-essay-scoring-2",
        ["essay_id", "score"], [["a", 1], ["b", 2], ["c", 5], ["d", 6]],
        ["essay_id", "score"], [["a", 1], ["b", 2], ["c", 5], ["d", 6]],
    ) == pytest.approx(1.0)


def test_task_utility_maps_to_unit_interval() -> None:
    assert analysis_utility("spaceship-titanic", 0.7, True) == 0.7
    assert analysis_utility("spooky-author-identification", math.log(2), True) == pytest.approx(0.5)
    assert analysis_utility("us-patent-phrase-to-phrase-matching", -0.5, True) == 0.25
    assert analysis_utility("nomad2018-predict-transparent-conductors", 1.0, True) == 0.5
    assert analysis_utility("learning-agency-lab-automated-essay-scoring-2", 0.0, True) == 0.5
    assert analysis_utility("spaceship-titanic", None, False) == 0.0


def test_invalid_prediction_and_mixed_evaluator_hashes_fail(tmp_path: Path) -> None:
    private = tmp_path / "labels.csv"
    public = tmp_path / "sample.csv"
    artifact = tmp_path / "submission.csv"
    write_csv(private, ["id", "author"], [["a", "EAP"]])
    write_csv(public, ["id", "EAP", "HPL", "MWS"], [["a", 0.3, 0.3, 0.4]])
    write_csv(artifact, ["id", "EAP", "HPL", "MWS"], [["a", -0.1, 0.5, 0.6]])
    result = score_submission(artifact, private, public, "spooky-author-identification")
    assert result["submission_valid"] is False
    assert result["failure_reason"] == "submission_prediction_invalid"

    contract = {
        "search_evaluator_executable_sha256": evaluator_bundle_sha256(Path(dsearch.__file__)),
        "sealed_label_evaluator_executable_sha256": evaluator_bundle_sha256(Path(dval.__file__)),
    }
    assert evaluator_module_names(contract) == (
        "phase1.balanced_continuation_e2a_dsearch_eval",
        "phase1.balanced_continuation_e2a_dval_sealer",
    )
    contract["sealed_label_evaluator_executable_sha256"] = "f" * 64
    with pytest.raises(Exception, match="mixed evaluator-profile"):
        evaluator_module_names(contract)
