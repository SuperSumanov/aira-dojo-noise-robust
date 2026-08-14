from __future__ import annotations

import json
from argparse import Namespace

import pytest

from phase1.balanced_continuation_real_adapter_mock import run_smoke
from phase1.balanced_continuation_real_contract import RealContractError
from phase1.verify_balanced_continuation_real_adapter_mock import (
    MockVerificationError,
    verify,
)


def test_process_boundary_smoke_and_independent_verifier(tmp_path) -> None:
    root = tmp_path / "real-adapter-mock"
    run_smoke(
        Namespace(output=str(root.resolve()), source_commit="1" * 40, test_fixture_mode=True)
    )
    receipt_path = tmp_path / "verification.json"
    result = verify(Namespace(input=str(root.resolve()), output=str(receipt_path.resolve())))
    assert result["status"] == "VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK"
    assert result["candidate_processes"] == 2
    assert result["operator_calls"] == 1
    assert result["retries"] == 0
    assert result["visible_dval_fields"] == 0
    assert result["dtest_rows_read"] == 0
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == result


def test_independent_verifier_rejects_worker_visible_dval_injection(tmp_path) -> None:
    root = tmp_path / "tampered-real-adapter-mock"
    run_smoke(
        Namespace(output=str(root.resolve()), source_commit="2" * 40, test_fixture_mode=True)
    )
    visible_path = root / "receipts" / "visible_000.json"
    visible = json.loads(visible_path.read_text(encoding="utf-8"))
    visible["dval_score"] = 0.99
    visible_path.write_text(json.dumps(visible), encoding="utf-8")
    with pytest.raises((MockVerificationError, RealContractError), match="visible step keys differ"):
        verify(Namespace(input=str(root.resolve()), output=None))
