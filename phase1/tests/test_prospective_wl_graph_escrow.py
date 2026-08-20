import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from phase1 import activate_wl_graph_extension as activation
from phase1.prospective_wl_graph_escrow import EscrowError, load_snapshot
from phase1.tests.test_wl_graph_multiview_extension import _cards, _pairs
from phase1.verify_prospective_wl_graph_escrow import score_independently
from phase1.wl_graph_multiview_extension import fit_bundle, load_bundle, score_cards


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values), encoding="utf-8")


def _snapshot(tmp_path: Path, generation: str = "2026-08-20T05:00:00Z") -> tuple[Path, Path]:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / ("a" * 64)
    intake = state / "intakes" / "drop-1"
    manifest = intake / "eligible_blind_manifest.jsonl"
    rows = []
    for index, identifier in enumerate(("a", "b"), 1):
        code = f"import numpy as np\nprint(np.mean([{index}]))\n"
        rows.append(
            {
                "card_id": identifier,
                "task": "task",
                "run_id": "run",
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "lineage": {"depth": 1, "step": index, "n_siblings": 2, "op": "Improve", "parent": "p"},
                "generation_started_at_utc": generation,
                "source_sha256": "b" * 64,
            }
        )
    _write_jsonl(manifest, rows)
    intake_summary = intake / "summary.json"
    _write_json(
        intake_summary,
        {
            "outputs": {"eligible_blind_manifest_sha256": _sha(manifest)},
            "security": {"env_members_read": False, "live_event_journal_members_read": False},
            "blindness": {
                "labels_used_for_run_selection": False,
                "labels_used_for_endpoint_selection": False,
                "metrics_computed": [],
            },
        },
    )
    _write_jsonl(
        snapshot / "intake_registry.jsonl",
        [{"drop_id": "drop-1", "intake_dir": str(intake.resolve()), "summary_sha256": _sha(intake_summary)}],
    )
    _write_jsonl(
        snapshot / "accumulator" / "provisional_runs.jsonl",
        [
            {
                "run_id": "run",
                "task": "task",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": 2,
                "generation_started_at_utc": generation,
                "source_sha256": "b" * 64,
            }
        ],
    )
    _write_json(
        snapshot / "accumulator" / "summary.json",
        {
            "inventory": {
                "drops": 1,
                "eligible_runs": 1,
                "eligible_endpoints": 2,
                "provisional_first960_runs": 1,
                "provisional_first960_endpoints": 2,
                "provisional_first960_structural_pairs": 1,
            }
        },
    )
    return state, snapshot


def test_snapshot_strict_temporal_boundary_is_exclusive(tmp_path: Path) -> None:
    state, snapshot = _snapshot(tmp_path)
    cards, pairs, metadata = load_snapshot(
        state,
        snapshot,
        "a" * 64,
        activation.dt.datetime.fromisoformat("2026-08-20T04:59:59+00:00"),
    )
    assert set(cards) == {"a", "b"}
    assert pairs == [("a", "b")]
    assert metadata["pair_strata"] == {"strict_post_activation_primary": 1}
    _cards_equal, _pairs_equal, equal = load_snapshot(
        state,
        snapshot,
        "a" * 64,
        activation.dt.datetime.fromisoformat("2026-08-20T05:00:00+00:00"),
    )
    assert equal["pair_strata"] == {"outcome_unread_support_only": 1}


def test_snapshot_rejects_any_extra_label_field(tmp_path: Path) -> None:
    state, snapshot = _snapshot(tmp_path)
    registry = next(iter(json.loads(line) for line in (snapshot / "intake_registry.jsonl").read_text().splitlines()))
    intake = Path(registry["intake_dir"])
    manifest = intake / "eligible_blind_manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    rows[0]["label"] = 1
    _write_jsonl(manifest, rows)
    summary = intake / "summary.json"
    value = json.loads(summary.read_text())
    value["outputs"]["eligible_blind_manifest_sha256"] = _sha(manifest)
    _write_json(summary, value)
    registry_value = json.loads((snapshot / "intake_registry.jsonl").read_text())
    registry_value["summary_sha256"] = _sha(summary)
    _write_jsonl(snapshot / "intake_registry.jsonl", [registry_value])
    with pytest.raises(EscrowError, match="schema mismatch"):
        load_snapshot(
            state,
            snapshot,
            "a" * 64,
            activation.dt.datetime.fromisoformat("2026-08-20T04:00:00+00:00"),
        )


def test_independent_inference_matches_producer(tmp_path: Path) -> None:
    arrays, _diagnostics, _scores = fit_bundle(_cards(), _pairs())
    bundle = tmp_path / "bundle.npz"
    np.savez_compressed(bundle, **arrays)
    produced, _ = score_cards(_cards(), load_bundle(bundle))
    verified, _ = score_independently(_cards(), bundle)
    for identifier in produced:
        for arm in produced[identifier]:
            assert abs(produced[identifier][arm] - verified[identifier][arm]) < 1e-12


def test_activation_refuses_unverified_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "bundle.npz"
    bundle.write_bytes(b"bundle")
    summary = tmp_path / "summary.json"
    verification = tmp_path / "verification.json"
    erratum = tmp_path / "erratum.json"
    protocol = tmp_path / "protocol.json"
    _write_json(
        summary,
        {
            "status": "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED",
            "source_commit": "b" * 40,
            "outputs": {"bundle_sha256": _sha(bundle)},
            "scope": {"v11_frozen_or_extension_read": False, "outcome_metrics_computed": []},
        },
    )
    _write_json(verification, {"status": "FAILED", "bundle_sha256": _sha(bundle), "scope": {"prospective_outcomes_read": False}})
    _write_json(
        erratum,
        {
            "status": "DECLARED_FREEZE_TIMESTAMP_INVALIDATED",
            "consequences": {"declared_frozen_at_utc_may_be_used_as_temporal_boundary": False},
        },
    )
    _write_json(
        protocol,
        {
            "protocol": activation.PROTOCOL,
            "source_paths": ["phase1/example.py"],
            "bundle": {
                "bundle_sha256": _sha(bundle),
                "build_source_commit": "b" * 40,
                "build_summary_sha256": _sha(summary),
                "independent_verification_sha256": _sha(verification),
            },
        },
    )
    monkeypatch.setattr(activation, "bind_source", lambda *_args: {"phase1/example.py": "c" * 64})
    args = argparse.Namespace(
        repo_root=tmp_path,
        source_commit="d" * 40,
        protocol=protocol,
        expect_protocol_sha256=_sha(protocol),
        bundle=bundle,
        expect_bundle_sha256=_sha(bundle),
        bundle_summary=summary,
        expect_bundle_summary_sha256=_sha(summary),
        bundle_verification=verification,
        expect_bundle_verification_sha256=_sha(verification),
        time_erratum=erratum,
        expect_time_erratum_sha256=_sha(erratum),
    )
    with pytest.raises(activation.ActivationError, match="verification"):
        activation.activate(args)
