from __future__ import annotations

from phase1.audit_failure_risk_pair_support import build_summary, card_parent


def card(card_id: str, parent: str | None, run: str, task: str, code: str) -> dict:
    return {
        "id": card_id,
        "task": {"name": task},
        "code": code,
        "run_id": run,
        "lineage": {"parent_id": parent} if parent else {},
    }


def test_card_parent_is_explicit_only() -> None:
    assert card_parent(card("x", "p", "r", "t", "code")) == "p"
    assert card_parent(card("x", None, "r", "t", "code")) is None


def test_parent_matched_selection_is_deterministic_and_excludes_identical_code() -> None:
    cards = {
        "task__p": card("task__p", None, "run-a", "task", "parent"),
        "task__b": card("task__b", "task__p", "run-a", "task", "different success"),
        "task__a": card("task__a", "task__p", "run-a", "task", "failed code"),
    }
    failures = {
        "task__f": {
            "child_id": "task__f",
            "parent_id": "task__p",
            "source_journal_sha256": "1" * 64,
            "failure_category": "RESOURCE_TIMEOUT",
        }
    }
    metadata = {
        "task__f": {
            "code_present": True,
            "code_bytes": len("failed code"),
            "code_sha256": __import__("hashlib").sha256(b"failed code").hexdigest(),
        }
    }
    summary = build_summary(
        cards,
        failures,
        metadata,
        {"credential_target_journal_shas": 0},
        set(),
    )
    assert summary["eligible_parent_matched_pairs"] == 1
    assert summary["failure_categories"] == {"RESOURCE_TIMEOUT": 1}
    assert summary["frozen_run_overlap"] == 0


def test_frozen_run_and_identical_code_fail_closed() -> None:
    cards = {
        "task__p1": card("task__p1", None, "run-frozen", "task", "parent"),
        "task__s1": card("task__s1", "task__p1", "run-frozen", "task", "success"),
        "task__p2": card("task__p2", None, "run-clean", "task", "parent"),
        "task__s2": card("task__s2", "task__p2", "run-clean", "task", "same"),
    }
    failures = {
        "task__f1": {
            "child_id": "task__f1", "parent_id": "task__p1",
            "source_journal_sha256": "1" * 64, "failure_category": "RESOURCE_TIMEOUT",
        },
        "task__f2": {
            "child_id": "task__f2", "parent_id": "task__p2",
            "source_journal_sha256": "2" * 64, "failure_category": "RESOURCE_TIMEOUT",
        },
    }
    metadata = {
        "task__f1": {
            "code_present": True, "code_bytes": 6,
            "code_sha256": __import__("hashlib").sha256(b"failed").hexdigest(),
        },
        "task__f2": {
            "code_present": True, "code_bytes": 4,
            "code_sha256": __import__("hashlib").sha256(b"same").hexdigest(),
        },
    }
    summary = build_summary(
        cards, failures, metadata, {"credential_target_journal_shas": 0}, {"run-frozen"}
    )
    assert summary["eligible_parent_matched_pairs"] == 0
    assert summary["frozen_run_overlap"] == 1
    assert summary["identical_code_only_parents"] == 1
