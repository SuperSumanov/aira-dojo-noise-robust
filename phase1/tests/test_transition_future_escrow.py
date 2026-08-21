import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from phase1 import prospective_transition_future_escrow as escrow
from phase1 import transition_future_fullfit as fullfit
from phase1 import activate_transition_future_escrow as activation
from phase1 import verify_transition_future_activation as activation_verifier
from phase1 import verify_transition_future_fullfit as fullfit_verifier
from phase1 import verify_prospective_transition_future_escrow as escrow_verifier


class FirstCoordinateModel:
    def decision_function(self, values):
        return np.asarray(values)[:, 0]


def _card(identifier: str, parent: str, run: str, generation: str, size: int):
    code = "x" * size + "\n"
    return {
        "id": identifier,
        "task": "task",
        "run": run,
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "parent": parent,
        "lineage": {"depth": 1, "step": 1, "n_siblings": 2, "op": "Improve"},
        "generation_started_at_utc": generation,
        "source_sha256": "a" * 64,
    }


def _cards():
    before = "2026-08-21T00:00:00Z"
    equal = "2026-08-21T01:00:00Z"
    after = "2026-08-21T02:00:00Z"
    return {
        "p": _card("p", "root", "old-run", before, 10),
        "a": _card("a", "p", "old-run", before, 20),
        "b": _card("b", "p", "old-run", before, 35),
        "u": _card("u", "missing", "equal-run", equal, 20),
        "v": _card("v", "missing", "equal-run", equal, 35),
        "q": _card("q", "root-2", "new-run", after, 10),
        "c": _card("c", "q", "new-run", after, 20),
        "d": _card("d", "q", "new-run", after, 35),
    }


def test_reference_orientation_is_canonical() -> None:
    rows = [
        {"task": "t", "parent": "p", "better": "b", "worse": "a", "intask_split": "train"},
        {"task": "t", "parent": "q", "better": "c", "worse": "d", "intask_split": "dev"},
    ]
    margins = {arm: np.asarray([2.0, 3.0]) for arm in fullfit.ARMS}
    result = fullfit.reference_rows(rows, margins)
    assert result[0]["left"] == "a" and result[0]["right"] == "b"
    assert result[0]["child_code"] == -2.0
    assert result[1]["left"] == "c" and result[1]["child_code"] == 3.0


def test_fullfit_scoring_is_antisymmetric() -> None:
    rng = np.random.default_rng(7)
    matrices = {
        "child_code": rng.normal(size=(64, 31)),
        "transition_only": rng.normal(size=(64, 37)),
        "child_plus_transition": rng.normal(size=(64, 68)),
    }
    models, _training, _receipts = fullfit.fit_full(matrices)
    forward, errors = fullfit.score_differences(models, matrices)
    reversed_matrices = {arm: -values for arm, values in matrices.items()}
    reverse, reverse_errors = fullfit.score_differences(models, reversed_matrices)
    for arm in fullfit.ARMS:
        assert np.max(np.abs(forward[arm] + reverse[arm])) <= 1e-12
        assert errors[arm] <= 1e-12 and reverse_errors[arm] <= 1e-12


def test_snapshot_scoring_enforces_parent_overlap_and_strict_timestamp() -> None:
    cards = _cards()
    models = {arm: FirstCoordinateModel() for arm in fullfit.ARMS}
    training = {
        "support_ids": {"p"},
        "support_runs": set(),
        "support_code_sha256": set(),
    }
    rows, _receipt, errors = escrow.score_snapshot(
        cards,
        [("a", "b"), ("u", "v"), ("c", "d")],
        dt.datetime.fromisoformat("2026-08-21T01:00:00+00:00"),
        models,
        training,
    )
    old, equal_missing, future = rows
    assert old["temporal_stratum"] == "support_only"
    assert old["training_endpoint_id_overlap"] is True
    assert old["source_novel"] is False and old["strict_effect_eligible"] is False
    assert equal_missing["temporal_stratum"] == "support_only"
    assert equal_missing["parent_source_present"] is False
    assert all(equal_missing[arm] is None for arm in fullfit.ARMS)
    assert future["temporal_stratum"] == "strict_future"
    assert future["parent_source_present"] is True
    assert future["source_novel"] is True
    assert future["finite_all_arms"] is True and future["nontie_all_arms"] is True
    assert future["strict_effect_eligible"] is True
    assert max(errors.values()) <= 1e-12


def test_all_three_arms_must_be_nontie() -> None:
    cards = _cards()

    class ZeroTransition(FirstCoordinateModel):
        def decision_function(self, values):
            if np.asarray(values).shape[1] == 37:
                return np.zeros(len(values))
            return super().decision_function(values)

    models = {arm: ZeroTransition() for arm in fullfit.ARMS}
    rows, _receipt, _errors = escrow.score_snapshot(
        cards,
        [("c", "d")],
        dt.datetime.fromisoformat("2026-08-21T01:00:00+00:00"),
        models,
        {"support_ids": set(), "support_runs": set(), "support_code_sha256": set()},
    )
    assert rows[0]["finite_all_arms"] is True
    assert rows[0]["nontie_all_arms"] is False
    assert rows[0]["strict_effect_eligible"] is False


def test_support_gate_ready_only_when_every_fixed_gate_passes() -> None:
    rows = []
    for index in range(1500):
        rows.append(
            {
                "temporal_stratum": "strict_future",
                "parent_source_present": True,
                "strict_effect_eligible": True,
                "task": f"task-{index % 15}",
                "run_id": f"run-{index % 150}",
                "training_endpoint_id_overlap": False,
                "training_run_id_overlap": False,
                "training_code_sha_overlap": False,
            }
        )
    support = escrow.summarize_support(rows)
    assert support["status"] == "TRANSITION_ESCROW_FUTURE_SUPPORT_READY_OUTCOMES_STILL_LOCKED"
    assert all(support["gates"].values())
    rows[0]["training_endpoint_id_overlap"] = True
    blocked = escrow.summarize_support(rows)
    assert blocked["status"] == "TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT"
    assert blocked["gates"]["strict_training_endpoint_overlap_zero"] is False


def test_prior_artifact_tamper_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "prior"
    root.mkdir()
    pair = {field: None for field in escrow.PAIR_FIELDS}
    pair.update({"pair_id": "id", "task": "t", "run_id": "r", "parent": "p", "left": "a", "right": "b"})
    pairs_path = root / "pairs.jsonl"
    pairs_path.write_text(json.dumps(pair) + "\n", encoding="utf-8")
    summary = {"outputs": {"pairs_sha256": hashlib.sha256(pairs_path.read_bytes()).hexdigest()}}
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
    summary_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    loaded, rows = escrow.load_prior(root, summary_sha)
    assert loaded == summary and len(rows) == 1
    pairs_path.write_text(json.dumps({**pair, "task": "tampered"}) + "\n", encoding="utf-8")
    with pytest.raises(escrow.EscrowError, match="prior pairs hash differs"):
        escrow.load_prior(root, summary_sha)


def test_activation_uses_parsed_timestamp_not_lexicographic_max(tmp_path: Path) -> None:
    snapshot_sha = "f" * 64
    state = tmp_path / "state"
    snapshot = state / "snapshots" / snapshot_sha
    runs = snapshot / "accumulator" / "provisional_runs.jsonl"
    runs.parent.mkdir(parents=True)
    values = [
        {
            "run_id": "zero",
            "flow_status": "scoreable",
            "generation_started_at_utc": "2026-08-21T00:00:00Z",
        },
        {
            "run_id": "fraction",
            "flow_status": "scoreable",
            "generation_started_at_utc": "2026-08-21T00:00:00.500000Z",
        },
    ]
    runs.write_text("".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")
    (state / "LATEST").write_text(snapshot_sha + "\n", encoding="utf-8")
    produced = activation.current_snapshot_receipt(state, snapshot_sha)
    verified = activation_verifier.snapshot_receipt(state, snapshot_sha)
    assert produced["maximum_generation_started_at_utc"] == "2026-08-21T00:00:00.500000Z"
    assert verified["maximum_generation_started_at_utc"] == "2026-08-21T00:00:00.500000Z"


def test_source_binding_checks_only_registered_blobs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    protocol = repo / "protocol.json"
    source = repo / "source.py"
    protocol.write_text(
        json.dumps(
            {
                "protocol": fullfit.ESCROW_PROTOCOL,
                "source_paths": ["protocol.json", "source.py"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "protocol.json", "source.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

    # A forbidden-name file elsewhere in the worktree is deliberately untracked.
    # Source binding must neither enumerate nor require cleanliness of unrelated paths.
    (repo / ".env_default").write_text("metadata sentinel\n", encoding="utf-8")
    paths = ["protocol.json", "source.py"]
    assert fullfit.bind_source(repo, commit, protocol)[1].keys() == set(paths)
    assert fullfit_verifier.bind_source(repo, commit, protocol)[1].keys() == set(paths)
    assert activation.bind_source(repo, commit, paths).keys() == set(paths)
    assert activation_verifier.source_hashes(repo, commit, paths).keys() == set(paths)
    assert escrow_verifier.bind_source(repo, commit, protocol)[1].keys() == set(paths)

    modules = (fullfit, fullfit_verifier, activation, activation_verifier, escrow_verifier)
    for module in modules:
        assert '"status", "--porcelain"' not in Path(module.__file__).read_text(encoding="utf-8")

    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(fullfit.FullFitError, match="bound source differs"):
        fullfit.bind_source(repo, commit, protocol)
