from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.verify_release_prepared_text_successor_v2 import VerifyError, verify


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "release_prepared_text_successor_v2.json"
RUNNER = (
    ROOT
    / "phase1"
    / "scripts"
    / "run_release_prepared_text_successor_v2_20260902.sh"
)
PREFLIGHT = (
    ROOT / "phase1" / "V11_RELEASE_PREPARED_TEXT_SUCCESSOR_V2_PREFLIGHT_20260902.md"
)
FAILURE_RECEIPT = (
    ROOT / "phase1" / "release_prepared_text_successor_v2_failure_receipt_20260902.json"
)
CURRENT = ROOT / "phase1" / "CURRENT_DIRECTION.md"


def contract_sha() -> str:
    return hashlib.sha256(CONTRACT.read_bytes()).hexdigest()


def fixture(root: Path) -> None:
    values = {
        "aptos2019-blindness-detection/prepared/sample_submission.csv": (
            "id_code,diagnosis\na,0\n"
        ),
        "aptos2019-blindness-detection/prepared/test.csv": "id_code\nb\n",
        "aptos2019-blindness-detection/prepared/train.csv": (
            "id_code,diagnosis\nc,1\n"
        ),
        "histopathologic-cancer-detection/prepared/sample_submission.csv": (
            "id,label\nd,0\n"
        ),
        "histopathologic-cancer-detection/prepared/train_labels.csv": (
            "id,label\ne,1\n"
        ),
    }
    for relative, content in values.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def test_contract_freezes_exact_file_set_before_download() -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_AFTER_ACCESS_PASS_BEFORE_DOWNLOAD"
    assert len(value["requested_files"]) == 5
    assert [item["filename"] for item in value["requested_files"]] == [
        "sample_submission.csv",
        "test.csv",
        "train.csv",
        "sample_submission.csv",
        "train_labels.csv",
    ]
    assert value["staging_contract"]["promotion_before_verification"] is False
    assert value["interpretation_boundary"]["api_access_is_redistribution_permission"] is False


def test_independent_verifier_emits_only_hashes_and_counts(tmp_path: Path) -> None:
    prepared = tmp_path / "prepared"
    fixture(prepared)
    output = tmp_path / "verification.json"
    result = verify(CONTRACT, contract_sha(), prepared, output)
    assert result["status"] == "PASS"
    assert result["totals"] == {
        "competitions": 2,
        "files": 5,
        "bytes": sum(path.stat().st_size for path in prepared.rglob("*.csv")),
        "rows_excluding_headers": 5,
    }
    rendered = output.read_text(encoding="utf-8")
    for raw_value in ("a,0", "b\n", "c,1", "d,0", "e,1"):
        assert raw_value not in rendered
    assert str(tmp_path) not in rendered


def test_verifier_rejects_extra_file_bad_header_and_credential_shape(tmp_path: Path) -> None:
    prepared = tmp_path / "prepared"
    fixture(prepared)
    extra = prepared / "aptos2019-blindness-detection" / "prepared" / "extra.csv"
    extra.write_text("x\ny\n", encoding="utf-8")
    with pytest.raises(VerifyError, match="file-set mismatch"):
        verify(CONTRACT, contract_sha(), prepared, tmp_path / "extra.json")
    extra.unlink()

    train = prepared / "aptos2019-blindness-detection" / "prepared" / "train.csv"
    train.write_text("wrong,header\nc,1\n", encoding="utf-8")
    with pytest.raises(VerifyError, match="header mismatch"):
        verify(CONTRACT, contract_sha(), prepared, tmp_path / "header.json")
    shaped = "sk" + "-or-v1-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
    train.write_text(f"id_code,diagnosis\n{shaped},1\n", encoding="utf-8")
    with pytest.raises(VerifyError, match="credential-shaped"):
        verify(CONTRACT, contract_sha(), prepared, tmp_path / "credential.json")


def test_runner_is_bounded_exact_commit_and_never_promotes() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "umask 077" in text
    assert "RELEASE_PREPARED_TEXT_PUBLIC_COMMIT" in text
    assert contract_sha() in text
    assert text.count('"${kaggle_bin}" competitions download') == 1
    assert 'for index in "${!competitions[@]}"' in text
    assert 'timeout 600s strace' in text
    assert '[[ "${#payloads[@]}" == 1 ]]' in text
    assert '[[ "${#members[@]}" == 1 ]]' in text
    assert '[[ "${members[0]}" == "${filename}" ]]' in text
    assert '[[ ! -e "${data_root}/${task}/prepared" ]]' in text
    assert "active_prepared_root_modified\": False" in text
    assert "cp -- \"${private}/prepared\"" not in text
    assert "prospective_decision_v1" in text
    assert text.count('"${python_bin}" -m phase1.verify_release_prepared_text_successor_v2') == 2


def test_preflight_contains_all_thirteen_items_and_interpretation_boundary() -> None:
    text = PREFLIGHT.read_text(encoding="utf-8")
    for number in range(1, 14):
        assert f"{number}. **" in text
    assert "not competition\n    data redistribution permission" in text
    assert "must never enter Git/LFS" in text


def test_failure_receipt_preserves_listing_download_distinction() -> None:
    receipt = json.loads(FAILURE_RECEIPT.read_text(encoding="utf-8"))
    current = CURRENT.read_text(encoding="utf-8")
    assert receipt["exact_public_commit"] == (
        "7b82b182247b54e616124c25d8efbd82785a14f4"
    )
    assert receipt["access_probe_before_freeze"]["file_listing_requests_succeeded"] == 2
    formal = receipt["formal_execution"]
    assert formal["kaggle_cli_process_rc_for_request_0"] == 0
    assert formal["application_level_status"] == 403
    assert formal["downloaded_files"] == 0
    assert formal["prepared_files"] == 0
    assert formal["active_prepared_root_modified"] is False
    assert receipt["interpretation"]["metadata_listing_proves_download_authorization"] is False
    assert receipt["interpretation"]["automatic_retry_allowed"] is False
    assert receipt["interpretation"]["prepared_text_coverage_remains"] == "23/25"
    assert receipt["security"]["prospective_values_or_identities_read"] is False
    assert "## 0L0m." in current
    assert "requests/downloaded/prepared=`1/0/0`" in current
