from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import derive_tree_linearization_estimand_sensitivity as producer
from phase1 import verify_tree_linearization_estimand_sensitivity as verifier


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_PROTOCOL = ROOT / "phase1" / "tree_linearization_estimand_sensitivity_corollary_v1.json"
PRODUCER_SOURCE = ROOT / "phase1" / "derive_tree_linearization_estimand_sensitivity.py"
VERIFIER_SOURCE = ROOT / "phase1" / "verify_tree_linearization_estimand_sensitivity.py"
COMMIT = "b" * 40
SNAPSHOT = "a" * 64


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def histogram(values: list[int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return result


def make_fixture(tmp_path: Path, multiplicities: list[int]) -> dict:
    edges = len(multiplicities)
    occurrences = sum(multiplicities)
    duplicates = occurrences - edges
    hist = histogram(multiplicities)
    repo = tmp_path / "repo"
    linear_path = repo / "linear.json"
    compatibility_path = repo / "compatibility.json"
    write_json(
        linear_path,
        {
            "classification": "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING",
            "snapshot_sha256": SNAPSHOT,
            "inventory": {"observed_unique_edges": edges},
            "linearization": {
                "unique_edge_rows": edges,
                "branch_linearized_edge_occurrences": occurrences,
                "duplicate_edge_occurrences": duplicates,
                "edge_multiplicity": {"histogram": hist},
            },
        },
    )
    write_json(
        compatibility_path,
        {
            "classification": "VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY",
            "snapshot_sha256": SNAPSHOT,
            "inventory": {"observed_unique_edges": edges},
            "path_compatibility": {
                "edge_occurrences": occurrences,
                "duplicate_edge_occurrences": duplicates,
                "edge_multiplicity_histogram": hist,
            },
        },
    )
    protocol = json.loads(OFFICIAL_PROTOCOL.read_text(encoding="utf-8"))
    protocol["fixed_inputs"] = {
        "linearization_receipt": {
            "path": "linear.json",
            "sha256": sha(linear_path),
            "required_classification": "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING",
        },
        "compatibility_receipt": {
            "path": "compatibility.json",
            "sha256": sha(compatibility_path),
            "required_classification": "VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY",
        },
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return {
        "repo": repo,
        "protocol": protocol_path,
        "protocol_sha": sha(protocol_path),
        "linear": linear_path,
        "compatibility": compatibility_path,
    }


def build(fixture: dict) -> dict:
    return producer.build(
        fixture["protocol"], fixture["protocol_sha"], fixture["repo"], COMMIT
    )


def test_known_shared_prefix_distribution_has_exact_tv(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path, [2, 1, 1]))
    assert receipt["classification"] == producer.PASS
    assert receipt["edge_measure_shift"]["total_variation"] == {
        "numerator": 1,
        "denominator": 6,
        "decimal_17g": "0.16666666666666666",
    }
    positive = receipt["edge_measure_shift"]["sharp_maximizing_set"]
    assert positive["unique_edges"] == 1
    assert positive["path_occurrences"] == 2
    assert positive["canonical_mass"] == {
        "numerator": 1,
        "denominator": 3,
        "decimal_17g": "0.33333333333333331",
    }
    assert positive["path_minus_canonical_mass"] == receipt["edge_measure_shift"]["total_variation"]
    assert receipt["concentration"]["path_inverse_hhi_descriptive_diversity"] == {
        "numerator": 8,
        "denominator": 3,
        "decimal_17g": "2.6666666666666665",
    }


def test_equal_multiplicity_has_zero_shift_and_full_diversity(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path, [2, 2, 2]))
    assert receipt["edge_measure_shift"]["total_variation"]["numerator"] == 0
    assert receipt["concentration"]["path_to_canonical_diversity_retention"] == {
        "numerator": 1,
        "denominator": 1,
        "decimal_17g": "1",
    }
    assert receipt["concentration"]["maximum_single_edge_mass_inflation"] == {
        "numerator": 1,
        "denominator": 1,
        "decimal_17g": "1",
    }


def test_independent_verifier_rederives_without_import(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [4, 2, 1, 1])
    receipt = build(fixture)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    result = verifier.verify(
        fixture["protocol"],
        fixture["protocol_sha"],
        fixture["repo"],
        receipt_path,
        sha(receipt_path),
        PRODUCER_SOURCE,
        sha(PRODUCER_SOURCE),
        COMMIT,
    )
    assert result["status"] == "INDEPENDENT_ESTIMAND_SENSITIVITY_COROLLARY_PASS"
    assert result["security"]["imports_producer"] is False


def test_verifier_rejects_tampered_exact_value(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [3, 1, 1])
    receipt = build(fixture)
    receipt["edge_measure_shift"]["total_variation"]["numerator"] += 1
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    with pytest.raises(verifier.VerificationError, match="independent derivation"):
        verifier.verify(
            fixture["protocol"], fixture["protocol_sha"], fixture["repo"],
            receipt_path, sha(receipt_path), PRODUCER_SOURCE, sha(PRODUCER_SOURCE), COMMIT,
        )


def test_cross_receipt_histogram_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [2, 1, 1])
    compatibility = json.loads(fixture["compatibility"].read_text(encoding="utf-8"))
    compatibility["path_compatibility"]["edge_multiplicity_histogram"] = {"1": 4}
    write_json(fixture["compatibility"], compatibility)
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["fixed_inputs"]["compatibility_receipt"]["sha256"] = sha(fixture["compatibility"])
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="reconciliation"):
        build(fixture)


def test_histogram_accounting_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [2, 1, 1])
    linear = json.loads(fixture["linear"].read_text(encoding="utf-8"))
    linear["linearization"]["branch_linearized_edge_occurrences"] += 1
    linear["linearization"]["duplicate_edge_occurrences"] += 1
    write_json(fixture["linear"], linear)
    compatibility = json.loads(fixture["compatibility"].read_text(encoding="utf-8"))
    compatibility["path_compatibility"]["edge_occurrences"] += 1
    compatibility["path_compatibility"]["duplicate_edge_occurrences"] += 1
    write_json(fixture["compatibility"], compatibility)
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["fixed_inputs"]["linearization_receipt"]["sha256"] = sha(fixture["linear"])
    protocol["fixed_inputs"]["compatibility_receipt"]["sha256"] = sha(fixture["compatibility"])
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="reconciliation"):
        build(fixture)


def test_protocol_hash_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [2, 1, 1])
    with pytest.raises(producer.CorollaryError, match="protocol SHA"):
        producer.build(fixture["protocol"], "0" * 64, fixture["repo"], COMMIT)


def test_bound_receipt_symlink_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [2, 1, 1])
    linked = fixture["repo"] / "linked_linear.json"
    try:
        linked.symlink_to(fixture["linear"].name)
    except OSError:
        pytest.skip("symlink creation unavailable")
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["fixed_inputs"]["linearization_receipt"]["path"] = linked.name
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="symlink"):
        build(fixture)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8", newline="\n")
    with pytest.raises(verifier.VerificationError, match="symlink"):
        verifier.verify(
            fixture["protocol"], fixture["protocol_sha"], fixture["repo"],
            receipt_path, sha(receipt_path), PRODUCER_SOURCE, sha(PRODUCER_SOURCE), COMMIT,
        )


def test_receipt_is_aggregate_only_and_discloses_posthoc_timing(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path, [2, 1, 1]))
    rendered = json.dumps(receipt, sort_keys=True)
    assert "edge_id" not in rendered
    assert "task_id" not in rendered
    assert "run_id" not in rendered
    assert receipt["design_timing"]["exploratory_values_seen_before_this_declaration"] is True
    assert receipt["claim_boundary"]["actual_predictor_accuracy_shift_observed"] is False
    assert receipt["claim_boundary"]["inverse_hhi_is_statistical_effective_sample_size"] is False


def test_result_is_deterministic(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, [4, 3, 2, 1, 1])
    assert json.dumps(build(fixture), sort_keys=True, separators=(",", ":")) == json.dumps(
        build(fixture), sort_keys=True, separators=(",", ":")
    )


def test_verifier_source_does_not_import_producer() -> None:
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    assert "import derive_tree_linearization_estimand_sensitivity" not in source
    assert "from phase1 import derive_tree_linearization_estimand_sensitivity" not in source
