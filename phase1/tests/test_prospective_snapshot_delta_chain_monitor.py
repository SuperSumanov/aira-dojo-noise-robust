from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]
PROTOCOL = ROOT / "phase1" / "prospective_snapshot_delta_chain_protocol_v1.json"
PRIMARY = ROOT / "phase1" / "verify_prospective_snapshot_delta.py"
GROUNDED = ROOT / "phase1" / "verify_prospective_snapshot_delta_grounded.py"
SCRIPT = (
    ROOT
    / "phase1"
    / "scripts"
    / "monitor_prospective_snapshot_delta_chain_20260831.sh"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_chain_protocol_freezes_seed_trigger_and_eight_hour_schedule():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["protocol"] == "prospective-snapshot-delta-chain-monitor-v1"
    assert protocol["seed"]["snapshot_sha256"] == (
        "0c0584b87140d9a3242f2aa59920829e07e9178749880e3c1f3bd0d065e0b07a"
    )
    assert protocol["seed"]["formal_manifest_sha256"] == (
        "69149e510d0bc519363dc48b57e578a3933757ae500e8e830ab60ff849d0bba0"
    )
    assert protocol["trigger"]["manual_snapshot_choice_allowed"] is False
    assert protocol["default_schedule"] == {
        "poll_seconds": 300,
        "max_polls": 96,
        "nominal_hours": 8,
    }
    assert protocol["resources"] == {
        "gpu": 0,
        "paid_api": 0,
        "model_fit": 0,
        "base_model_update": 0,
    }


def test_monitor_binds_exact_protocol_and_two_verifier_sources():
    source = SCRIPT.read_text(encoding="utf-8")
    assert f"protocol_sha={sha(PROTOCOL)}" in source
    assert f"primary_sha={sha(PRIMARY)}" in source
    assert f"grounded_sha={sha(GROUNDED)}" in source
    assert "__PROTOCOL_SHA256__" not in source
    assert "__PRIMARY_SHA256__" not in source
    assert "__GROUNDED_SHA256__" not in source
    assert source.index("source /uac/y24/yzyang4/env_setup.sh") < source.index(
        "set -u"
    )
    assert "export PYTHONDONTWRITEBYTECODE=1" in source


def test_monitor_requires_primary_and_grounded_ab_before_state_promotion():
    source = SCRIPT.read_text(encoding="utf-8")
    required = [
        "primary_a",
        "primary_b",
        'cmp "${current_output}/receipt_a.json" "${current_output}/receipt_b.json"',
        "grounded_a",
        "grounded_b",
        'cmp "${current_output}/grounded_a.json" "${current_output}/grounded_b.json"',
        'chmod -R a-w "${current_output}"',
        'mv "${state_tmp}" "${state_file}"',
    ]
    for marker in required:
        assert marker in source
    assert source.index('cmp "${current_output}/receipt_a.json"') < source.index(
        'cmp "${current_output}/grounded_a.json"'
    )
    assert source.index('cmp "${current_output}/grounded_a.json"') < source.index(
        'chmod -R a-w "${current_output}"'
    )
    assert source.index('chmod -R a-w "${current_output}"') < source.index(
        'mv "${state_tmp}" "${state_file}"'
    )


def test_monitor_failure_path_does_not_promote_state():
    source = SCRIPT.read_text(encoding="utf-8")
    handler = source[source.index("on_error()") : source.index("trap on_error ERR")]
    assert "state_promoted=false" in handler
    assert "MANIFEST_SHA256" in handler
    assert "chmod -R a-w" in handler
    assert 'mv "${state_tmp}" "${state_file}"' not in handler
    assert "same_root_repair_allowed" not in source
    assert "HCE" not in source
    assert "multi-fidelity" not in source
    assert "lookahead" not in source


def test_monitor_has_timeout_symlink_and_read_only_gates():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'timeout 1800s "$@"' in source
    assert source.count('-type l -print -quit') >= 2
    assert 'test -z "$(find "${current_output}" -type l -print -quit)"' in source


def test_monitor_shell_syntax():
    completed = subprocess.run(
        ["bash", "-n"],
        check=False,
        capture_output=True,
        input=SCRIPT.read_bytes().replace(b"\r", b""),
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8")
