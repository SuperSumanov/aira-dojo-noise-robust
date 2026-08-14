from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_opportunity_identity_recovery as producer
from phase1 import verify_source_opportunity_identity_recovery as verifier


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def card(card_id: str, parent: str | None, children: list[str]) -> dict:
    return {
        "id": card_id,
        "lineage": {"parent_id": parent, "children_ids": children},
        "label": {"graded": 0.123},
        "code": "ignored",
    }


def parent_row(role: str, parent: str, source_size: int, retained: int, present: bool) -> dict:
    return {
        "role": role,
        "parent": parent,
        "source_declared_size": source_size,
        "raw_card_child_count": retained,
        "parent_card_present": str(present),
    }


def fixture(tmp_path: Path, *, break_frozen: bool = False) -> dict[str, Path]:
    frozen_children = ["fa", "fb"] if break_frozen else ["fa", "fb", "fm"]
    cards = [
        card("control", None, ["ca", "cb"]),
        card("ca", "control", []),
        card("cb", "control", []),
        card("train-parent", None, ["ta", "tb", "tm"]),
        card("ta", "train-parent", []),
        card("tb", "train-parent", []),
        card("frozen-parent", None, frozen_children),
        card("fa", "frozen-parent", []),
        card("fb", "frozen-parent", []),
        card("extension-parent", None, ["ea", "eb", "em"]),
        card("ea", "extension-parent", []),
        card("eb", "extension-parent", []),
    ]
    parents = [
        parent_row("train", "control", 2, 2, True),
        parent_row("train", "train-parent", 3, 2, True),
        parent_row("frozen", "frozen-parent", 3, 2, True),
        parent_row("extension", "extension-parent", 3, 2, True),
    ]
    paths = {
        "cards": tmp_path / "cards.jsonl",
        "parents": tmp_path / "parents.csv",
        "root": tmp_path / "recovery",
        "receipt": tmp_path / "receipt.json",
    }
    write_jsonl(paths["cards"], cards)
    with paths["parents"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(parents[0]))
        writer.writeheader()
        writer.writerows(parents)
    return paths


def producer_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        cards=str(paths["cards"]),
        per_parent=str(paths["parents"]),
        source_commit="a" * 40,
        output=str(paths["root"]),
    )


def verifier_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        recovery_root=str(paths["root"]),
        cards=str(paths["cards"]),
        per_parent=str(paths["parents"]),
        output=str(paths["receipt"]),
    )


def summary(paths: dict[str, Path]) -> dict:
    return json.loads((paths["root"] / "summary.json").read_text(encoding="utf-8"))


def test_high_coverage_recovers_missing_identities_without_outcomes(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_HIGH
    assert value["source_incomplete_parents"] == 3
    assert value["exact_identity_recoverable_parents"] == 3
    assert value["scope"]["accesses_label_fields"] is False
    assert value["complete_labeled_choice_set_claim_allowed"] is False
    assert verifier.verify(verifier_args(paths)) == 0


def test_partial_recovery_does_not_pass_frozen_or_overall_gate(tmp_path: Path) -> None:
    paths = fixture(tmp_path, break_frozen=True)
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_PARTIAL
    assert value["exact_identity_recovery_rate"] == pytest.approx(2 / 3)
    assert value["criteria"]["frozen_recovery_rate_ge_0_75"] is False
    assert verifier.verify(verifier_args(paths)) == 0


def test_orphan_incomplete_parent_is_retained_as_unrecoverable(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    with paths["parents"].open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "role",
                "parent",
                "source_declared_size",
                "raw_card_child_count",
                "parent_card_present",
            ],
        )
        writer.writerow(parent_row("train", "orphan", 3, 2, False))
    cards = [card("oa", "orphan", []), card("ob", "orphan", [])]
    with paths["cards"].open("a", encoding="utf-8", newline="\n") as handle:
        for row in cards:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    assert producer.run(producer_args(paths)) == 0
    rows = [
        json.loads(line)
        for line in (paths["root"] / "per_parent.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    orphan = next(row for row in rows if row["parent"] == "orphan")
    assert orphan["exact_identity_recoverable"] is False
    assert orphan["reason"] == "ORPHAN_PARENT_CARD"
    assert orphan["missing_status"] == "UNKNOWN"
    assert verifier.verify(verifier_args(paths)) == 0


def test_independent_verifier_rejects_rehashed_identity_tamper(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    rows_path = paths["root"] / "per_parent.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["missing_child_ids"] = ["invented"]
    write_jsonl(rows_path, rows)
    manifest_path = paths["root"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["per_parent.jsonl"] = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="per-parent"):
        verifier.verify(verifier_args(paths))


def test_credential_shape_is_rejected_before_parse(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    paths["cards"].write_bytes(b"not-json sk-" + b"A" * 20 + b"\n")
    with pytest.raises(producer.RecoveryError, match="credential-shaped"):
        producer.run(producer_args(paths))


def test_independent_verifier_source_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("source_opportunity_identity_recovery" in name for name in imported)
