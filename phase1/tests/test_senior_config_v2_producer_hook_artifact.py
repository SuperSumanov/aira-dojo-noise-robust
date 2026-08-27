from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
PATCH = ROOT / "upstream_patches" / "0001-Add-prospective-config-v2-producer-hook-18-tests.patch"
RESULT = ROOT / "results" / "senior_config_v2_producer_hook_20260827_56a3e4b"
PATCH_SHA256 = "56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5"


def receipt_fields() -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (RESULT / "receipt.txt").read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        fields[key] = value
    return fields


def test_patch_bytes_and_base_contract_are_frozen() -> None:
    raw = PATCH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PATCH_SHA256
    text = raw.decode("utf-8")
    assert "Subject: [PATCH] Add prospective config-v2 producer hook (18 tests)" in text
    assert "DOJO_CONFIG_V2_SIDECAR" in text
    assert "DOJO_GENERATOR_RELEASE" in text
    assert "producer.config_v2.jsonl" in text
    assert "maybe_emit_for_resolved_run" in text
    assert "os.link(temporary, path)" in text


def test_remote_receipt_records_complete_linux_verification() -> None:
    fields = receipt_fields()
    assert fields["status"] == "ENGINEERING_PATCH_VERIFIED"
    assert fields["base_commit"] == "61459c0a1248900079dafed7c505afa87e476b40"
    assert fields["reference_commit"] == "f5955b0b887e6c89244fd5ac5b8b17de7b1ae88b"
    assert fields["patch_sha256"] == PATCH_SHA256
    assert fields["focused"] == "19 passed in 0.26s"
    assert fields["full_tests_rc"] == "0"
    assert fields["full_tests"] == "84 passed, 1 skipped, 26 warnings in 32.69s"
    assert fields["filename_secret_hits"] == "0"
    assert fields["blob_secret_hits"] == "0"
    assert fields["gpu_jobs_submitted"] == "0"
    assert fields["archives_or_outcomes_read"] == "false"
    assert fields["labels_or_predictions_read"] == "false"


def test_cross_implementation_receipt_is_exact() -> None:
    payload = json.loads((RESULT / "crosscheck.log").read_text(encoding="utf-8"))
    assert payload == {
        "equivalent_cases": 128,
        "rejected_cases": 4,
        "status": "EXACT_ROW_BYTES_EQUIVALENT",
    }


def test_remote_manifest_hash_is_preserved() -> None:
    line = (RESULT / "remote_SHA256SUMS.sha256").read_text(encoding="utf-8").strip()
    digest, remote_path = line.split(maxsplit=1)
    assert digest == "fbb9536c760c9a14ba9e7da044d1f32fe7f748ff54298f27fb1951bbe743c2b0"
    assert remote_path.endswith("/verify_fa2151b_v4/SHA256SUMS")


def test_local_package_manifest_covers_every_artifact() -> None:
    manifest = RESULT / "SHA256SUMS"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "816ca815e9614aaa762227a58f8f7d8a46e3c5bf218d36bf3aa807ddcf3f1b53"
    )
    recorded: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        assert name not in recorded
        recorded[name] = digest
    expected = {
        path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(recorded) == expected
    for name, digest in recorded.items():
        assert hashlib.sha256((RESULT / name).read_bytes()).hexdigest() == digest
