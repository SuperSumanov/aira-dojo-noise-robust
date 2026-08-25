from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.verify_decision_predictor_estimand_panel import (
    EstimandPanelVerificationError,
    verify,
)


ROOT = Path(__file__).parents[2]
CONTRACT = ROOT / "phase1" / "decision_predictor_estimand_panel_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_contract(path: Path, value: dict) -> str:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return sha256(path)


def test_real_panel_verifies_against_bound_evidence() -> None:
    receipt = verify(CONTRACT, sha256(CONTRACT), ROOT, "a" * 40)
    assert receipt["status"] == "INDEPENDENT_ESTIMAND_PANEL_PASS"
    assert all(receipt["checks"].values())
    assert receipt["access_and_compute"][
        "prospective_label_grade_outcome_or_winner_orientation_read"
    ] is False


def test_panel_rejects_headline_hierarchy_tamper(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["generic_headline"]["aggregation_order"][1:3] = reversed(
        value["generic_headline"]["aggregation_order"][1:3]
    )
    path = tmp_path / "contract.json"
    contract_sha = write_contract(path, value)
    with pytest.raises(EstimandPanelVerificationError, match="headline hierarchy"):
        verify(path, contract_sha, ROOT, "a" * 40)


def test_panel_rejects_existing_primary_supersession(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["authority"]["supersedes_existing_experiment_primary"] = True
    path = tmp_path / "contract.json"
    contract_sha = write_contract(path, value)
    with pytest.raises(EstimandPanelVerificationError, match="authority firewall"):
        verify(path, contract_sha, ROOT, "a" * 40)


def test_panel_rejects_rescue_view(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["required_nonrescuing_panel"][2][
        "may_rescue_generic_headline_or_existing_primary"
    ] = True
    path = tmp_path / "contract.json"
    contract_sha = write_contract(path, value)
    with pytest.raises(EstimandPanelVerificationError, match="rescue lock"):
        verify(path, contract_sha, ROOT, "a" * 40)


def test_panel_rejects_contract_hash_mismatch() -> None:
    with pytest.raises(EstimandPanelVerificationError, match="contract SHA"):
        verify(CONTRACT, "b" * 64, ROOT, "a" * 40)
