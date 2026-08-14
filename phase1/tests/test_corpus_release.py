import copy
import hashlib
import json
from pathlib import Path

import pytest

from phase1.corpus_release import (
    CorpusReleaseError,
    PROTOCOL_BASIC,
    PROTOCOL_SANITIZED,
    PROTOCOL_SANITIZED_V11,
    build_release,
    load_contracts,
)


def canonical_lock(records: list[dict]) -> str:
    raw = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def stats(raw: bytes) -> dict:
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(raw.splitlines()),
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_contract(
    root: Path,
    batches: list[tuple[str, bytes]],
    expected_output: bytes,
    protocol: str = PROTOCOL_BASIC,
) -> tuple[Path, Path]:
    phase1 = root / "phase1"
    releases = phase1 / "corpus_releases"
    releases.mkdir(parents=True)
    records = []
    for name, raw in batches:
        (phase1 / name).write_bytes(raw)
        records.append({"file": name, **stats(raw)})
    registry = {
        "schema_version": "aira-dojo-corpus-batch-registry-v1",
        "batches": records,
    }
    release = {
        "schema_version": "aira-dojo-corpus-release-v1",
        "version": "v99",
        "release_commit": "a" * 40,
        "rebuild_protocol": protocol,
        "batch_count": len(records),
        "batch_lock_sha256": canonical_lock(records),
        "output": {"file": "cards_current_v99.jsonl", **stats(expected_output)},
    }
    registry_path = releases / "batch_registry.json"
    release_path = releases / "v99.json"
    write_json(registry_path, registry)
    write_json(release_path, release)
    return release_path, phase1


def jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row) + "\n" for row in rows).encode()


def test_basic_protocol_is_byte_exact_and_writes_receipt(tmp_path: Path) -> None:
    rows = [
        {
            "id": "a1",
            "task": {"name": "spaceship-titanic", "type": "tabular"},
            "lineage": {"step": 1, "parent_id": None},
        },
        {
            "id": "a2",
            "task": {"name": "spaceship-titanic", "type": "tabular"},
            "lineage": {"step": 2, "parent_id": "a1"},
            "provenance": {"source": "synthetic"},
        },
    ]
    expected_rows = copy.deepcopy(rows)
    for row in expected_rows:
        row["run_id"] = "cards_batch_a.jsonl:0"
        row.setdefault("provenance", {})[
            "run_id_source"
        ] = "reconstructed:file-contiguity"
    expected = jsonl(expected_rows)
    release, phase1 = make_contract(
        tmp_path, [("cards_batch_a.jsonl", jsonl(rows))], expected
    )
    output = tmp_path / "output.jsonl"
    receipt = tmp_path / "receipt.json"
    result = build_release(release, output, phase1_dir=phase1, receipt_path=receipt)
    assert output.read_bytes() == expected
    assert result["status"] == "VERIFIED_BYTE_EXACT_CORPUS_REBUILD"
    assert result["segmentation"]["runs"] == 1
    assert json.loads(receipt.read_text())["output"]["sha256"] == stats(expected)["sha256"]


def test_sanitized_protocol_freezes_task_type_and_nonfinite_quarantine(
    tmp_path: Path,
) -> None:
    row = {
        "id": "x1",
        "task": {"name": "spooky-author-identification", "type": "wrong"},
        "lineage": {"step": 1, "parent_id": None},
        "label": {"graded": float("nan"), "y_norm": 0.2, "medal_bucket": "bronze"},
    }
    expected_row = copy.deepcopy(row)
    expected_row["task"]["type"] = "nlp"
    expected_row["label"] = {"graded": None, "y_norm": None, "medal_bucket": "invalid"}
    expected_row["provenance"] = {
        "label_status": "quarantined:nonfinite_label",
        "run_id_source": "reconstructed:file-contiguity",
        "task_type_source": "phase1.build_cards:TASK_TYPE",
    }
    expected_row["run_id"] = "cards_batch_b.jsonl:0"
    expected = (json.dumps(expected_row, allow_nan=False) + "\n").encode()
    release, phase1 = make_contract(
        tmp_path,
        [("cards_batch_b.jsonl", jsonl([row]))],
        expected,
        protocol=PROTOCOL_SANITIZED,
    )
    output = tmp_path / "sanitized.jsonl"
    build_release(release, output, phase1_dir=phase1)
    assert output.read_bytes() == expected


def test_v11_protocol_includes_the_new_dogs_vs_cats_task(tmp_path: Path) -> None:
    row = {
        "id": "dog1",
        "task": {"name": "dogs-vs-cats-redux-kernels-edition", "type": "wrong"},
        "lineage": {"step": 1, "parent_id": None},
    }
    expected_row = copy.deepcopy(row)
    expected_row["task"]["type"] = "image-cls"
    expected_row["run_id"] = "cards_batch_dog.jsonl:0"
    expected_row["provenance"] = {
        "run_id_source": "reconstructed:file-contiguity",
        "task_type_source": "phase1.build_cards:TASK_TYPE",
    }
    expected = jsonl([expected_row])
    release, phase1 = make_contract(
        tmp_path,
        [("cards_batch_dog.jsonl", jsonl([row]))],
        expected,
        protocol=PROTOCOL_SANITIZED_V11,
    )
    output = tmp_path / "v11.jsonl"
    build_release(release, output, phase1_dir=phase1)
    assert output.read_bytes() == expected


def test_unsmudged_lfs_pointer_fails_before_hash_acceptance(tmp_path: Path) -> None:
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:" + b"f" * 64 + b"\nsize 123\n"
    )
    release, phase1 = make_contract(
        tmp_path, [("cards_batch_pointer.jsonl", pointer)], b"not-used\n"
    )
    with pytest.raises(CorpusReleaseError, match="unsmudged Git LFS pointer"):
        build_release(release, tmp_path / "out.jsonl", phase1_dir=phase1)


def test_changed_immutable_batch_fails_closed(tmp_path: Path) -> None:
    row = {
        "id": "a1",
        "task": {"name": "spaceship-titanic"},
        "lineage": {"step": 1, "parent_id": None},
    }
    raw = jsonl([row])
    release, phase1 = make_contract(
        tmp_path, [("cards_batch_a.jsonl", raw)], b"not-used\n"
    )
    (phase1 / "cards_batch_a.jsonl").write_bytes(raw + b"\n")
    with pytest.raises(CorpusReleaseError, match="immutable batch mismatch"):
        build_release(release, tmp_path / "out.jsonl", phase1_dir=phase1)


def test_bad_output_contract_leaves_no_partial_output(tmp_path: Path) -> None:
    row = {
        "id": "a1",
        "task": {"name": "spaceship-titanic"},
        "lineage": {"step": 1, "parent_id": None},
    }
    release, phase1 = make_contract(
        tmp_path, [("cards_batch_a.jsonl", jsonl([row]))], b"deliberately-wrong\n"
    )
    output = tmp_path / "out.jsonl"
    with pytest.raises(CorpusReleaseError, match="rebuilt output mismatch"):
        build_release(release, output, phase1_dir=phase1)
    assert not output.exists()
    assert not list(tmp_path.glob(".out.jsonl.*.tmp"))


def test_registry_append_does_not_change_a_pinned_prefix(tmp_path: Path) -> None:
    row = {
        "id": "a1",
        "task": {"name": "spaceship-titanic"},
        "lineage": {"step": 1, "parent_id": None},
    }
    expected_row = copy.deepcopy(row)
    expected_row["run_id"] = "cards_batch_a.jsonl:0"
    expected_row["provenance"] = {"run_id_source": "reconstructed:file-contiguity"}
    release, phase1 = make_contract(
        tmp_path,
        [("cards_batch_a.jsonl", jsonl([row]))],
        jsonl([expected_row]),
    )
    registry_path = release.with_name("batch_registry.json")
    registry = json.loads(registry_path.read_text())
    registry["batches"].append(
        {"file": "cards_future.jsonl", "sha256": "b" * 64, "bytes": 10, "rows": 1}
    )
    write_json(registry_path, registry)
    loaded, selected, _ = load_contracts(release)
    assert loaded["batch_count"] == 1
    assert [record["file"] for record in selected] == ["cards_batch_a.jsonl"]
    build_release(release, tmp_path / "out.jsonl", phase1_dir=phase1)


def test_release_contract_rejects_unknown_fields(tmp_path: Path) -> None:
    row = {
        "id": "a1",
        "task": {"name": "spaceship-titanic"},
        "lineage": {"step": 1, "parent_id": None},
    }
    release, _ = make_contract(
        tmp_path, [("cards_batch_a.jsonl", jsonl([row]))], b"not-used\n"
    )
    value = json.loads(release.read_text())
    value["surprise"] = True
    write_json(release, value)
    with pytest.raises(CorpusReleaseError, match="unknown=.*surprise"):
        load_contracts(release)


def test_checked_in_release_descriptors_have_valid_prefix_locks() -> None:
    releases = Path(__file__).resolve().parents[1] / "corpus_releases"
    expected = {
        "v6": (23, 9433, PROTOCOL_BASIC),
        "v7": (25, 10755, PROTOCOL_BASIC),
        "v8": (26, 12383, PROTOCOL_BASIC),
        "v9": (27, 14323, PROTOCOL_BASIC),
        "v10": (28, 15158, PROTOCOL_SANITIZED),
        "v11": (29, 16012, PROTOCOL_SANITIZED_V11),
    }
    for version, (count, rows, protocol) in expected.items():
        release, selected, _ = load_contracts(releases / f"{version}.json")
        assert len(selected) == count
        assert sum(record["rows"] for record in selected) == rows
        assert release["rebuild_protocol"] == protocol


def test_withheld_batches_cannot_enter_public_registry_or_manifest() -> None:
    phase1 = Path(__file__).resolve().parents[1]
    releases = phase1 / "corpus_releases"
    withheld = json.loads((releases / "withheld_batches.json").read_text(encoding="utf-8"))
    assert set(withheld) == {"schema_version", "batches"}
    assert withheld["schema_version"] == "aira-dojo-corpus-withheld-batches-v1"
    assert withheld["batches"]

    registry = json.loads((releases / "batch_registry.json").read_text(encoding="utf-8"))
    public_files = {record["file"] for record in registry["batches"]}
    manifest_files = {
        line.strip()
        for line in (phase1 / "corpus_manifest.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    required_keys = {
        "file",
        "sha256",
        "bytes",
        "rows",
        "source_runs",
        "status",
        "release_eligible",
        "reason",
    }
    for record in withheld["batches"]:
        assert set(record) == required_keys
        assert record["release_eligible"] is False
        assert record["status"] == "WITHHELD_TEMPORAL_BLIND_LABEL_VAULT"
        assert record["file"] not in public_files
        assert record["file"] not in manifest_files
        assert not (phase1 / record["file"]).exists()
        assert len(record["sha256"]) == 64
        int(record["sha256"], 16)
        assert record["bytes"] > 0
        assert record["rows"] > 0
        assert record["source_runs"] > 0


def test_future_merged_corpora_are_not_automatically_added_to_lfs() -> None:
    root = Path(__file__).resolve().parents[2]
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "phase1/cards_current_v*.jsonl" not in attributes
    for version in ("v9", "v10", "v11"):
        assert f"phase1/cards_current_{version}.jsonl filter=lfs" in attributes
    assert "phase1/rebuilt/" in (root / ".gitignore").read_text(encoding="utf-8")
