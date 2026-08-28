from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from phase1 import build_historical_relation_integrity_contrast as producer
from phase1 import verify_historical_relation_integrity_contrast as independent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_RELATIVE = Path("phase1/historical_relation_integrity_contrast_v1.json")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    protocol_target = root / PROTOCOL_RELATIVE
    protocol_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / PROTOCOL_RELATIVE, protocol_target)
    protocol = json.loads(protocol_target.read_text(encoding="utf-8"))
    for rule in protocol["inputs"].values():
        source = ROOT / rule["root"]
        target = root / rule["root"]
        shutil.copytree(source, target)
    return root, protocol_target


def built_candidate(root: Path, protocol_path: Path) -> tuple[dict, Path]:
    value = producer.build_contrast(root, protocol_path)
    path = root / "candidate.json"
    write_json(path, value)
    return value, path


def test_real_aggregate_contrast_builds_and_independently_verifies(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, path = built_candidate(root, protocol_path)
    receipt = independent.verify_candidate(root, protocol_path, path)
    assert candidate["diagnostic_receipt"]["canonical_hard_integrity_accepted"] is True
    assert candidate["diagnostic_receipt"]["mixed_family_hard_integrity_rejected"] is True
    assert candidate["diagnostic_receipt"]["deterministic_direct_sibling_quarantine_certificate_passed_all_hard_gates"] is True
    assert candidate["diagnostic_receipt"]["canonical_all_support_gates_accepted"] is False
    assert receipt["all_aggregate_fields_equal"] is True


def test_exact_contrast_and_repair_receipts_are_preserved(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, _ = built_candidate(root, protocol_path)
    contrast = candidate["aggregate_contrasts"]
    assert contrast["canonical_lineage_direct_share"] == {
        "numerator": 8107,
        "denominator": 8107,
        "decimal_17g": "1",
    }
    assert contrast["mixed_non_direct_relation_share"] == {
        "numerator": 6374,
        "denominator": 7644,
        "decimal_17g": "0.83385661957090529",
    }
    assert contrast["mixed_quarantine_share"] == contrast["mixed_non_direct_relation_share"]
    assert contrast["referenced_run_overlap_before_after"] == {"before": 96, "after": 0}
    assert contrast["parent_partition_mismatch_cross_run_localization"]["numerator"] == 743
    assert contrast["parent_partition_mismatch_cross_run_localization"]["denominator"] == 743


def test_candidate_cannot_hide_canonical_support_failure(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, path = built_candidate(root, protocol_path)
    candidate["diagnostic_receipt"]["canonical_all_support_gates_accepted"] = True
    write_json(path, candidate)
    with pytest.raises(independent.VerificationError, match="candidate differs"):
        independent.verify_candidate(root, protocol_path, path)


def test_package_member_hash_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    rule = protocol["inputs"]["mixed_0819"]
    summary = root / rule["root"] / rule["summary"]
    summary.write_text(summary.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(producer.ContrastError, match="manifest member hash drift"):
        producer.build_contrast(root, protocol_path)


def test_manifest_membership_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    package = root / protocol["inputs"]["repaired_0819"]["root"]
    (package / "unregistered.txt").write_text("unexpected\n", encoding="utf-8", newline="\n")
    with pytest.raises(producer.ContrastError, match="manifest membership drift"):
        producer.build_contrast(root, protocol_path)


def test_semantic_taxonomy_count_drift_is_rejected() -> None:
    protocol = json.loads((ROOT / PROTOCOL_RELATIVE).read_text(encoding="utf-8"))
    rule = protocol["inputs"]["mixed_0819"]
    summary = json.loads((ROOT / rule["root"] / rule["summary"]).read_text(encoding="utf-8"))
    summary["semantic_class_counts"]["cross_run_declared_context"]["total"] -= 1
    with pytest.raises(producer.ContrastError, match="mixed count drift"):
        producer.validate_mixed(summary, protocol["required_aggregate_facts"]["mixed"])


def test_repair_non_exhaustiveness_is_rejected() -> None:
    protocol = json.loads((ROOT / PROTOCOL_RELATIVE).read_text(encoding="utf-8"))
    mixed_rule = protocol["inputs"]["mixed_0819"]
    repair_rule = protocol["inputs"]["repaired_0819"]
    mixed = json.loads((ROOT / mixed_rule["root"] / mixed_rule["summary"]).read_text(encoding="utf-8"))
    repair = json.loads((ROOT / repair_rule["root"] / repair_rule["summary"]).read_text(encoding="utf-8"))
    repair["quarantine_counts"]["total"] -= 1
    with pytest.raises(producer.ContrastError, match="repair exhaustiveness"):
        producer.validate_repair(repair, protocol["required_aggregate_facts"]["repair"], mixed)


def test_protocol_and_verifier_preserve_known_result_boundary(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path)
    candidate, path = built_candidate(root, protocol_path)
    receipt = independent.verify_candidate(root, protocol_path, path)
    assert candidate["known_result_status"]["descriptive_synthesis_not_preregistration"] is True
    assert candidate["known_result_status"]["prospective_confirmation_claimed"] is False
    assert receipt["known_result_descriptive_synthesis"] is True
    assert receipt["prospective_values_read"] is False
    assert candidate["comparability_notes"]["gate_schemas_related_but_not_identical"] is True
    assert candidate["comparability_notes"]["contrast_is_a_deterministic_two_family_case_study_not_a_population_estimate"] is True


def test_independent_verifier_does_not_import_producer() -> None:
    source = inspect.getsource(independent)
    assert "build_historical_relation_integrity_contrast" not in source
    assert "from phase1 import build" not in source
