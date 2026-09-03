"""Run reproducible SYNTHETIC CPU checks without pytest or real training data.

python -B -m phase1.global_local_cpu_validation [--torch]
The opt-in torch check uses fixed CPU score vectors, not a model or optimizer.
Only this module's own source files are read for receipt hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

from phase1.global_local_execution_plan import bt_loss_and_gradient, demo_plans, digest_records, remaining_batches
from phase1.verify_global_local_execution_trace import BatchReceipt, verify_plan, verify_prefix


def check_cpu_autograd():
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA context already initialized; CPU-only check refused")
    comparisons = 0
    for sign in (-1, 1):
        a = torch.tensor([-6.0, -0.25, 0.0, 0.7, 8.0], dtype=torch.float64,
                         device="cpu", requires_grad=True)
        b = torch.tensor([3.0, 0.75, 0.0, -1.3, -4.0], dtype=torch.float64,
                         device="cpu", requires_grad=True)
        signed = torch.nn.functional.softplus(-sign * (a - b)).mean()
        grads = torch.autograd.grad(signed, (a, b))
        legacy = -torch.nn.functional.logsigmoid((a - b) if sign == 1 else (b - a)).mean()
        legacy_grads = torch.autograd.grad(legacy, (a, b))
        torch.testing.assert_close(signed, legacy, rtol=1e-12, atol=1e-12)
        for observed, expected in zip(grads, legacy_grads):
            torch.testing.assert_close(observed, expected, rtol=1e-12, atol=1e-12)
        for i, (x, y) in enumerate(zip(a.detach().tolist(), b.detach().tolist())):
            _, da, db = bt_loss_and_gradient(x, y, sign)
            if not (math.isclose(float(grads[0][i]), da / len(a), rel_tol=1e-12, abs_tol=1e-12)
                    and math.isclose(float(grads[1][i]), db / len(a), rel_tol=1e-12, abs_tol=1e-12)):
                raise RuntimeError("scalar oracle / autograd mismatch")
            comparisons += 1
    if torch.cuda.is_initialized():
        raise RuntimeError("unexpected CUDA context")
    return {"status": "PASS", "torch_version": torch.__version__, "device": "cpu",
            "score_pairs_checked": comparisons, "rtol": 1e-12, "atol": 1e-12,
            "cuda_context_initialized": False, "models_loaded": 0, "model_fits": 0}


def validate_cpu(*, torch_check=False):
    plans = tuple(demo_plans())
    reference = next(p for p in plans if p.arm == "G_to_L")
    g = tuple(r for b in reference.batches for r in b.rows if r.source == "G")
    l = tuple(r for b in reference.batches for r in b.rows if r.source == "L")
    resume_checks = 0
    for plan in plans:
        verify_plan(plan, g, l)
        plan_hash = plan.sha256
        for completed in range(plan.steps + 1):
            prefix = tuple(b for b in plan.batches if b.optimizer_step < completed)
            events = []
            for b in prefix:
                counts = [e.valid_tokens for row in b.rows for e in (row.a, row.b)]
                events.append(BatchReceipt(plan_hash, b.optimizer_step, b.micro_step, b.rank,
                    tuple(r.key for r in b.rows),
                    tuple((r.a.encoded_sha256, r.b.encoded_sha256) for r in b.rows),
                    sum(counts), len(counts) * max(counts)))
            cursor = verify_prefix(plan, events, completed_steps=completed)
            if prefix + remaining_batches(plan, cursor) != plan.batches:
                raise RuntimeError("synthetic resume mismatch")
            resume_checks += 1
    source_names = ("global_local_execution_plan.py", "verify_global_local_execution_trace.py",
                    "global_local_cpu_validation.py")
    root = Path(__file__).resolve().parent
    return {
        "status": "SYNTHETIC_CPU_VALIDATION_ONLY", "python_version": platform.python_version(),
        "synthetic_plans": len(plans), "seeds": sorted({p.seed for p in plans}),
        "demo_sha256": digest_records(p.summary() for p in plans),
        "resume_boundaries_checked": resume_checks,
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_names},
        "actual_training_batches_observed": 0, "optimizer_state_restored": False,
        "frozen_or_train_data_files_opened": 0, "gpu_jobs": 0, "model_fits": 0,
        "training_authorized": False,
        "autograd": check_cpu_autograd() if torch_check else {"status": "NOT_REQUESTED"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--torch", action="store_true", help="opt-in fixed-score CPU autograd check")
    args = parser.parse_args()
    print(json.dumps(validate_cpu(torch_check=args.torch), sort_keys=True))
