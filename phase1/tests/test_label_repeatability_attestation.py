from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1 import label_repeatability_attestation as producer
from phase1 import verify_label_repeatability_attestation as verifier


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
        newline="\n",
    )


def regrade(card: str, original: float, rep: int, score: float) -> dict:
    return {
        "card_id": card,
        "competition": "task",
        "orig_graded": original,
        "rep": rep,
        "score": score,
    }


def synthetic_inputs(tmp_path: Path) -> tuple[Path, Path]:
    regrades = tmp_path / "regrades.jsonl"
    write_jsonl(
        regrades,
        [
            regrade("a", 0.90, 0, 0.89),
            regrade("a", 0.90, 0, 0.87),
            regrade("a", 0.90, 1, 0.88),
            regrade("b", 0.70, 0, 0.69),
            regrade("b", 0.70, 1, 0.71),
            regrade("c", 0.40, 0, 0.41),
            regrade("c", 0.40, 1, 0.39),
        ],
    )
    pairs = tmp_path / "pairs.jsonl"
    write_jsonl(
        pairs,
        [
            {"task": "task", "gap_raw": 0.00005},
            {"task": "task", "gap_raw": 0.002},
            {"task": "unmeasured", "gap_raw": 0.2},
        ],
    )
    card = tmp_path / "audit_card.json"
    write_json(
        card,
        {
            "protocol": "decision_corpus_audit_v1",
            "status": "VERIFIED_DECISION_CORPUS_AUDIT",
            "inputs": {
                "train:b0": {
                    "path": str(pairs.resolve()),
                    "hash_mode": "normalized_utf8_lf_v1",
                    "sha256_normalized_lf": producer.normalized_lf_sha256(pairs),
                }
            },
            "sets": {"train:b0": {"pairs": 3}},
        },
    )
    return regrades, card


def test_pava_pools_violations_and_carries_empty_bins() -> None:
    fitted = producer.fitted_agreement(
        [8, 2, 9, 0, 0, 0, 0, 0, 0],
        [10, 10, 10, 0, 0, 0, 0, 0, 0],
    )
    assert fitted[:3] == [0.5, 0.5, 0.9]
    assert fitted[3:] == [0.9] * 6


def test_duplicate_rep_is_audited_and_sensitivity_is_fixed(tmp_path: Path) -> None:
    regrades, _ = synthetic_inputs(tmp_path)
    records, metadata = producer.load_regrades([regrades])
    assert metadata["finite_successful_records"] == 7
    assert metadata["duplicate_card_rep_groups"] == 1
    assert metadata["conflicting_duplicate_card_rep_groups"] == 1
    assert len(producer.select_records(records, "all_successful_records")) == 7
    assert len(producer.select_records(records, "first_success_per_card_rep")) == 6
    assert len(producer.select_records(records, "last_success_per_card_rep")) == 6


def test_independent_verifier_rebuilds_every_mode_and_rejects_tampering(tmp_path: Path) -> None:
    regrades, card = synthetic_inputs(tmp_path)
    result = producer.build_attestation(
        [regrades],
        card,
        tmp_path,
        bootstrap_repetitions=2000,
        bootstrap_seed=20260814,
    )
    attestation = tmp_path / "attestation.json"
    write_json(attestation, result)
    verified = verifier.verify(attestation, Path.cwd())
    assert verified["status"] == "INDEPENDENTLY_VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2"
    assert verified["verified_modes"] == 3
    assert verified["verified_pair_sets"] == 1

    result["sensitivity_modes"]["all_successful_records"]["targets"]["train:b0"][
        "all_pairs"
    ]["transported_repeat_agreement"] -= 0.1
    write_json(attestation, result)
    with pytest.raises(verifier.VerificationError, match="scientific quantities"):
        verifier.verify(attestation, Path.cwd())


def test_verifier_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "import label_repeatability_attestation" not in source
    assert "from phase1 import label_repeatability_attestation" not in source
