from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import phase1.build_balanced_continuation_e1_inputs as producer
import phase1.verify_balanced_continuation_e1_inputs as verifier


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision(task: str, run: str, parent: str, left: str, right: str, gap: float = 0.1) -> dict:
    return {
        "better": left,
        "budget": 0,
        "clears_tau": None,
        "gap_raw": gap,
        "intask_split": "train",
        "loto_fold": task,
        "parent": parent,
        "run_id": run,
        "set_size": 2,
        "src": "decision_v11",
        "task": task,
        "worse": right,
    }


def card(card_id: str, task: str, run: str, parent: str | None, code: str) -> dict:
    return {
        "id": card_id,
        "task": {"name": task},
        "run_id": run,
        "lineage": {"parent_id": parent},
        "code": code,
    }


def fixture(tmp_path: Path) -> tuple[dict[str, Path], dict[str, str]]:
    cards = tmp_path / "cards.jsonl"
    hold = tmp_path / "hold.json"
    train = tmp_path / "train.jsonl"
    frozen = [tmp_path / f"frozen_{index}.jsonl" for index in range(3)]
    rows = []
    decisions = []
    for task_index, task in enumerate(producer.TARGET_TASKS):
        run = f"run-{task_index}"
        parent = f"parent-{task_index}"
        left, right = f"left-{task_index}", f"right-{task_index}"
        rows.extend([
            card(parent, task, run, None, f"print('parent-{task_index}')\n"),
            card(left, task, run, parent, f"print('left-{task_index}')\n"),
            card(right, task, run, parent, f"print('right-{task_index}')\n"),
        ])
        decisions.append(decision(task, run, parent, left, right))
    rows.extend([
        card("frozen-left", producer.TARGET_TASKS[0], "frozen-run", None, "print('frozen-left')\n"),
        card("frozen-right", producer.TARGET_TASKS[0], "frozen-run", None, "print('frozen-right')\n"),
    ])
    write_jsonl(cards, rows)
    write_json(hold, {
        "all": ["run-0", "run-1", "frozen-run"],
        "hold": ["frozen-run"],
        "new_hold": [],
        "prior_all": ["run-0", "run-1", "frozen-run"],
        "prior_hold": ["frozen-run"],
        "seed": 7,
    })
    write_jsonl(train, decisions)
    for index, path in enumerate(frozen):
        write_jsonl(path, [{
            "better": "frozen-left",
            "worse": "frozen-right",
        }])
    paths = {
        "cards": cards,
        "hold": hold,
        "decision_train_b0": train,
        "frozen_b0": frozen[0],
        "frozen_b1": frozen[1],
        "frozen_b2": frozen[2],
    }
    return paths, {role: sha(path) for role, path in paths.items()}


def build_args(paths: dict[str, Path], output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        cards=str(paths["cards"]),
        hold=str(paths["hold"]),
        decision_train_b0=str(paths["decision_train_b0"]),
        frozen_b0=str(paths["frozen_b0"]),
        frozen_b1=str(paths["frozen_b1"]),
        frozen_b2=str(paths["frozen_b2"]),
        output=str(output.resolve()),
    )


def verify_args(paths: dict[str, Path], result: Path, receipt: Path) -> argparse.Namespace:
    value = build_args(paths, result)
    return argparse.Namespace(**vars(value), result=str(result), receipt=str(receipt))


def test_end_to_end_independent_reconstruction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, hashes = fixture(tmp_path)
    monkeypatch.setattr(producer, "EXPECTED_SHA256", hashes)
    monkeypatch.setattr(producer, "EXPECTED_CARD_ROWS", 8)
    monkeypatch.setattr(verifier, "HASHES", hashes)
    monkeypatch.setattr(verifier, "EXPECTED_CARD_ROWS", 8)
    output = tmp_path / "result"
    summary = producer.build(build_args(paths, output))
    receipt = verifier.verify(verify_args(paths, output, tmp_path / "verified.json"))
    assert summary["selected_sibling_count"] == 4
    assert summary["selected_frozen_endpoint_overlap"] == 0
    assert receipt["status"] == "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP"
    anchors = verifier.read_jsonl(output / "anchors.jsonl")
    assert {row["sibling_id"] for row in anchors} == {"left-0", "right-0", "left-1", "right-1"}


def test_fresh_selection_excludes_prior_physical_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _ = fixture(tmp_path)
    cards = [json.loads(line) for line in paths["cards"].read_text().splitlines()]
    decisions = [json.loads(line) for line in paths["decision_train_b0"].read_text().splitlines()]
    hold = json.loads(paths["hold"].read_text())
    expected_fresh_runs = set()
    for task_index, task in enumerate(producer.TARGET_TASKS):
        run = f"run-z-{task_index}"
        parent = f"parent-z-{task_index}"
        left, right = f"left-z-{task_index}", f"right-z-{task_index}"
        cards.extend([
            card(parent, task, run, None, f"print('parent-z-{task_index}')\n"),
            card(left, task, run, parent, f"print('left-z-{task_index}')\n"),
            card(right, task, run, parent, f"print('right-z-{task_index}')\n"),
        ])
        decisions.append(decision(task, run, parent, left, right))
        hold["all"].append(run)
        hold["prior_all"].append(run)
        expected_fresh_runs.add(run)
    write_jsonl(paths["cards"], cards)
    write_jsonl(paths["decision_train_b0"], decisions)
    write_json(paths["hold"], hold)
    hashes = {role: sha(path) for role, path in paths.items()}
    monkeypatch.setattr(producer, "EXPECTED_SHA256", hashes)
    monkeypatch.setattr(producer, "EXPECTED_CARD_ROWS", 14)
    monkeypatch.setattr(verifier, "HASHES", hashes)
    monkeypatch.setattr(verifier, "EXPECTED_CARD_ROWS", 14)

    prior = tmp_path / "prior"
    producer.build(build_args(paths, prior))
    prior_selection = prior / "selected_public.json"
    prior_sha = sha(prior_selection)
    fresh_args = build_args(paths, tmp_path / "fresh")
    fresh_args.exclude_selected_public = str(prior_selection)
    fresh_args.exclude_selected_public_sha256 = prior_sha
    summary = producer.build(fresh_args)
    verify_fresh = verify_args(
        paths, tmp_path / "fresh", tmp_path / "fresh.verify.json"
    )
    verify_fresh.exclude_selected_public = str(prior_selection)
    verify_fresh.exclude_selected_public_sha256 = prior_sha
    receipt = verifier.verify(verify_fresh)

    selected = verifier.read_json(tmp_path / "fresh" / "selected_public.json")
    assert {row["source_run_id"] for row in selected} == expected_fresh_runs
    assert summary["selected_prior_run_overlap"] == 0
    assert receipt["selected_prior_run_overlap"] == 0


def test_parent_whitelist_ignores_winner_orientation_and_gap(tmp_path: Path) -> None:
    task = producer.TARGET_TASKS[0]
    other = producer.TARGET_TASKS[1]
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    shared = decision(other, "other-run", "other-parent", "a", "b", 0.2)
    write_jsonl(first, [decision(task, "run", "parent", "left", "right", 0.9), shared])
    write_jsonl(second, [decision(task, "run", "parent", "right", "left", 0.00001), shared])
    assert producer.load_training_parent_whitelist(first) == producer.load_training_parent_whitelist(second)


def test_frozen_endpoint_overlap_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _ = fixture(tmp_path)
    write_jsonl(paths["frozen_b0"], [{
        "better": "left-0", "worse": "frozen-right"
    }])
    hashes = {role: sha(path) for role, path in paths.items()}
    monkeypatch.setattr(producer, "EXPECTED_SHA256", hashes)
    monkeypatch.setattr(producer, "EXPECTED_CARD_ROWS", 8)
    with pytest.raises(producer.E1InputError, match="overlaps frozen evaluation"):
        producer.build(build_args(paths, tmp_path / "result"))


def test_selected_task_credential_shape_fails_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _ = fixture(tmp_path)
    rows = [json.loads(line) for line in paths["cards"].read_text(encoding="utf-8").splitlines()]
    rows[1]["code"] = "TOKEN = " + repr("sk-" + "A" * 30) + "\n"
    write_jsonl(paths["cards"], rows)
    hashes = {role: sha(path) for role, path in paths.items()}
    monkeypatch.setattr(producer, "EXPECTED_SHA256", hashes)
    monkeypatch.setattr(producer, "EXPECTED_CARD_ROWS", 8)
    with pytest.raises(producer.E1InputError, match="credential-shaped"):
        producer.build(build_args(paths, tmp_path / "result"))


def test_source_hash_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, hashes = fixture(tmp_path)
    hashes["cards"] = "0" * 64
    monkeypatch.setattr(producer, "EXPECTED_SHA256", hashes)
    monkeypatch.setattr(producer, "EXPECTED_CARD_ROWS", 8)
    with pytest.raises(producer.E1InputError, match="cards SHA differs"):
        producer.build(build_args(paths, tmp_path / "result"))
