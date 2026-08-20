import argparse
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1.verify_wl_graph_escrow_append import (
    ARMS,
    AppendVerificationError,
    ENDPOINT_FIELDS,
    verify,
)


SCORER_COMMIT = "a" * 40
PRIOR_SNAPSHOT = "b" * 64
CURRENT_SNAPSHOT = "c" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _endpoint(identifier: str, run: str, task: str, stratum: str, value: float) -> dict[str, str]:
    row = {
        "card_id": identifier,
        "task": task,
        "run_id": run,
        "parent": f"parent-{run}",
        "code_sha256": hashlib.sha256(identifier.encode()).hexdigest(),
        "generation_started_at_utc": "2026-08-21T00:00:00Z",
        "temporal_stratum": stratum,
    }
    row.update({arm: format(value + index / 10, ".17g") for index, arm in enumerate(ARMS)})
    return row


def _pair(left: dict[str, str], right: dict[str, str]) -> dict:
    row = {
        "task": left["task"],
        "run_id": left["run_id"],
        "parent": left["parent"],
        "left": left["card_id"],
        "right": right["card_id"],
        "temporal_stratum": left["temporal_stratum"],
        "pair_key_sha256": hashlib.sha256(
            "\0".join((left["card_id"], right["card_id"])).encode()
        ).hexdigest(),
    }
    for arm in ARMS:
        margin = float(left[arm]) - float(right[arm])
        row[f"{arm}_margin_left_minus_right"] = margin
        row[f"{arm}_selected"] = left["card_id"] if margin > 0 else right["card_id"] if margin < 0 else "tie"
    return row


def _write_artifact(root: Path, snapshot: str, endpoints: list[dict[str, str]], pairs: list[dict]) -> None:
    root.mkdir(parents=True)
    endpoint_path = root / "endpoint_scores.csv"
    with endpoint_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENDPOINT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(endpoints)
    pair_path = root / "pair_predictions.jsonl"
    pair_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in pairs),
        encoding="utf-8",
    )
    run_strata = {}
    for row in endpoints:
        run_strata[row["run_id"]] = row["temporal_stratum"]
    inventory = {
        "endpoints": len(endpoints),
        "runs": len(run_strata),
        "tasks": len({row["task"] for row in endpoints}),
        "pairs": len(pairs),
        "run_strata": dict(sorted({s: list(run_strata.values()).count(s) for s in set(run_strata.values())}.items())),
        "pair_strata": dict(sorted({s: [p["temporal_stratum"] for p in pairs].count(s) for s in {p["temporal_stratum"] for p in pairs}}.items())),
        "ties": {arm: sum(row[f"{arm}_selected"] == "tie" for row in pairs) for arm in ARMS},
    }
    summary = {
        "status": "PROSPECTIVE_WL_GRAPH_PREDICTION_ESCROW_COMPLETE",
        "protocol": "prospective-wl-graph-escrow-v1",
        "source_commit": SCORER_COMMIT,
        "source_file_sha256": {"phase1/scorer.py": "d" * 64},
        "activation": {"receipt_sha256": "e" * 64, "activated_at_utc": "2026-08-20T00:00:00Z"},
        "inputs": {
            "snapshot_sha256": snapshot,
            "protocol_sha256": "1" * 64,
            "bundle_sha256": "2" * 64,
            "bundle_summary_sha256": "3" * 64,
            "bundle_verification_sha256": "4" * 64,
        },
        "inventory": inventory,
        "outputs": {
            "endpoint_scores_sha256": _sha(endpoint_path),
            "pair_predictions_sha256": _sha(pair_path),
        },
        "scope": {
            "prospective_outcomes_read": False,
            "temporal_label_vault_read": False,
            "v11_frozen_or_extension_read": False,
            "effect_metrics_computed": [],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        name: _sha(root / name)
        for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
    }
    (root / "sha256_manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> argparse.Namespace:
    support = "outcome_unread_support_only"
    strict = "strict_post_activation_primary"
    old_a = _endpoint("a", "old-run", "old-task", support, 2.0)
    old_b = _endpoint("b", "old-run", "old-task", support, 1.0)
    new_c = _endpoint("c", "new-run", "new-task", strict, 4.0)
    new_d = _endpoint("d", "new-run", "new-task", strict, 3.0)
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    _write_artifact(prior, PRIOR_SNAPSHOT, [old_a, old_b], [_pair(old_a, old_b)])
    _write_artifact(
        current,
        CURRENT_SNAPSHOT,
        [old_a, old_b, new_c, new_d],
        [_pair(old_a, old_b), _pair(new_c, new_d)],
    )
    independent = tmp_path / "independent.json"
    independent.write_text(
        json.dumps(
            {
                "status": "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED",
                "artifact_summary_sha256": _sha(current / "summary.json"),
                "snapshot_sha256": CURRENT_SNAPSHOT,
                "endpoints": 4,
                "pairs": 2,
                "prospective_outcomes_read": False,
                "effect_metrics_computed": [],
                "maximum_absolute_score_difference": {arm: 0.0 for arm in ARMS},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    producer_trace = tmp_path / "producer.strace"
    verifier_trace = tmp_path / "verifier.strace"
    producer_trace.write_text('1 openat(AT_FDCWD, "/safe/input", O_RDONLY) = 3\n', encoding="utf-8")
    verifier_trace.write_text('2 openat(AT_FDCWD, "/safe/artifact", O_RDONLY) = 3\n', encoding="utf-8")
    return argparse.Namespace(
        prior_artifact=prior,
        current_artifact=current,
        current_independent_verification=independent,
        expect_scorer_commit=SCORER_COMMIT,
        expect_prior_summary_sha256=_sha(prior / "summary.json"),
        expect_prior_snapshot_sha256=PRIOR_SNAPSHOT,
        expect_current_snapshot_sha256=CURRENT_SNAPSHOT,
        trace=[producer_trace, verifier_trace],
        scan_root=[current, independent, producer_trace, verifier_trace],
    )


def test_accepts_exact_blind_append(tmp_path: Path) -> None:
    receipt = verify(_fixture(tmp_path))
    assert receipt["added"] == {"endpoints": 2, "runs": 1, "pairs": 1}
    assert receipt["strict_post_activation_inventory"]["runs"] == 1
    assert receipt["strict_post_activation_inventory"]["pairs"] == 1
    assert receipt["fixed_effect_eligibility_gate"]["passed"] is False
    assert receipt["effect_metrics_computed"] == []


def test_rejects_changed_prior_prediction(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    path = args.current_artifact / "endpoint_scores.csv"
    text = path.read_text(encoding="utf-8").replace("2,2.1000000000000001", "9,2.1000000000000001", 1)
    path.write_text(text, encoding="utf-8")
    summary = json.loads((args.current_artifact / "summary.json").read_text())
    summary["outputs"]["endpoint_scores_sha256"] = _sha(path)
    (args.current_artifact / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        name: _sha(args.current_artifact / name)
        for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
    }
    (args.current_artifact / "sha256_manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    independent = json.loads(args.current_independent_verification.read_text())
    independent["artifact_summary_sha256"] = _sha(args.current_artifact / "summary.json")
    args.current_independent_verification.write_text(json.dumps(independent) + "\n", encoding="utf-8")
    with pytest.raises(AppendVerificationError, match="prior endpoint row changed"):
        verify(args)


def test_rejects_forbidden_trace_observation(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    args.trace[0].write_text(
        '1 openat(AT_FDCWD, "/research/prospective_decision_v1/outcome_vault/x", O_RDONLY) = 3\n',
        encoding="utf-8",
    )
    with pytest.raises(AppendVerificationError, match="forbidden path observed"):
        verify(args)


def test_rejects_credential_shaped_output(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    suspect = tmp_path / "suspect.log"
    suspect.write_text("sk-" + "a" * 24 + "\n", encoding="utf-8")
    args.scan_root.append(suspect)
    with pytest.raises(AppendVerificationError, match="credential-shaped content"):
        verify(args)
