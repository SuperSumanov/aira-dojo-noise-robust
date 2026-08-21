from __future__ import annotations

import csv
from pathlib import Path

import pytest

from phase1 import meta_kaggle_exact_parent_s0b as producer
from phase1 import verify_meta_kaggle_exact_parent_s0b as verifier


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(header)
        writer.writerows(rows)


def make_fixture(
    root: Path,
    *,
    parents: int = 500,
    competitions: int = 20,
    mismatched_children: int = 0,
    duplicate_unrelated_version: bool = False,
) -> tuple[Path, Path, Path, Path]:
    kernels = root / "Kernels.csv"
    versions = root / "KernelVersions.csv"
    links = root / "KernelVersionCompetitionSources.csv"
    competition_table = root / "Competitions.csv"

    kernel_rows: list[list[object]] = []
    version_rows: list[list[object]] = []
    link_rows: list[list[object]] = []
    child_index = 0
    for parent_offset in range(parents):
        parent_version = 1 + parent_offset
        competition = 1 + (parent_offset % competitions)
        version_rows.append(
            [parent_version, 50_000 + parent_offset, "", "01/01/2020 00:00:00", 1]
        )
        link_rows.append([parent_version, competition])
        for branch in range(2):
            child_index += 1
            child_kernel = 100_000 + child_index
            child_version = 1_000_000 + child_index
            kernel_rows.append([child_kernel, parent_version, child_version])
            recorded_parent = parent_version
            if child_index <= mismatched_children:
                recorded_parent = 1 + ((parent_offset + 1) % parents)
            version_rows.append(
                [child_version, child_kernel, recorded_parent, "01/02/2020 00:00:00", "1.0"]
            )
            link_rows.append([child_version, competition])

    if duplicate_unrelated_version:
        version_rows.extend(
            [
                [9_999_999, 8_000_001, "", "01/01/2020 00:00:00", 1],
                [9_999_999, 8_000_002, "", "01/01/2020 00:00:00", 1],
            ]
        )

    write_csv(kernels, list(producer.KERNEL_COLUMNS), kernel_rows)
    write_csv(versions, list(producer.VERSION_COLUMNS), version_rows)
    write_csv(links, ["Id", *producer.LINK_COLUMNS], [[index, *row] for index, row in enumerate(link_rows, 1)])
    write_csv(
        competition_table,
        list(producer.COMPETITION_COLUMNS),
        [[identifier, "01/01/2021 00:00:00", "True", "true"] for identifier in range(1, competitions + 1)],
    )
    return kernels, versions, links, competition_table


def run_producer(root: Path, **fixture_options: object) -> tuple[dict, list[dict]]:
    paths = make_fixture(root, **fixture_options)
    return producer.reconstruct(*paths, root / "scratch-producer")


def test_formal_scale_valid_fixture_passes_and_independent_rebuild_matches(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path)
    summary, pairs = producer.reconstruct(*paths, tmp_path / "scratch-producer")
    independent, independent_pairs = verifier.rebuild(*paths, tmp_path / "scratch-verifier")

    assert summary == independent
    assert pairs == independent_pairs
    assert summary["status"] == "EXACT_PARENT_STRUCTURE_SUPPORT_FEASIBLE"
    assert summary["inventory"]["canonical_pairs"] == 500
    assert summary["inventory"]["completed_competitions_in_pairs"] == 20
    assert summary["inventory"]["direct_parent_field_agreement_rate"] == 1.0
    assert len({pair["parent_version_id"] for pair in pairs}) == len(pairs)


def test_more_than_five_percent_direct_parent_disagreement_fails_identity(tmp_path: Path) -> None:
    summary, _ = run_producer(tmp_path, mismatched_children=51)
    assert summary["inventory"]["direct_parent_field_agreement_rate"] == pytest.approx(0.949)
    assert not summary["identity_criteria"]["direct_parent_field_agreement_rate_ge_0_95"]
    assert summary["status"] == "IDENTITY_UNAVAILABLE"


def test_exactly_five_percent_direct_parent_disagreement_passes_rate_gate(tmp_path: Path) -> None:
    summary, _ = run_producer(tmp_path, mismatched_children=50)
    assert summary["inventory"]["direct_parent_field_agreement_rate"] == pytest.approx(0.95)
    assert summary["identity_criteria"]["direct_parent_field_agreement_rate_ge_0_95"]


def test_global_duplicate_version_id_fails_even_when_unrelated_to_forks(tmp_path: Path) -> None:
    summary, _ = run_producer(tmp_path, duplicate_unrelated_version=True)
    assert summary["inventory"]["kernel_versions"]["duplicate_id"] == 1
    assert not summary["identity_criteria"]["kernel_version_ids_globally_unique"]
    assert summary["status"] == "IDENTITY_UNAVAILABLE"


def test_fixed_hash_pair_uses_only_two_children_and_is_order_stable() -> None:
    children = [
        {"child_kernel_id": kernel, "child_first_version_id": kernel + 1000, "competition_id": 7}
        for kernel in (11, 12, 13, 14)
    ]
    first = producer.deterministic_pair(5, children)
    second = producer.deterministic_pair(5, list(reversed(children)))
    assert first == second
    assert len({first["child_a_kernel_id"], first["child_b_kernel_id"]}) == 2


def test_modules_have_no_outcome_table_or_score_field_input() -> None:
    forbidden = (
        "Submissions" + ".csv",
        "Public" + "Score",
        "Private" + "Score",
        "Source" + "KernelVersionId",
    )
    for module in (producer, verifier):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert all(token not in source for token in forbidden)


def test_missing_required_header_fails_closed(tmp_path: Path) -> None:
    paths = list(make_fixture(tmp_path, parents=1, competitions=1))
    write_csv(paths[0], ["Id", "FirstKernelVersionId"], [[1, 2]])
    with pytest.raises(producer.AuditError, match="missing columns"):
        producer.reconstruct(*paths, tmp_path / "scratch")
