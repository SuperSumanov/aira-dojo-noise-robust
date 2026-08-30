from __future__ import annotations

import itertools
import math
import zlib

import numpy as np

from phase1.vertex_cost_contrast_design import (
    ContrastDesignError,
    ParentGroup,
    code_hash_feature,
    contrast_rank_count,
    rank_normalized_pair_weight,
    raw_pair_count,
    select_vertex_cost_contrasts,
)


def groups_and_features() -> tuple[list[ParentGroup], dict[str, np.ndarray]]:
    groups: list[ParentGroup] = []
    features: dict[str, np.ndarray] = {}
    vectors = [
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0, 0.0]),
        np.array([0.0, -1.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, -1.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 1.0]),
        np.array([0.0, 0.0, 0.0, -1.0]),
    ]
    cursor = 0
    for index in range(4):
        endpoints = tuple(f"e{index}-{offset}" for offset in range(2))
        groups.append(ParentGroup(f"p{index}", f"t{index}", f"r{index}", endpoints))
        for endpoint in endpoints:
            features[endpoint] = vectors[cursor]
            cursor += 1
    return groups, features


def test_clique_rows_are_quadratic_but_contrast_rank_is_linear() -> None:
    for size in range(2, 12):
        selected = {"p": [f"e{i}" for i in range(size)]}
        assert raw_pair_count(selected) == math.comb(size, 2)
        assert contrast_rank_count(selected) == size - 1
        assert math.isclose(
            raw_pair_count(selected) * rank_normalized_pair_weight(size),
            size - 1,
        )


def test_code_hash_feature_is_deterministic_bounded_and_unicode_safe() -> None:
    code = "变量 = 1\nprint(变量)\n" * 50
    first = code_hash_feature(code, dimension=64, max_chars=80)
    second = code_hash_feature(code, dimension=64, max_chars=80)
    suffix_changed = code_hash_feature(code + "ignored suffix", dimension=64, max_chars=80)
    assert np.array_equal(first, second)
    assert np.array_equal(first, suffix_changed)
    assert first.shape == (64,)
    assert np.isfinite(first).all()
    assert math.isclose(float(np.linalg.norm(first)), 1.0)


def test_unicode_character_grams_do_not_split_multibyte_codepoints() -> None:
    feature = code_hash_feature("甲乙丙", dimension=32, ngram_min=3, ngram_max=3)
    expected = np.zeros(32)
    gram = "甲乙丙".encode("utf-8")
    bucket = (zlib.crc32(gram, 0x13579BDF) & 0xFFFFFFFF) % 32
    sign = 1 if (zlib.crc32(gram, 0x2468ACE0) & 0xFFFFFFFF) & 1 else -1
    expected[bucket] = sign
    assert np.array_equal(feature, expected)


def test_design_is_deterministic_exact_nested_and_respects_caps() -> None:
    groups, features = groups_and_features()
    first = select_vertex_cost_contrasts(
        groups,
        features,
        budget=8,
        task_share_denominator=4,
        run_share_denominator=4,
    )
    second = select_vertex_cost_contrasts(
        groups,
        features,
        budget=8,
        task_share_denominator=4,
        run_share_denominator=4,
    )
    assert first.selected_endpoints == second.selected_endpoints
    assert len(first.selected_endpoints) == len(set(first.selected_endpoints)) == 8
    assert [row["step"] for row in first.steps] == list(range(1, 9))
    assert first.task_cap == first.run_cap == 2
    assert max(row["maximum_task_endpoints"] for row in first.steps) <= 2
    assert max(row["maximum_run_endpoints"] for row in first.steps) <= 2
    assert first.steps[-1]["contrast_rank_count"] == 4


def test_incremental_logdet_matches_direct_dense_matrix() -> None:
    groups, features = groups_and_features()
    result = select_vertex_cost_contrasts(
        groups,
        features,
        budget=8,
        task_share_denominator=4,
        run_share_denominator=4,
    )
    matrix = np.eye(4)
    for vector in result.contrast_vectors:
        matrix += np.outer(vector, vector)
    sign, direct = np.linalg.slogdet(matrix)
    assert sign > 0
    assert math.isclose(result.information_logdet_gain, direct, rel_tol=1e-10)
    assert result.numerical_feature_rank == 4


def test_open_action_uses_two_endpoints_then_adds_one_rank() -> None:
    groups, features = groups_and_features()
    result = select_vertex_cost_contrasts(
        groups,
        features,
        budget=2,
        task_share_denominator=5,
        run_share_denominator=10,
    )
    assert [row["action_kind"] for row in result.steps] == [
        "open_parent_pair",
        "open_parent_pair",
    ]
    assert [row["contrast_rank_count"] for row in result.steps] == [0, 1]
    assert [row["raw_induced_pair_count"] for row in result.steps] == [0, 1]


def test_orthogonal_parent_contrasts_accumulate_feature_rank() -> None:
    groups, features = groups_and_features()
    result = select_vertex_cost_contrasts(
        groups,
        features,
        budget=6,
        task_share_denominator=3,
        run_share_denominator=3,
    )
    assert result.numerical_feature_rank == 3
    assert result.steps[-1]["contrast_rank_count"] == 3
    assert result.steps[-1]["raw_induced_pair_count"] == 3


def test_caps_fail_closed_when_population_cannot_fill_exact_budget() -> None:
    endpoints = tuple(f"e{i}" for i in range(5))
    group = ParentGroup("p", "only-task", "only-run", endpoints)
    features = {endpoint: np.eye(5)[index] for index, endpoint in enumerate(endpoints)}
    try:
        select_vertex_cost_contrasts(
            [group],
            features,
            budget=5,
            task_share_denominator=5,
            run_share_denominator=10,
        )
    except ContrastDesignError as error:
        assert "exact budget infeasible" in str(error)
    else:
        raise AssertionError("infeasible caps must fail closed")


def test_input_rejects_endpoint_shared_across_parent_groups() -> None:
    groups = [
        ParentGroup("p1", "t1", "r1", ("a", "b")),
        ParentGroup("p2", "t2", "r2", ("a", "c")),
    ]
    features = {name: np.eye(3)[index] for index, name in enumerate(("a", "b", "c"))}
    try:
        select_vertex_cost_contrasts(groups, features, budget=2)
    except ContrastDesignError as error:
        assert "multiple parents" in str(error)
    else:
        raise AssertionError("shared endpoint must fail closed")


def test_array_like_features_are_copied_to_numeric_vectors() -> None:
    groups = [ParentGroup("p", "t", "r", ("a", "b"))]
    result = select_vertex_cost_contrasts(groups, {"a": [1.0, 0.0], "b": [0.0, 1.0]}, budget=2)
    assert result.steps[-1]["contrast_rank_count"] == 1


def test_pair_weight_is_orientation_agnostic() -> None:
    size = 6
    pairs = list(itertools.combinations(range(size), 2))
    weighted_orientations = len(pairs) * 2 * (rank_normalized_pair_weight(size) / 2.0)
    assert math.isclose(weighted_orientations, size - 1)
