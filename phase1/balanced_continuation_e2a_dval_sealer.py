"""Isolated D_val scorer/sealer for one balanced-continuation E2-A artifact."""

from __future__ import annotations

import argparse
import os
import pathlib
import stat
import sys

from phase1.balanced_continuation_e2a_scoring import (
    ScoreError, TASK_SPECS, atomic_json, canonical_json, checked_json,
    evaluator_bundle_sha256, file_sha256, score_submission, sha256_bytes,
)
from phase1.balanced_continuation_real_contract import (
    SEALED_LABEL_SCHEMA, validate_sealed_label_receipt, validate_worker_contract,
)


COMMITMENT_SCHEMA = "balanced-continuation-sealed-commitment-v1"


def run(args: argparse.Namespace) -> tuple[dict, dict]:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract).resolve()))
    if args.task not in TASK_SPECS:
        raise ScoreError("unsupported E2-A task")
    bundle_sha = evaluator_bundle_sha256(pathlib.Path(__file__))
    if bundle_sha != contract["sealed_label_evaluator_executable_sha256"]:
        raise ScoreError("D_val evaluator bundle differs")
    labels = pathlib.Path(args.labels).resolve()
    if not labels.is_file() or labels.name != f"{args.task}.csv":
        raise ScoreError("D_val label path differs")
    if os.name == "posix" and stat.S_IMODE(labels.stat().st_mode) != 0o600:
        raise ScoreError("D_val labels are not mode 0600")
    public_sample = pathlib.Path(args.public_sample).resolve()
    expected_sample = pathlib.Path(contract["public_data_root"]) / args.task / "sample_submission.csv"
    if not public_sample.is_file():
        raise ScoreError("public sample submission path differs")
    if os.name == "posix" and (
        public_sample != expected_sample.resolve()
        or stat.S_IMODE(public_sample.stat().st_mode) != 0o444
    ):
        raise ScoreError("public sample submission path/mode differs")
    artifact = pathlib.Path(args.artifact).resolve()
    scored = score_submission(artifact, labels, public_sample, args.task)
    score = scored["score"]
    orientation = int(TASK_SPECS[args.task]["orientation"])
    receipt = {
        "schema_version": SEALED_LABEL_SCHEMA,
        "rollout_id": args.rollout_id, "workspace_token": args.workspace_token,
        "task": args.task, "execution_ordinal": args.ordinal,
        "artifact_sha256": file_sha256(artifact) if artifact.is_file() else None,
        "submission_valid": scored["submission_valid"], "dval_score": score,
        "dval_utility": None if score is None else orientation * score,
        "orientation": orientation,
        "split_manifest_sha256": contract["split_manifest_sha256_opaque"],
        "evaluator_executable_sha256": bundle_sha,
        "grade_return_code": 0 if scored["submission_valid"] else 2,
        "private_bytes_exposed_to_candidate": 0, "dtest_rows_read": 0,
        "file_mode": 0o600,
    }
    validate_sealed_label_receipt(receipt, contract)
    sealed = pathlib.Path(args.sealed_receipt).resolve()
    atomic_json(sealed, receipt, mode=0o600)
    commitment = {
        "schema_version": COMMITMENT_SCHEMA,
        "rollout_id": args.rollout_id, "workspace_token": args.workspace_token,
        "task": args.task, "execution_ordinal": args.ordinal,
        "sealed_label_receipt_sha256": sha256_bytes(sealed.read_bytes()),
    }
    return receipt, commitment


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract", required=True); ap.add_argument("--task", required=True)
    ap.add_argument("--rollout-id", required=True); ap.add_argument("--workspace-token", required=True)
    ap.add_argument("--ordinal", required=True, type=int); ap.add_argument("--artifact", required=True)
    ap.add_argument("--labels", required=True); ap.add_argument("--public-sample", required=True)
    ap.add_argument("--sealed-receipt", required=True)
    return ap


def main() -> int:
    try:
        _, commitment = run(parser().parse_args())
    except (ScoreError, OSError, ValueError) as exc:
        print(f"E2A_DVAL_SEALER_ERROR: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical_json(commitment) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
