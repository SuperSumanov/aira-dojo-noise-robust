from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import derive_tree_linearization_depth_order_corollary as producer
from phase1 import verify_tree_linearization_depth_order_corollary as verifier


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_PROTOCOL = ROOT / "phase1" / "tree_linearization_depth_order_corollary_v1.json"
PRODUCER_SOURCE = ROOT / "phase1" / "derive_tree_linearization_depth_order_corollary.py"
VERIFIER_SOURCE = ROOT / "phase1" / "verify_tree_linearization_depth_order_corollary.py"
COMMIT = "c" * 40
SNAPSHOT = "d" * 64


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def nearest_rank(counts: dict[int, int], numerator: int, denominator: int) -> int:
    target = (sum(counts.values()) * numerator + denominator - 1) // denominator
    cumulative = 0
    for depth in sorted(counts):
        cumulative += counts[depth]
        if cumulative >= target:
            return depth
    raise AssertionError("unreachable")


def disclosure(canonical: dict[int, int], path_frequency: dict[int, int]) -> dict:
    depths = sorted(canonical)
    canonical_total, path_total = sum(canonical.values()), sum(path_frequency.values())
    canonical_sum = sum(depth * canonical[depth] for depth in depths)
    path_sum = sum(depth * path_frequency[depth] for depth in depths)
    canonical_mean = Fraction(canonical_sum, canonical_total)
    path_mean = Fraction(path_sum, path_total)
    differences = [
        Fraction(path_frequency[depth], path_total) - Fraction(canonical[depth], canonical_total)
        for depth in depths
    ]
    tv = sum((abs(value) for value in differences), Fraction()) / 2
    cumulative = Fraction()
    cdf = []
    for value in differences:
        cumulative += value
        cdf.append(cumulative)
    maximum = max(cdf)
    signs = [1 if value > 0 else -1 for value in differences if value]
    return {
        "canonical_depth_support": [depths[0], depths[-1]],
        "canonical_depth_count": canonical_total,
        "path_frequency_depth_count": path_total,
        "canonical_depth_sum": canonical_sum,
        "path_frequency_depth_sum": path_sum,
        "canonical_mean_depth": str(canonical_mean),
        "path_frequency_mean_depth": str(path_mean),
        "path_minus_canonical_mean_depth": str(path_mean - canonical_mean),
        "path_to_canonical_mean_depth_ratio": str(path_mean / canonical_mean),
        "depth_total_variation": str(tv),
        "maximum_cdf_gap": str(maximum),
        "maximum_cdf_gap_depth": depths[cdf.index(maximum)],
        "shallow_first_order_stochastic_dominance": all(value >= 0 for value in cdf),
        "nonzero_pmf_sign_changes": sum(left != right for left, right in zip(signs, signs[1:])),
        "canonical_nearest_rank_median_depth": nearest_rank(canonical, 1, 2),
        "path_frequency_nearest_rank_median_depth": nearest_rank(path_frequency, 1, 2),
        "canonical_nearest_rank_p90_depth": nearest_rank(canonical, 9, 10),
        "path_frequency_nearest_rank_p90_depth": nearest_rank(path_frequency, 9, 10),
    }


def make_fixture(
    tmp_path: Path,
    canonical: dict[int, int] | None = None,
    path_frequency: dict[int, int] | None = None,
) -> dict:
    canonical = canonical or {1: 1, 2: 1, 3: 2}
    path_frequency = path_frequency or {1: 3, 2: 1, 3: 2}
    assert set(canonical) == set(path_frequency)
    seen = disclosure(canonical, path_frequency)
    repo = tmp_path / "repo"
    source = repo / "source.json"
    write_json(
        source,
        {
            "protocol": "prospective-tree-linearization-weight-audit-receipt-v1",
            "status": "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE",
            "classification": "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING",
            "snapshot_sha256": SNAPSHOT,
            "inventory": {"observed_unique_edges": seen["canonical_depth_count"]},
            "linearization": {
                "unique_edge_rows": seen["canonical_depth_count"],
                "branch_linearized_edge_occurrences": seen["path_frequency_depth_count"],
            },
            "weighting": {
                "depth_diagnostic": {
                    "unique_edge_counts": {str(key): value for key, value in canonical.items()},
                    "branch_linearized_counts": {
                        str(key): value for key, value in path_frequency.items()
                    },
                    "total_variation": float(Fraction(seen["depth_total_variation"])),
                    "non_rescuing": True,
                }
            },
            "pre_registered_gate": {"all_hard_gates_passed": True},
        },
    )
    protocol = json.loads(OFFICIAL_PROTOCOL.read_text(encoding="utf-8"))
    protocol["fixed_input"] = {
        "path": "source.json",
        "sha256": sha(source),
        "required_protocol": "prospective-tree-linearization-weight-audit-receipt-v1",
        "required_status": "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE",
        "required_classification": "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING",
        "required_snapshot_sha256": SNAPSHOT,
        "required_observed_unique_edges": seen["canonical_depth_count"],
        "required_path_edge_occurrences": seen["path_frequency_depth_count"],
    }
    protocol["values_seen_before_declaration"] = seen
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return {
        "repo": repo,
        "source": source,
        "protocol": protocol_path,
        "protocol_sha": sha(protocol_path),
    }


def build(fixture: dict) -> dict:
    return producer.build(
        fixture["protocol"], fixture["protocol_sha"], fixture["repo"], COMMIT
    )


def test_official_aggregate_matches_disclosed_exact_corollary() -> None:
    receipt = producer.build(OFFICIAL_PROTOCOL, sha(OFFICIAL_PROTOCOL), ROOT, COMMIT)
    assert receipt["classification"] == producer.PASS
    profile = receipt["exact_order_profile"]
    assert profile["path_minus_canonical_mean_depth"] == {
        "numerator": -324480056,
        "denominator": 284435765,
        "decimal_17g": "-1.1407850064143656",
    }
    assert profile["depth_total_variation"] == {
        "numerator": 27231696,
        "denominator": 284435765,
        "decimal_17g": "0.095739352609191045",
    }
    assert profile["maximum_cdf_gap"] == profile["depth_total_variation"]
    assert profile["maximum_cdf_gap_depth"] == 5
    assert receipt["deterministic_properties"] == {
        "shallow_first_order_stochastic_dominance": True,
        "strictly_negative_mean_depth_shift": True,
        "exactly_one_nonzero_pmf_sign_change": True,
        "maximum_cdf_gap_equals_depth_total_variation": True,
    }


def test_synthetic_shallow_single_crossing_is_verified(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path))
    assert receipt["classification"] == producer.PASS
    assert receipt["exact_order_profile"]["depth_total_variation"] == {
        "numerator": 1,
        "denominator": 4,
        "decimal_17g": "0.25",
    }
    assert receipt["exact_order_profile"]["maximum_cdf_gap_depth"] == 1


def test_valid_non_fosd_profile_is_not_verified(tmp_path: Path) -> None:
    receipt = build(
        make_fixture(
            tmp_path,
            canonical={1: 1, 2: 1, 3: 2},
            path_frequency={1: 1, 2: 1, 3: 4},
        )
    )
    assert receipt["classification"] == producer.NOT_VERIFIED
    assert receipt["deterministic_properties"]["shallow_first_order_stochastic_dominance"] is False
    assert receipt["deterministic_properties"]["strictly_negative_mean_depth_shift"] is False


def test_independent_verifier_reconstructs_without_import(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
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
    assert result["status"] == "INDEPENDENT_TREE_LINEARIZATION_DEPTH_ORDER_PASS"
    assert result["security"]["imports_producer"] is False


def test_verifier_rejects_tampered_receipt(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    receipt = build(fixture)
    receipt["exact_order_profile"]["maximum_cdf_gap_depth"] += 1
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    with pytest.raises(verifier.VerificationError, match="independent derivation"):
        verifier.verify(
            fixture["protocol"], fixture["protocol_sha"], fixture["repo"],
            receipt_path, sha(receipt_path), PRODUCER_SOURCE, sha(PRODUCER_SOURCE), COMMIT,
        )


def test_source_hash_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    source = json.loads(fixture["source"].read_text(encoding="utf-8"))
    source["status"] = "DRIFTED"
    write_json(fixture["source"], source)
    with pytest.raises(producer.CorollaryError, match="SHA mismatch"):
        build(fixture)


def test_noncontiguous_depth_support_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(
        tmp_path,
        canonical={1: 1, 3: 2},
        path_frequency={1: 2, 3: 2},
    )
    with pytest.raises(producer.CorollaryError, match="not contiguous"):
        build(fixture)


def test_seen_value_disclosure_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["values_seen_before_declaration"]["maximum_cdf_gap_depth"] += 1
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="seen-values"):
        build(fixture)


def test_upstream_float_tv_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    source = json.loads(fixture["source"].read_text(encoding="utf-8"))
    source["weighting"]["depth_diagnostic"]["total_variation"] += 0.01
    write_json(fixture["source"], source)
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["fixed_input"]["sha256"] = sha(fixture["source"])
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="does not roundtrip"):
        build(fixture)


def test_result_is_byte_deterministic(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    first = json.dumps(build(fixture), sort_keys=True, separators=(",", ":"))
    second = json.dumps(build(fixture), sort_keys=True, separators=(",", ":"))
    assert first == second


def test_protocol_hash_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    with pytest.raises(producer.CorollaryError, match="protocol SHA"):
        producer.build(fixture["protocol"], "0" * 64, fixture["repo"], COMMIT)


def test_bound_source_symlink_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    linked = fixture["repo"] / "linked.json"
    try:
        linked.symlink_to(fixture["source"].name)
    except OSError:
        pytest.skip("symlink creation unavailable")
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["fixed_input"]["path"] = linked.name
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    with pytest.raises(producer.CorollaryError, match="symlink"):
        build(fixture)


def test_receipt_discloses_posthoc_and_contains_no_identity_fields(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path))
    rendered = json.dumps(receipt, sort_keys=True)
    assert "card_id" not in rendered
    assert "run_id" not in rendered
    assert "task_id" not in rendered
    assert receipt["design_timing"]["exploratory_cdf_order_and_crossing_seen_before_declaration"] is True
    assert receipt["claim_boundary"]["preregistered_or_confirmatory_discovery"] is False
    assert receipt["security"]["prospective_label_grade_outcome_prediction_values_read"] is False


def test_verifier_source_does_not_import_producer() -> None:
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    assert "import derive_tree_linearization_depth_order_corollary" not in source
    assert "from phase1 import derive_tree_linearization_depth_order_corollary" not in source
