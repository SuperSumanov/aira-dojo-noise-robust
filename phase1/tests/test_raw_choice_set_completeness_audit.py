from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import raw_choice_set_completeness_audit as producer
from phase1 import verify_raw_choice_set_completeness_audit as verifier


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def card(
    card_id: str,
    *,
    parent: str | None,
    run: str,
    siblings: int | None,
    children: list[str] | None = None,
    grade: float | None = 0.5,
) -> dict:
    return {
        "id": card_id,
        "task": {"name": "task-a"},
        "run_id": run,
        "lineage": {
            "parent_id": parent,
            "n_siblings": siblings,
            "children_ids": children or [],
        },
        "label": {"graded": grade} if grade is not None else None,
    }


def pairs(role_parent: str, endpoints: list[str], run: str, set_size: int) -> list[dict]:
    rows = []
    for left_index, left in enumerate(endpoints):
        for right in endpoints[left_index + 1 :]:
            rows.append(
                {
                    "task": "task-a",
                    "run_id": run,
                    "parent": role_parent,
                    "better": left,
                    "worse": right,
                    "set_size": set_size,
                    "budget": 0,
                }
            )
    return rows


def fixture(
    tmp_path: Path,
    *,
    include_fragment: bool = True,
    complete_size: int = 3,
    declared_size: int | None = None,
    nonfinite_last: bool = False,
    inconsistent_siblings: bool = False,
) -> dict[str, Path]:
    rows: list[dict] = []
    run_map: dict[str, str] = {}
    train_rows: list[dict] = []
    frozen_rows: list[dict] = []
    if include_fragment:
        rows.extend(
            [
                card(
                    "parent-fragment",
                    parent=None,
                    run="run-fragment",
                    siblings=0,
                    children=["fa", "fb", "fc", "fd", "fe"],
                ),
                card("fa", parent="parent-fragment", run="run-fragment", siblings=4),
                card("fb", parent="parent-fragment", run="run-fragment", siblings=4),
            ]
        )
        train_rows = pairs("parent-fragment", ["fa", "fb"], "run-fragment", 2)

    endpoint_ids = [f"q{index}" for index in range(complete_size)]
    rows.append(
        card(
            "parent-complete",
            parent=None,
            run="run-complete",
            siblings=0,
            children=endpoint_ids,
        )
    )
    for index, endpoint in enumerate(endpoint_ids):
        sibling_count = complete_size - 1
        if inconsistent_siblings and index == 1:
            sibling_count += 1
        rows.append(
            card(
                endpoint,
                parent="parent-complete",
                run="run-complete",
                siblings=sibling_count,
                grade=None if nonfinite_last and index == complete_size - 1 else 0.5 + index,
            )
        )
    frozen_rows = pairs(
        "parent-complete",
        endpoint_ids,
        "run-complete",
        declared_size if declared_size is not None else complete_size,
    )
    for row in rows:
        run_map[row["id"]] = row["run_id"]

    paths = {
        "cards": tmp_path / "cards.jsonl",
        "run_map": tmp_path / "run_map.json",
        "train": tmp_path / "train.jsonl",
        "frozen": tmp_path / "frozen.jsonl",
        "extension": tmp_path / "extension.jsonl",
        "audit": tmp_path / "audit",
        "verification": tmp_path / "verification.json",
    }
    write_jsonl(paths["cards"], rows)
    write_json(paths["run_map"], run_map)
    write_jsonl(paths["train"], train_rows)
    write_jsonl(paths["frozen"], frozen_rows)
    write_jsonl(paths["extension"], [])
    return paths


def producer_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        cards=str(paths["cards"]),
        run_map=str(paths["run_map"]),
        train=str(paths["train"]),
        frozen=str(paths["frozen"]),
        extension=str(paths["extension"]),
        source_commit="a" * 40,
        output=str(paths["audit"]),
    )


def verifier_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        audit_root=str(paths["audit"]),
        cards=str(paths["cards"]),
        run_map=str(paths["run_map"]),
        train=str(paths["train"]),
        frozen=str(paths["frozen"]),
        extension=str(paths["extension"]),
        output=str(paths["verification"]),
    )


def summary(paths: dict[str, Path]) -> dict:
    return json.loads((paths["audit"] / "summary.json").read_text(encoding="utf-8"))


def test_retained_two_of_source_five_is_labeled_fragment(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    result = summary(paths)
    assert result["status"] == producer.STATUS_FRAGMENT
    assert result["criteria"]["endpoint_fidelity_all"] is True
    assert result["criteria"]["finite_set_declaration_all"] is True
    assert result["criteria"]["source_choice_set_retained_all"] is False
    assert result["choice_set_faithful_claim_allowed"] is False
    assert result["labeled_sibling_fragment_claim_allowed"] is True
    assert verifier.verify(verifier_args(paths)) == 0
    receipt = json.loads(paths["verification"].read_text(encoding="utf-8"))
    assert receipt["producer_status"] == producer.STATUS_FRAGMENT
    assert receipt["imports_producer"] is False


def test_complete_source_set_allows_claim(tmp_path: Path) -> None:
    paths = fixture(tmp_path, include_fragment=False)
    assert producer.run(producer_args(paths)) == 0
    result = summary(paths)
    assert result["status"] == producer.STATUS_COMPLETE
    assert result["choice_set_faithful_claim_allowed"] is True
    assert verifier.verify(verifier_args(paths)) == 0


def test_release_schema_without_pair_run_id_derives_it_from_endpoints(
    tmp_path: Path,
) -> None:
    paths = fixture(tmp_path)
    for role in ("train", "frozen", "extension"):
        rows = [
            json.loads(line)
            for line in paths[role].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            row.pop("run_id")
        write_jsonl(paths[role], rows)
    assert producer.run(producer_args(paths)) == 0
    assert summary(paths)["status"] == producer.STATUS_FRAGMENT
    assert verifier.verify(verifier_args(paths)) == 0


def test_complete_source_set_above_five_stays_on_provenance_hold(tmp_path: Path) -> None:
    paths = fixture(tmp_path, include_fragment=False, complete_size=6)
    assert producer.run(producer_args(paths)) == 0
    result = summary(paths)
    assert result["status"] == producer.STATUS_PROVENANCE_HOLD
    assert result["criteria"]["source_choice_set_retained_all"] is True
    assert result["criteria"]["source_size_gt_five_provenance_resolved"] is False
    assert result["choice_set_faithful_claim_allowed"] is False
    assert verifier.verify(verifier_args(paths)) == 0


@pytest.mark.parametrize(
    ("fixture_kwargs", "failed_criterion"),
    [
        ({"declared_size": 2}, "finite_set_declaration_all"),
        ({"nonfinite_last": True, "declared_size": 2}, "endpoint_fidelity_all"),
        ({"inconsistent_siblings": True}, "source_metadata_consistent_all"),
    ],
)
def test_structural_corruption_is_invalid(
    tmp_path: Path, fixture_kwargs: dict, failed_criterion: str
) -> None:
    paths = fixture(tmp_path, include_fragment=False, **fixture_kwargs)
    assert producer.run(producer_args(paths)) == 0
    result = summary(paths)
    assert result["status"] == producer.STATUS_INVALID
    assert result["criteria"][failed_criterion] is False
    assert result["labeled_sibling_fragment_claim_allowed"] is False
    assert verifier.verify(verifier_args(paths)) == 0


def test_independent_verifier_rejects_rehashed_parent_tamper(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    per_parent = paths["audit"] / "per_parent.csv"
    with per_parent.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["raw_card_child_count"] = "999"
    with per_parent.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest_path = paths["audit"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["per_parent.csv"] = hashlib.sha256(per_parent.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(verifier.VerificationError, match="per_parent mismatch"):
        verifier.verify(verifier_args(paths))


def test_independent_verifier_rejects_rehashed_summary_aggregate_tamper(
    tmp_path: Path,
) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    summary_path = paths["audit"] / "summary.json"
    summary_value = json.loads(summary_path.read_text(encoding="utf-8"))
    summary_value["roles"]["train"]["parents"] = 999
    write_json(summary_path, summary_value)
    manifest_path = paths["audit"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(verifier.VerificationError, match="role aggregates mismatch"):
        verifier.verify(verifier_args(paths))


def test_credential_shape_is_rejected_before_cards_parse(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    paths["cards"].write_bytes(b"not-json sk-" + b"A" * 20 + b"\n")
    with pytest.raises(producer.AuditError, match="credential-shaped"):
        producer.run(producer_args(paths))


def test_independent_verifier_source_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.endswith("raw_choice_set_completeness_audit") for name in imported)
