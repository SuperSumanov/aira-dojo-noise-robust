from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase1" / "results"
SNAPSHOT = "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"

PACKAGES = {
    "within": RESULTS / "tree_linearization_within_stratum_887_20260828_2363b68",
    "depth": RESULTS / "tree_linearization_depth_order_887_20260828_333a3b6",
    "path": RESULTS / "tree_path_split_prefix_leakage_887_20260828_aec6356",
}

SOURCES = {
    "within": {
        "protocol": ROOT / "phase1" / "tree_linearization_within_stratum_decomposition_v1.json",
        "producer": ROOT / "phase1" / "decompose_tree_linearization_within_strata.py",
        "verifier": ROOT / "phase1" / "verify_tree_linearization_within_stratum_decomposition.py",
        "tests": ROOT / "phase1" / "tests" / "test_tree_linearization_within_stratum_decomposition.py",
    },
    "depth": {
        "protocol": ROOT / "phase1" / "tree_linearization_depth_order_corollary_v1.json",
        "producer": ROOT / "phase1" / "derive_tree_linearization_depth_order_corollary.py",
        "verifier": ROOT / "phase1" / "verify_tree_linearization_depth_order_corollary.py",
        "tests": ROOT / "phase1" / "tests" / "test_tree_linearization_depth_order_corollary.py",
    },
    "path": {
        "protocol": ROOT / "phase1" / "tree_path_split_prefix_leakage_v1.json",
        "producer": ROOT / "phase1" / "audit_tree_path_split_prefix_leakage.py",
        "verifier": ROOT / "phase1" / "verify_tree_path_split_prefix_leakage.py",
        "tests": ROOT / "phase1" / "tests" / "test_tree_path_split_prefix_leakage.py",
    },
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def verify_manifest(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    rows: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        assert relative not in rows
        rows[relative] = expected
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(rows) == actual
    for relative, expected in rows.items():
        assert digest(directory / relative) == expected
    return digest(manifest)


def test_source_and_manifest_bindings_are_exact() -> None:
    expected_commits = {
        "within": "2363b687ea503ced5945208766bb25f1baaeffed",
        "depth": "333a3b66ca5399dcf87e586be1339423917d1264",
        "path": "aec63564cb4a347a3bb6c61b38ae30850d1d755f",
    }
    for name, package in PACKAGES.items():
        bindings = load(package / "source_bindings.json")
        assert bindings["snapshot_sha256"] == SNAPSHOT
        assert bindings["formal_source_commit"] == expected_commits[name]
        for role, source in SOURCES[name].items():
            assert digest(source) == bindings["source_sha256"][role]
        assert verify_manifest(package / "formal") == bindings["formal_sha256"][
            "formal_manifest"
        ]


def test_formal_receipts_and_independent_verifiers_are_bound() -> None:
    expected = {
        "within": (
            "WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL",
            "INDEPENDENT_WITHIN_STRATUM_DECOMPOSITION_PASS",
        ),
        "depth": (
            "VERIFIED_SHALLOW_DEPTH_STOCHASTIC_ORDER_COROLLARY",
            "INDEPENDENT_TREE_LINEARIZATION_DEPTH_ORDER_PASS",
        ),
        "path": (
            "RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK",
            "INDEPENDENT_TREE_PATH_SPLIT_PREFIX_LEAKAGE_PASS",
        ),
    }
    for name, package in PACKAGES.items():
        formal = package / "formal"
        bindings = load(package / "source_bindings.json")
        receipt = load(formal / "final_receipt.json")
        verification = load(formal / "independent_verification.json")
        assert receipt["classification"] == expected[name][0] == bindings["status"]
        assert verification["classification"] == receipt["classification"]
        assert verification["status"] == expected[name][1]
        assert verification["receipt_sha256"] == digest(formal / "final_receipt.json")
        assert digest(formal / "final_receipt.json") == bindings["formal_sha256"][
            "final_receipt"
        ]
        assert digest(formal / "independent_verification.json") == bindings["formal_sha256"][
            "independent_verification"
        ]
        assert digest(formal / "formal_summary.json") == bindings["formal_sha256"][
            "formal_summary"
        ]
        assert (formal / "producer_a.json").read_bytes() == (
            formal / "producer_b.json"
        ).read_bytes()
        assert (formal / "verifier_a.json").read_bytes() == (
            formal / "verifier_b.json"
        ).read_bytes()


def test_within_stratum_failure_is_not_rescued_post_hoc() -> None:
    package = PACKAGES["within"]
    receipt = load(package / "formal" / "final_receipt.json")
    bindings = load(package / "source_bindings.json")
    gate = receipt["pre_registered_gate"]
    assert gate["all_hard_gates_passed"] is False
    assert gate["axis_strength"] == {"physical_run": True, "task": True}
    assert gate["hard_integrity_and_support"][
        "recomputed_task_marginal_tv_roundtrips_to_disclosed_17g"
    ] is False
    assert bindings["interpretation"]["same_snapshot_rescue_permitted"] is False
    assert bindings["interpretation"][
        "future_confirmation_requires_unseen_snapshot_and_exact_rational_binding"
    ] is True

    task = receipt["partitions"]["task"]
    run = receipt["partitions"]["physical_run"]
    assert task["group_marginal_total_variation"] == {
        "decimal_17g": "0.16033760381715709",
        "denominator": 284435765,
        "numerator": 45605749,
    }
    assert task["canonical_marginal_standardized_within_total_variation"][
        "decimal_17g"
    ] == "0.34286096272939481"
    assert task["anonymous_conditionable_group_distribution"][
        "fraction_at_or_above_reference"
    ] == {"decimal_17g": "0.94117647058823528", "denominator": 17, "numerator": 16}
    assert task["maximum_anonymous_canonical_contribution_share"][
        "decimal_17g"
    ] == "0.35387441357728333"
    assert run["canonical_marginal_standardized_within_total_variation"][
        "decimal_17g"
    ] == "0.30840042995574296"
    assert run["anonymous_conditionable_group_distribution"][
        "fraction_at_or_above_reference"
    ] == {"decimal_17g": "0.82027649769585254", "denominator": 217, "numerator": 178}
    assert run["maximum_anonymous_canonical_contribution_share"][
        "decimal_17g"
    ] == "0.10868797144906397"


def test_depth_order_corollary_is_exact_and_post_hoc() -> None:
    receipt = load(PACKAGES["depth"] / "formal" / "final_receipt.json")
    profile = receipt["exact_order_profile"]
    assert receipt["deterministic_properties"] == {
        "exactly_one_nonzero_pmf_sign_change": True,
        "maximum_cdf_gap_equals_depth_total_variation": True,
        "shallow_first_order_stochastic_dominance": True,
        "strictly_negative_mean_depth_shift": True,
    }
    assert profile["canonical_mean_depth"] == {
        "decimal_17g": "8.1884350619550261",
        "denominator": 10895,
        "numerator": 89213,
    }
    assert profile["path_frequency_mean_depth"] == {
        "decimal_17g": "7.0476500555406592",
        "denominator": 26107,
        "numerator": 183993,
    }
    assert profile["path_minus_canonical_mean_depth"] == {
        "decimal_17g": "-1.1407850064143656",
        "denominator": 284435765,
        "numerator": -324480056,
    }
    assert profile["maximum_cdf_gap_depth"] == 5
    assert profile["maximum_cdf_gap"] == profile["depth_total_variation"] == {
        "decimal_17g": "0.095739352609191045",
        "denominator": 284435765,
        "numerator": 27231696,
    }
    assert (
        profile["canonical_nearest_rank_median_depth"],
        profile["canonical_nearest_rank_p90_depth"],
        profile["path_frequency_nearest_rank_median_depth"],
        profile["path_frequency_nearest_rank_p90_depth"],
    ) == (7, 15, 6, 13)
    assert receipt["design_timing"]["confirmatory_or_preregistered_discovery_claim_allowed"] is False
    assert receipt["claim_boundary"]["logged_depth_is_semantic_importance_or_difficulty"] is False


def test_path_split_prefix_risk_is_run_broad_only() -> None:
    receipt = load(PACKAGES["path"] / "formal" / "final_receipt.json")
    assert receipt["inventory"]["root_to_leaf_path_records"] == 3599
    assert receipt["global"]["split_sizes"] == {
        "root_to_leaf_path_records": 3599,
        "test": 360,
        "train": 2879,
        "validation": 360,
    }
    assert receipt["global"]["expected_train_test_cross_split_canonical_edges"][
        "decimal_17g"
    ] == "1291.4019805907681"
    assert receipt["global"]["unique_test_edge_contamination_ratio_of_expectations"][
        "decimal_17g"
    ] == "0.63841797380705656"
    assert receipt["global"]["test_occurrence_contamination_ratio_of_expectations"][
        "decimal_17g"
    ] == "0.71072159960645032"

    task = receipt["anonymous_profiles"]["task"]
    run = receipt["anonymous_profiles"]["physical_run"]
    assert receipt["pre_registered_gate"]["axis_strength"] == {
        "physical_run": True,
        "task": False,
    }
    assert run["anonymous_group_distribution"]["groups_at_or_above_reference"] == 339
    assert run["maximum_anonymous_expected_contaminated_occurrence_contribution_share"][
        "decimal_17g"
    ] == "0.14093310549689442"
    assert task["anonymous_group_distribution"]["groups_at_or_above_reference"] == 31
    assert task["maximum_anonymous_expected_contaminated_occurrence_contribution_share"][
        "decimal_17g"
    ] == "0.45161151698862051"
    assert receipt["grouped_split_controls"][
        "fragment_grouped_expected_exact_canonical_edge_crossing"
    ] == {"decimal_17g": "0", "denominator": 1, "numerator": 0}
    assert receipt["grouped_split_controls"][
        "physical_run_grouped_expected_exact_canonical_edge_crossing"
    ] == {"decimal_17g": "0", "denominator": 1, "numerator": 0}
    assert receipt["claim_boundary"]["actual_model_performance_inflation_measured"] is False


def test_security_and_formal_test_counts_are_preserved() -> None:
    counts = {
        "within": ("49 passed", "1355 passed, 47 warnings"),
        "depth": ("63 passed", "1369 passed, 47 warnings"),
        "path": ("90 passed", "1391 passed, 47 warnings"),
    }
    for name, package in PACKAGES.items():
        formal = package / "formal"
        receipt = load(formal / "final_receipt.json")
        assert (formal / "forbidden_open_hits.txt").read_bytes() == b""
        assert (formal / "credential_filename_hits.txt").read_text().strip() == "0"
        assert (formal / "credential_content_file_hits.txt").read_text().strip() == "0"
        assert (formal / "focused_tests.stderr").read_bytes() == b""
        assert (formal / "full_tests.stderr").read_bytes() == b""
        assert receipt["security"][
            "prospective_label_grade_outcome_prediction_values_read"
        ] is False
        assert receipt["security"]["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
        assert counts[name][0] in (formal / "focused_tests.txt").read_text(encoding="utf-8")
        assert counts[name][1] in (formal / "full_tests.txt").read_text(encoding="utf-8")
