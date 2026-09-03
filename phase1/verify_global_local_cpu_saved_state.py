"""Read-only independent check of freshly produced synthetic CPU checkpoints.

Does not import the plan, adapter, or primary validation implementation. Only
use on locally trusted artifacts from global_local_trainer_cpu_validation, not
third-party checkpoints. Hash receipts prove integrity, not authorship.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import load_file
from transformers.trainer import safe_globals


FILES = ("model.safetensors", "optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json")


def same(a, b):
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.dtype == b.dtype and np.array_equal(a, b)
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def read(root, name):
    folder = root / name / "checkpoint-4"
    if folder.resolve().parent.parent != root.resolve() or folder.is_symlink():
        raise ValueError("checkpoint_scope_error")
    receipt = json.loads((folder / "gl_cpu_resume_receipt.json").read_text())
    assert receipt["completed_steps"] == 4 and set(receipt["files"]) == set(FILES)
    for filename in FILES:
        p = folder / filename
        assert p.is_file() and not p.is_symlink() and 0 < p.stat().st_size < 8*1024*1024
        assert hashlib.sha256(p.read_bytes()).hexdigest() == receipt["files"][filename]
    state = json.loads((folder / "trainer_state.json").read_text())
    assert state["global_step"] == 4
    saved = {"model": load_file(folder / "model.safetensors")}
    with safe_globals():
        for field, name in (("optimizer", "optimizer.pt"), ("scheduler", "scheduler.pt"), ("rng", "rng_state.pth")):
            saved[field] = torch.load(folder / name, map_location="cpu", weights_only=True)
    assert set(saved["model"]) == {"weight"} and saved["model"]["weight"].numel() == 2
    return saved


def verify(root):
    assert not torch.cuda.is_initialized()
    checked = []
    for arm in ("G_to_L", "Ghash_to_L"):
        expected = read(root, "resume-full-" + arm)
        for cut in (1, 2, 3):
            actual = read(root, f"resumed-{arm}-{cut}")
            assert all(same(expected[k], actual[k]) for k in expected)
            checked.append({"arm": arm, "cut_step": cut, "all_four_states_bitwise_equal": True})
    base = read(root, "resume-full-G_to_L")
    canaries = []
    for rng in ("python", "numpy", "torch"):
        broken = read(root, "rng-sensitivity-" + rng)
        assert not same(base["model"], broken["model"])
        canaries.append({"rng": rng, "final_parameter_divergence_confirmed": True})
    assert not torch.cuda.is_initialized()
    return {"status": "INDEPENDENT_SAVED_CPU_STATE_PASS", "read_only": True,
            "resume_checks": checked, "rng_canaries": canaries,
            "gpu_context_created": False, "distributed_validation": False,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "primary_receipt_sha256": hashlib.sha256((root/"receipt.json").read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().root), sort_keys=True))
