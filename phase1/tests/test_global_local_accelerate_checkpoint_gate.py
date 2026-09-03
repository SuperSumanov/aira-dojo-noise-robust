import copy
import json
from pathlib import Path

import pytest

from phase1 import global_local_accelerate_checkpoint_gate as gate


def fixture(root):
    root.mkdir()
    binding = {"scope": "synthetic-two-parameter-cpu-only", "world": 2, "arm": "G_to_L", "seed": 6,
        "base_commit": "dca429b85507cfcd96b256f65e2df2ac15be7b9a",
        **{name: "a" * 64 for name in ("plan_sha256", "input_sha256", "runtime_sha256", "sources_sha256")}}
    for name in gate.expected_files(2):
        path = root / name
        if name.startswith("observed_"):
            rank = int(name.split("_")[1].split(".")[0])
            path.write_text(json.dumps({"binding": binding, "rank": rank, "completed_steps": 2,
                "state": {key: "b" * 64 for key in gate.COMPONENTS}}))
        else:
            path.write_bytes(b"synthetic file bytes - never deserialized")
    digest = gate.seal(root, binding, 2, 0)
    return binding, digest


def test_complete_checkpoint_gate(tmp_path):
    root = tmp_path / "checkpoint"
    binding, digest = fixture(root)
    assert gate.verify(root, binding, 2, digest)["completed_steps"] == 2


@pytest.mark.parametrize("fault,expected", [
    ("missing_rank", "file_set"), ("corrupt_rng", "file_hash"), ("extra_file", "file_set"),
    ("manifest_drift", "manifest_hash"), ("wrong_cursor", "cursor_or_binding"),
    ("wrong_world", "cursor_or_binding"), ("wrong_plan", "cursor_or_binding"),
    ("non_synthetic", "scope_or_binding"), ("empty_file", "unsafe_checkpoint_file"),
    ("oversize_file", "unsafe_checkpoint_file"), ("wrong_rank_semantic", "rank_receipt"),
    ("missing_component_semantic", "rank_receipt"),
])
def test_faults_fail_before_loading(tmp_path, fault, expected):
    root = tmp_path / "checkpoint"
    binding, digest = fixture(root)
    cursor = 2
    if fault == "missing_rank":
        (root / "random_states_1.pkl").unlink()
    elif fault == "corrupt_rng":
        (root / "random_states_1.pkl").write_bytes(b"different bytes")
    elif fault == "extra_file":
        (root / "unexpected.bin").write_bytes(b"unexpected")
    elif fault == "manifest_drift":
        with (root / "manifest.json").open("a") as stream:
            stream.write(" ")
    elif fault == "wrong_cursor":
        cursor = 3
    elif fault == "wrong_world":
        binding["world"] = 4
    elif fault == "wrong_plan":
        binding["plan_sha256"] = "c" * 64
    elif fault == "non_synthetic":
        binding["scope"] = "research-model"
    elif fault in ("empty_file", "oversize_file"):
        (root / "optimizer.bin").write_bytes(b"" if fault == "empty_file" else b"x" * (gate.MAX_FILE_BYTES + 1))
    else:
        path = root / "observed_1.json"
        row = json.loads(path.read_text())
        if fault == "wrong_rank_semantic":
            row["rank"] = 0
        else:
            row["state"].pop("torch_rng")
        path.write_text(json.dumps(row))
        # Semantic faults must be rejected even after the file is rehashed.
        manifest_path = root / "manifest.json"
        value = json.loads(manifest_path.read_text())
        value["files"][path.name] = {"sha256": gate.sha(path), "bytes": path.stat().st_size}
        manifest_path.write_text(json.dumps(value))
        digest = gate.sha(manifest_path)
    with pytest.raises(ValueError, match=expected):
        gate.verify(root, binding, cursor, digest)


@pytest.mark.parametrize("component", gate.COMPONENTS)
def test_swallowed_load_failure_detected(component):
    expected = {key: "a" * 64 for key in gate.COMPONENTS}
    actual = copy.deepcopy(expected)
    actual[component] = "b" * 64
    with pytest.raises(ValueError, match="restored_state_mismatch:" + component):
        gate.verify_restored(expected, actual)


def test_no_research_entry_or_default_trainer_modification():
    path = Path(__file__).resolve().parents[1] / "global_local_accelerate_resume_validation.py"
    source = path.read_text()
    assert 'Tiny(True)' in source
    assert 'sum(p.numel() for p in model.parameters()) != 2' in source
    assert 'accelerator.save_state(' in source and 'accelerator.load_state(' in source
    assert 'from_pretrained' not in source and 'sbatch' not in source
    assert 'weights_only": True' in source
    assert 'save_calls_mirrored_in_full": True' in source
    assert 'else 9600' in source


def test_atomic_checkpoint_manifest_cannot_overwrite(tmp_path):
    path = tmp_path / "manifest.json"
    gate.atomic_json(path, {"first": True})
    with pytest.raises(ValueError, match="overwrite_forbidden"):
        gate.atomic_json(path, {"second": True})
    assert json.loads(path.read_text()) == {"first": True}
