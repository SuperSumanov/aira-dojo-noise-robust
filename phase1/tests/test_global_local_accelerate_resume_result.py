import csv
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from phase1.verify_global_local_accelerate_resume import verify


REPO = Path(__file__).resolve().parents[2]
RESULT = REPO / "phase1/results/global_local_accelerate_resume_20260904"
SUMMARY_SHA = "99601e0ca6440952f789690b5e118a0887cfec54ff2355f376fc849ea2c7bc7b"


def test_saved_receipts_reverify_without_binary_or_torch():
    current = verify(RESULT, SUMMARY_SHA, binary=False)
    saved = json.loads((RESULT / "independent_export_receipt.json").read_text())
    assert current == saved
    binary = json.loads((RESULT / "independent_binary_receipt.json").read_text())
    assert binary["framework_binary_checkpoints_decoded"] == current["checkpoint_receipts_checked"] == 36
    assert binary["verified_resume_rank_states"] == current["verified_resume_rank_states"] == 24
    assert binary["resume_cases"] == current["resume_cases"]
    assert binary["all_rank_forward_calls"] == current["all_rank_forward_calls"] == 612
    assert binary["verifier_sha256"] == current["verifier_sha256"]


def test_sources_and_minimal_postrun_decoder_correction_bound():
    summary = json.loads((RESULT / "summary.json").read_text())
    for name, digest in summary["sources"].items():
        raw = (REPO / "phase1" / name).read_bytes()
        if name == "verify_global_local_accelerate_resume.py":
            # Only the independent decoder changed AFTER the trajectories ended.
            # Reconstruct its original bytes, retaining the failed version's SHA.
            before = (b'        numpy_core = getattr(np, "_core", np.core)\n'
                      b'        allow = [numpy_core.multiarray._reconstruct, np.ndarray, np.dtype, type(np.dtype("uint32"))]\n')
            after = (b'        from numpy.core.multiarray import _reconstruct\n'
                     b'        allow = [_reconstruct, np.ndarray, np.dtype, type(np.dtype("uint32"))]\n')
            assert raw.count(after) == 1
            raw = raw.replace(after, before)
            assert digest == "6791f220e744b51ac7bb3b26bfc69c6eec01d398880cad2576c4c62dffeab4ff"
        assert hashlib.sha256(raw).hexdigest() == digest


def test_exec_receipt_is_complete_and_zero_gpu():
    receipt = json.loads((RESULT / "execution_exit.json").read_text())
    assert receipt["returncode"] == 0 and receipt["timed_out"] is False
    assert receipt["GPU"] == receipt["paid_API"] == receipt["research_model_fits"] == 0
    assert 0 < receipt["elapsed_seconds"] < 1200
    assert receipt["environment_overrides"]["CUDA_VISIBLE_DEVICES"] == ""


def test_per_trajectory_ledger_has_commit_budget_and_fixed_knobs():
    summary = json.loads((RESULT / "summary.json").read_text())
    with (RESULT / "run_ledger.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(summary["trials"]) == 20
    for row, trial in zip(rows, summary["trials"]):
        assert row["name"] == trial["name"]
        assert row["base_commit"] == summary["base_commit"]
        assert row["execution_source_sha256"] == summary["sources"]["global_local_accelerate_resume_validation.py"]
        assert int(row["world"]) == trial["world"]
        assert row["arm"] == trial["arm"] and int(row["seed"]) == trial["seed"]
        assert int(row["optimizer_updates"]) == trial["optimizer_updates"]
        assert int(row["all_rank_forward_calls"]) == trial["new_forwards"]
        assert int(row["matrix_max_wall_seconds"]) == 1200
        assert int(row["model_parameter_count"]) == 2
        assert float(row["peak_learning_rate"]) == 1e-5
        assert row["GPU"] == row["paid_API"] == row["research_model_fits"] == "0"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.mark.parametrize("fault,expected", [
    ("summary_bytes", "summary_hash"), ("missing_rank", "inventory"),
    ("target_reads", "true_label_access"), ("wrong_sync", "sync_or_lr"),
    ("model_state", "rank_parameter"), ("missing_resume_trial", "trajectory_matrix"),
])
def test_corruption_and_rehashed_semantic_faults_fail(tmp_path, fault, expected):
    root = tmp_path / "copy"
    shutil.copytree(RESULT, root)
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary_sha = SUMMARY_SHA
    trial = summary["trials"][0]
    trial_root = root / trial["name"]
    trajectory_path = trial_root / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    if fault == "summary_bytes":
        summary_path.write_bytes(summary_path.read_bytes() + b" ")
    elif fault == "missing_rank":
        (trial_root / "checkpoint-4/observed_1.json").unlink()
    else:
        if fault == "missing_resume_trial":
            summary["trials"].pop()
        elif fault == "target_reads":
            trajectory["states"][0]["true_target_reads_this_process"] += 1
        else:
            directory = trial_root / "checkpoint-4"
            observed_path = directory / "observed_0.json"
            observed = json.loads(observed_path.read_text())
            if fault == "wrong_sync":
                observed["events"][0]["synchronize"] = True
            else:
                observed["state"]["model"] = "a" * 64
            dump(observed_path, observed)
            manifest_path = directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][observed_path.name] = {"sha256": digest(observed_path), "bytes": observed_path.stat().st_size}
            dump(manifest_path, manifest)
            trajectory["saved"][-1]["manifest_sha256"] = digest(manifest_path)
        dump(trajectory_path, trajectory)
        trial["trajectory_sha256"] = digest(trajectory_path)
        dump(summary_path, summary)
        summary_sha = digest(summary_path)
    with pytest.raises(ValueError, match=expected):
        verify(root, summary_sha, binary=False)
