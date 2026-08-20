from __future__ import annotations

import ast
from pathlib import Path

import pytest

from phase1 import traceml_external_structure_audit as producer
from phase1 import verify_traceml_external_structure_audit as verifier


def fixture_rows() -> tuple[list[dict], list[dict]]:
    states: list[dict] = []
    actions: list[dict] = []
    for run_number in range(13):
        run = f"mlev__run_r{run_number:02d}"
        task = f"task-{run_number % 4}"
        for branch, child in ((0, 1), (1, 2)):
            key = f"{run}__branch{branch}"
            common = {"key_id": key, "comp": task, "group": "MLEvolve", "is_agent": True}
            states.extend(
                [
                    {
                        **common,
                        "version_number": 0,
                        "orig_version_number": 0,
                        "depth": 0,
                        "raw_code_path": None,
                    },
                    {
                        **common,
                        "version_number": 1,
                        "orig_version_number": child,
                        "depth": 1,
                        "raw_code_path": None,
                    },
                ]
            )
            actions.append({**common, "v_old": 0, "v_new": 1})
    return states, actions


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("mlev__run_alpha__branch0", ("mlev__run_alpha", 0)),
        ("mlev__run_alpha__branch12", ("mlev__run_alpha", 12)),
        ("mlev__run_a__branchx", None),
        ("other__run_a__branch1", None),
        ("mlev__run_a__branch1_suffix", None),
        (None, None),
    ],
)
def test_two_independent_branch_parsers_agree(key: object, expected: object) -> None:
    assert producer.parse_branch_key(key) == expected
    assert verifier.split_key(key) == expected


def test_valid_direct_tree_mapping_is_reconstructed_identically() -> None:
    states, actions = fixture_rows()
    produced = producer.audit_identity_rows(states, actions)
    rebuilt = verifier.independently_aggregate(states, actions)
    for section in ("identity", "provisional_path_graph", "mapping_gate", "external_replication_gate"):
        assert produced[section] == rebuilt[section]
    assert produced["mapping_gate"]["passed"] is True
    assert produced["identity"]["physical_runs"] == 13
    assert produced["provisional_path_graph"]["canonical_direct_sibling_pairs"] == 13
    assert produced["external_replication_gate"]["passed"] is False
    assert produced["external_replication_gate"]["checks"]["complete_unique_code_join"] is False


def test_skipped_depth_adjacency_fails_closed() -> None:
    states, actions = fixture_rows()
    target = next(
        row
        for row in states
        if row["key_id"] == "mlev__run_r00__branch0" and row["version_number"] == 1
    )
    target["depth"] = 2
    produced = producer.audit_identity_rows(states, actions)
    rebuilt = verifier.independently_aggregate(states, actions)
    assert produced["provisional_path_graph"] == rebuilt["provisional_path_graph"]
    assert produced["provisional_path_graph"]["edge_depth_delta_counts"] == {"1": 25, "2": 1}
    assert produced["mapping_gate"]["checks"]["direct_depth_increment_exactly_one"] is False
    assert produced["mapping_gate"]["passed"] is False
    assert produced["provisional_path_graph"]["canonical_direct_sibling_pairs"] is None


def test_duplicate_action_identity_fails_closed() -> None:
    states, actions = fixture_rows()
    actions.append(dict(actions[0]))
    produced = producer.audit_identity_rows(states, actions)
    rebuilt = verifier.independently_aggregate(states, actions)
    assert produced["identity"] == rebuilt["identity"]
    assert produced["identity"]["duplicate_action_rows"] == 1
    assert produced["mapping_gate"]["checks"]["action_identity_unique"] is False
    assert produced["mapping_gate"]["passed"] is False


def test_cross_branch_node_metadata_conflict_fails_closed() -> None:
    states, actions = fixture_rows()
    target = next(
        row
        for row in states
        if row["key_id"] == "mlev__run_r00__branch1" and row["version_number"] == 0
    )
    target["depth"] = 7
    produced = producer.audit_identity_rows(states, actions)
    rebuilt = verifier.independently_aggregate(states, actions)
    assert produced["identity"] == rebuilt["identity"]
    assert produced["identity"]["original_node_metadata_conflicts"] == 1
    assert produced["mapping_gate"]["checks"][
        "original_node_metadata_consistent_across_branches"
    ] is False


def test_credential_shape_in_identity_is_rejected() -> None:
    states, _ = fixture_rows()
    states[0]["comp"] = "sk-" + "A" * 20
    with pytest.raises(producer.AuditError, match="credential-shaped"):
        producer.scan_identity_values(states, producer.STATE_COLUMNS, "fixture")
    with pytest.raises(verifier.VerificationError, match="credential-shaped"):
        verifier.scan_values(states, verifier.STATE_FIELDS, "fixture")


def test_independent_verifier_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.endswith("traceml_external_structure_audit") for name in imported)
