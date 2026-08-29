from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / "phase1"
RESULT = PHASE / "results/yield_guarded_breadth_feasibility_development_20260829_0e62c9c"
PRODUCER = PHASE / "develop_yield_guarded_breadth_feasibility_v2.py"
VERIFIER = PHASE / "verify_yield_guarded_breadth_development_v2.py"
PREFLIGHT = PHASE / "实验记录/2026-08-29/YieldGuardedBreadthFeasibility_v2_开发预检.md"
PRIOR = PHASE / "results/historical_run_split_breadth_pareto_20260829_6cdcc92/aggregate_result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_frozen_hashes() -> None:
    assert sha(PRODUCER) == "0e62c9c3bf15b689caf98ee73b2f22d1134e99b6c212960c958bd7021570942e"
    assert sha(VERIFIER) == "5079a6350a5f4e83a028f43cfa99e8217abeb486acab8ae345d371f607a9610c"
    assert sha(PREFLIGHT) == "3d3c5fa54877ef830c9fff67ae06a93330bbcfcd12448c8cbc6639deb5ad900b"
    assert sha(RESULT / "aggregate_result.json") == "e43831946643d60654bb10b834278fd480c97292fcf91ea6dfa95962c77c191d"
    assert sha(RESULT / "independent_aggregate_verification.json") == "c3680fb2a767ad51a3b3c1109f102ec56556d17ec33e041d248cdb9e22f06a2d"


def test_checked_in_result_keeps_development_boundary_and_all_gates() -> None:
    value = json.loads((RESULT / "aggregate_result.json").read_text())
    assert value["status"] == "DEVELOPMENT_AFTER_BOTH_RUN_SPLIT_FOLDS_READOUT"
    assert value["all_folds_feasible_and_all_development_gates_pass"] is True
    assert value["scope"]["external_confirmation"] is False
    assert value["scope"]["identities_emitted"] is False
    for fold in ("fold0", "fold1"):
        item = value["folds"][fold]
        assert item["status"] == "FEASIBLE_WITNESS"
        assert item["solver_threads_requested"] == 1
        assert item["solver_random_seed"] == 0
        assert item["solver_mip_gap"] == 0.0
        assert all(item["gates"].values())


def test_independent_verification_is_explicitly_aggregate_only() -> None:
    value = json.loads((RESULT / "independent_aggregate_verification.json").read_text())
    assert value["classification"] == "DEVELOPMENT_AGGREGATE_INDEPENDENT_VERIFICATION_PASS"
    assert value["ab_byte_exact"] is True
    assert value["boundary"] == {
        "aggregate_gates_recomputed": True,
        "external_confirmation": False,
        "non_importing": True,
        "private_witness_recomputed": False,
    }


def test_non_importing_verifier_reproduces_checked_in_bytes(tmp_path: Path) -> None:
    output = tmp_path / "verification.json"
    subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--result",
            str(RESULT / "aggregate_result.json"),
            "--ab-result",
            str(RESULT / "aggregate_result.json"),
            "--prior",
            str(PRIOR),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.read_bytes() == (RESULT / "independent_aggregate_verification.json").read_bytes()


def test_v1_failure_is_preserved_as_no_readout() -> None:
    rows = dict(
        line.split("=", 1)
        for line in (RESULT / "v1_thread_preflight_violation.txt").read_text().splitlines()
    )
    assert rows["status"] == "STOPPED_BEFORE_READOUT"
    assert rows["threads_observed"] == "20"
    assert rows["result_file_present"] == "false"


def test_package_manifest() -> None:
    entries = {}
    for line in (RESULT / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        entries[name] = digest
    expected = {path.name for path in RESULT.iterdir() if path.name != "SHA256SUMS"}
    assert set(entries) == expected
    for name, digest in entries.items():
        assert sha(RESULT / name) == digest
