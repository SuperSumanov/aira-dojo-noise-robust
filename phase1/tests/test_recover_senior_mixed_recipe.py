from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import phase1.recover_senior_mixed_recipe as recovery


def pair(
    better: str,
    worse: str,
    split: str = "train",
    source: str = "value",
) -> dict[str, object]:
    return {
        "better": better,
        "worse": worse,
        "intask_split": split,
        "src": source,
        "task": "task-a",
    }


def test_frozen_candidate_grid_has_exactly_sixty_six_recipes() -> None:
    specs = list(recovery.candidate_specs())
    assert len(specs) == 66
    assert len({(order, tuple(sorted(counts.items()))) for order, counts in specs}) == 66
    expected = [
        (order, counts)
        for order, counts in specs
        if order == recovery.EXPECTED_ORDER and counts == recovery.EXPECTED_COUNTS
    ]
    assert len(expected) == 1


def test_weight_allocation_matches_recovered_counts() -> None:
    assert recovery.allocate_counts(15_000, [8, 1, 1]) == [12_000, 1_500, 1_500]


def test_simulation_deduplicates_and_reserves_complete_test() -> None:
    datasets = {
        "local": [pair("l", "x"), pair("t", "u")],
        "decision": [
            pair("d", "x", source="decision"),
            pair("t", "u", split="test", source="decision"),
            pair("t", "u", split="test", source="decision"),
        ],
        "global": [pair("g", "x")],
    }
    output, trace = recovery.simulate_builder(
        datasets,
        ("local", "decision", "global"),
        {"local": 2, "decision": 1, "global": 1},
        seed=7,
        use_test_dataset="decision",
    )
    keys = [(row["better"], row["worse"]) for row in output]
    assert keys[-1] == ("t", "u")
    assert len(keys) == len(set(keys)) == 4
    assert trace == {
        "requested_sampled": 4,
        "unique_sampled": 3,
        "retained_test": 1,
    }


def test_exact_match_search_differentiates_candidate_recipes() -> None:
    datasets = {
        "local": [pair("l1", "x"), pair("l2", "x")],
        "decision": [
            pair("d1", "x", source="decision"),
            pair("d2", "x", source="decision"),
            pair("t", "x", split="test", source="decision"),
        ],
        "global": [pair("g1", "x"), pair("g2", "x")],
    }
    order = ("local", "decision", "global")
    true_counts = {"local": 1, "decision": 1, "global": 1}
    false_counts = {"local": 2, "decision": 1, "global": 0}
    target, _ = recovery.simulate_builder(
        datasets, order, true_counts, seed=7, use_test_dataset="decision"
    )
    matches, searched = recovery.find_exact_matches(
        datasets,
        target,
        [(order, true_counts), (order, false_counts)],
        seed=7,
        use_test_dataset="decision",
    )
    assert searched == 2
    assert len(matches) == 1
    assert matches[0][1] == true_counts


def test_builder_serialization_is_utf8_compact_lf() -> None:
    payload = recovery.builder_bytes([pair("更好", "worse")])
    assert payload.endswith(b"\n")
    assert b"\r\n" not in payload
    assert b'": "' not in payload
    assert "更好".encode("utf-8") in payload


def test_locked_jsonl_requires_exact_hash_and_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "target.jsonl"
    raw = (json.dumps(pair("a", "b"), separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(
        recovery.LOCKED_FILES,
        "target",
        {"filename": "target.jsonl", "sha256": digest, "bytes": len(raw)},
    )
    rows, metadata, locked_raw = recovery.checked_locked_jsonl(
        path, "target", digest, len(raw)
    )
    assert rows == [pair("a", "b")]
    assert metadata["sha256"] == digest
    assert locked_raw == raw
    with pytest.raises(recovery.RecoveryError, match="SHA-256 mismatch"):
        recovery.checked_locked_jsonl(path, "target", "0" * 64, len(raw))
    with pytest.raises(recovery.RecoveryError, match="byte-size mismatch"):
        recovery.checked_locked_jsonl(path, "target", digest, len(raw) + 1)


def test_credential_shaped_bytes_are_refused_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    synthetic_credential = b"sk-" + b"abcdefghijklmnop"
    path.write_bytes(b'{"token":"' + synthetic_credential + b'"}\n')
    with pytest.raises(recovery.RecoveryError, match="credential-shaped bytes refused"):
        recovery.checked_regular_file(path, "synthetic")


def test_builder_source_lock_is_line_ending_invariant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lf = b"line one\nline two\n"
    monkeypatch.setattr(recovery, "BUILDER_LF_SHA256", hashlib.sha256(lf).hexdigest())
    monkeypatch.setattr(recovery, "BUILDER_GIT_BLOB_SHA1", recovery.git_blob_sha1(lf))
    metadata = []
    for name, payload in (("lf.py", lf), ("crlf.py", lf.replace(b"\n", b"\r\n"))):
        path = tmp_path / name
        path.write_bytes(payload)
        metadata.append(recovery.checked_builder_source(path))
    assert metadata[0] == metadata[1]
    assert metadata[0]["normalized_lf_bytes"] == len(lf)


def test_builder_source_rejects_lone_carriage_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "builder.py"
    path.write_bytes(b"line one\rline two\n")
    monkeypatch.setattr(
        recovery,
        "BUILDER_LF_SHA256",
        hashlib.sha256(b"line one\rline two\n").hexdigest(),
    )
    monkeypatch.setattr(
        recovery,
        "BUILDER_GIT_BLOB_SHA1",
        recovery.git_blob_sha1(b"line one\rline two\n"),
    )
    with pytest.raises(recovery.RecoveryError, match="unsupported lone CR"):
        recovery.checked_builder_source(path)


def test_source_count_is_deterministically_sorted() -> None:
    rows = [pair("a", "b", source="z"), pair("c", "d", source="a")]
    assert recovery.source_count(rows) == {"a": 1, "z": 1}
