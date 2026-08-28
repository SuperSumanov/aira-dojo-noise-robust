from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "phase1/results/selective_parent_order_baseline_falsification_887_20260829_cb74a93"
)
PROTOCOL = ROOT / "phase1/selective_parent_order_baseline_falsification_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_publication_manifest_is_complete_and_exact() -> None:
    manifest = PACKAGE / "MANIFEST.sha256"
    rows: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        assert name not in rows
        assert sha256(PACKAGE / name) == digest
        rows[name] = digest
    actual = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256"
    }
    assert set(rows) == actual
    assert len(rows) == 25
    assert sha256(manifest) == "0a667d45022d6b08265268cf78cf2c91cd7ff41b45b0afe7dab0f6f4cfcaf373"


def test_formal_classification_stays_fail_closed() -> None:
    result = read_json(PACKAGE / "formal/producer_a.json")
    summary = read_json(PACKAGE / "formal/formal_summary.json")
    assert result["classification"] == (
        "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL"
    )
    assert summary["classification"] == result["classification"]
    assert result["integrity_gates"][
        "recorded_parent_strictly_precedes_child_manifest_row"
    ] is False
    assert result["primary_baseline_gates"]["nearest_prior_manifest_row"][
        "minimum_comparable_coverage"
    ] is False


def test_valid_step_control_is_strongly_and_broadly_falsified() -> None:
    result = read_json(PACKAGE / "formal/producer_a.json")
    assert result["integrity_gates"][
        "recorded_parent_strictly_precedes_child_step"
    ] is True
    assert result["inventory"]["recorded_parent_not_prior_step"] == 0
    step = result["selected_population_primary_comparisons"]["max_prior_step"]
    assert (step["comparable_rows"], step["content_errors"], step["order_errors"]) == (
        2691,
        7,
        492,
    )
    assert step["comparable_coverage"]["numerator"] == 1
    assert step["comparable_coverage"]["denominator"] == 1
    assert step["paired_correctness"] == {
        "both_correct": 2196,
        "both_wrong": 4,
        "content_only_correct": 488,
        "order_only_correct": 3,
    }
    threat = result["strongest_order_threat"]
    assert threat["baseline"] == "max_prior_step"
    assert threat["task_breadth"]["conditionable_groups"] == 19
    assert threat["run_breadth"]["conditionable_groups"] == 96
    assert threat["task_breadth"]["fraction_net_content_positive"]["numerator"] == 1
    assert threat["run_breadth"]["fraction_net_content_positive"]["numerator"] == 1
    assert all(result["breadth_gates"].values())


def test_manifest_and_timestamp_controls_cannot_rescue() -> None:
    result = read_json(PACKAGE / "formal/producer_a.json")
    assert result["inventory"]["parent_present_edges"] == 10895
    assert result["inventory"]["recorded_parent_not_prior_manifest_row"] == 5449
    manifest = result["selected_population_primary_comparisons"][
        "nearest_prior_manifest_row"
    ]
    assert manifest["comparable_rows"] == 2034
    assert manifest["comparable_coverage"] == {
        "decimal_17g": "0.7558528428093646",
        "denominator": 299,
        "numerator": 226,
    }
    assert result["inventory"]["recorded_parent_equal_generation_time"] == 10895
    generation = result["selected_population_secondary_generation_time"]
    assert generation["comparable_rows"] == 0
    assert generation["comparable_coverage"]["numerator"] == 0


def test_independent_verification_and_postflight_bind_formal() -> None:
    result_path = PACKAGE / "formal/producer_a.json"
    verifier_path = PACKAGE / "formal/verifier_a.json"
    verifier = read_json(verifier_path)
    bindings = read_json(PACKAGE / "source_bindings.json")
    postflight = (PACKAGE / "postflight/postflight.txt").read_text(encoding="utf-8")
    assert sha256(PROTOCOL) == bindings["protocol"]["sha256"]
    assert sha256(result_path) == bindings["formal"]["result_sha256"]
    assert sha256(verifier_path) == bindings["formal"][
        "independent_verification_sha256"
    ]
    assert verifier["all_aggregate_fields_equal"] is True
    assert verifier["producer_imported"] is False
    assert "formal_classification=DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL" in postflight
    assert "valid_step_baseline_descriptive_result_preserved=true" in postflight
    assert "invalid_manifest_order_baseline_not_used_to_rescue=true" in postflight


def test_failure_history_and_scope_are_preserved() -> None:
    bindings = read_json(PACKAGE / "source_bindings.json")
    assert (PACKAGE / "failure_history/r1/FAILED_RC").read_text().strip() == "1"
    assert not (PACKAGE / "failure_history/r1/producer_a.json").exists()
    assert bindings["failure_history"]["scientific_output_created"] is False
    assert bindings["interpretation"]["formal_strong_classification_claimed"] is False
    assert bindings["interpretation"][
        "valid_step_baseline_supports_content_beyond_simple_step_recency"
    ] is True
    assert bindings["scope"]["prospective_values_read"] is False
    assert bindings["scope"]["target522_candidate_or_profile_read"] is False
    assert bindings["scope"]["raw_senior_archives_opened"] is False
    assert bindings["scope"]["row_level_release_created"] is False
    assert bindings["scope"]["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
