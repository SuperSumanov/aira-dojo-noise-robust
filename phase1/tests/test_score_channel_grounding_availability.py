from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from phase1 import score_channel_grounding_availability as producer
from phase1 import verify_score_channel_grounding_availability as verifier


def test_missing_channel_is_availability_not_ranking_regret():
    truth = {"a": 0.0, "b": 1.0, "c": 2.0}
    expected = {
        "availability_regret": 1.0,
        "ranking_regret": 0.0,
        "total_regret": 1.0,
    }
    assert producer.channel_decomposition(list(truth), [], {}, truth) == expected
    assert verifier.independent_decomposition(list(truth), [], {}, truth) == {
        "availability": 1.0,
        "ranking": 0.0,
        "total": 1.0,
    }


def test_signal_ties_receive_uniform_expected_truth():
    truth = {"a": 2.0, "b": 0.0, "c": 3.0}
    signal = {"a": 5.0, "b": 5.0}
    expected = producer.channel_decomposition(
        list(truth), ["a", "b"], signal, truth
    )
    independent = verifier.independent_decomposition(
        list(truth), ["a", "b"], signal, truth
    )
    assert expected == {
        "availability_regret": 1.0,
        "ranking_regret": 1.0,
        "total_regret": 2.0,
    }
    assert independent == {"availability": 1.0, "ranking": 1.0, "total": 2.0}


def test_hybrid_gives_external_precedence_and_union_availability():
    cards = ["a", "b", "c"]
    truth = {"a": 0.9, "b": 0.2, "c": 1.0}
    produced = producer.hybrid_decomposition(
        cards,
        ["a", "b"],
        ["c"],
        {"a": 0.0, "b": 1.0},
        {"c": 1.0},
        truth,
    )
    independent = verifier.independent_hybrid(
        cards,
        ["a", "b"],
        ["c"],
        {"a": 0.0, "b": 1.0},
        {"c": 1.0},
        truth,
    )
    assert produced == {
        "availability_regret": 0.0,
        "ranking_regret": 0.8,
        "total_regret": 0.8,
    }
    assert independent == {"availability": 0.0, "ranking": 0.8, "total": 0.8}


def synthetic_inputs():
    selected = [
        {
            "task": "task-a",
            "run_id": "run-1",
            "parent_id": "parent-1",
            "selection_rank_in_run": 1,
            "candidate_card_ids": ["a", "b", "c", "d"],
        },
        {
            "task": "task-b",
            "run_id": "run-2",
            "parent_id": "parent-2",
            "selection_rank_in_run": 1,
            "candidate_card_ids": ["e", "f"],
        },
    ]
    labels = {"a": 0.1, "b": 0.6, "c": 0.9, "d": 0.4, "e": 0.2, "f": 0.8}
    results = {
        "a": {"sub_exists": True, "sub_score": 0.1, "val_how": "keyed", "stdout_val": 0.8},
        "b": {"sub_exists": True, "sub_score": 0.9, "val_how": "none", "stdout_val": None},
        "c": {"sub_exists": False, "sub_score": None, "val_how": "keyed", "stdout_val": 0.2},
        "d": {"sub_exists": False, "sub_score": None, "val_how": "bare", "stdout_val": 0.7},
        "e": {"sub_exists": True, "sub_score": 0.7, "val_how": "keyed", "stdout_val": 0.4},
        "f": {"sub_exists": True, "sub_score": 0.3, "val_how": "keyed", "stdout_val": 0.6},
    }
    return selected, labels, results, {"task-a": 1, "task-b": -1}


def test_joint_states_and_parent_rows_match_independent_reconstruction():
    selected, labels, results, orientation = synthetic_inputs()
    produced_candidates, produced_parents = producer.candidate_and_parent_rows(
        selected, labels, results, orientation
    )
    verified_candidates, verified_parents = verifier.reconstruct_rows(
        selected, labels, results, orientation
    )
    assert produced_candidates == verified_candidates
    assert produced_parents == verified_parents
    first = produced_parents[0]
    assert [first[f"{state}_count"] for state in verifier.STATES] == [1, 1, 1, 1]
    assert first["stdout_available_count"] == 2


def test_full_summary_matches_independent_bootstrap():
    selected, labels, results, orientation = synthetic_inputs()
    candidates, parents = producer.candidate_and_parent_rows(
        selected, labels, results, orientation
    )
    produced = producer.summarize(
        candidates, parents, producer.BOOTSTRAPS, producer.SEED
    )
    independent = verifier.reconstruct_summary(candidates, parents)
    assert produced == independent
    assert produced["counts"]["joint_state_counts"] == {
        "both": 3,
        "external_only": 1,
        "stdout_only": 1,
        "neither": 1,
    }


def test_protocol_hash_mismatch_fails_closed(tmp_path: Path):
    protocol = Path(producer.__file__).with_name(
        "score_channel_grounding_availability_protocol_v1.json"
    )
    expected = hashlib.sha256(protocol.read_bytes()).hexdigest()
    tampered = tmp_path / "protocol.json"
    tampered.write_bytes(protocol.read_bytes() + b"\n")
    with pytest.raises(producer.AvailabilityError, match="SHA mismatch"):
        producer.load_protocol(tampered, expected)
    with pytest.raises(verifier.GroundingVerifyError, match="SHA mismatch"):
        verifier.load_protocol(tampered, expected)


def test_independent_verifier_does_not_import_new_producer():
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "from phase1 import score_channel_grounding_availability" not in source
    assert "import phase1.score_channel_grounding_availability" not in source
