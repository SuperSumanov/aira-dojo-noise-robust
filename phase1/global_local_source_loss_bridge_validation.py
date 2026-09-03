"""Source-bound CPU bridge for the senior reward-model loss and pooling methods.

Only the two AST method bodies are executed with synthetic tensors.  The model
constructor, training entry point, dataset readers, and evaluation code are not
imported or called.  This is interoperability evidence, not a model effect fit.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import torch


SOURCE = Path(
    "/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b/"
    "src/mle_critic/src/train/bradley_terry.py"
)
SOURCE_SHA256 = "d3cfd12602dc399a456810d4f706124df7117834ebba124813233f77ba043977"


def _method(tree, source_text, class_name, method_name):
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
    if len(classes) != 1:
        raise ValueError("source_class_mismatch")
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == method_name]
    if len(methods) != 1:
        raise ValueError("source_method_mismatch")
    method = methods[0]
    if method.decorator_list:
        raise ValueError("unexpected_method_decorator")
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {"torch": torch}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    body = ast.get_source_segment(source_text, method)
    return namespace[method_name], hashlib.sha256(body.encode()).hexdigest()


def run():
    if str(torch.__version__) != "2.11.0+cu128" or torch.cuda.is_initialized():
        raise ValueError("runtime_or_cuda_scope_mismatch")
    torch.set_num_threads(1)
    torch.manual_seed(6)
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("source_hash_mismatch")
    credential_shapes = [
        rb"sk-[A-Za-z0-9_.-]{16,}", rb"ghp_[A-Za-z0-9]{20,}",
        rb"AKIA[0-9A-Z]{16}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    hits = sum(len(re.findall(pattern, raw)) for pattern in credential_shapes)
    if hits:
        raise ValueError("credential_shape_in_source")
    text = raw.decode()
    tree = ast.parse(text)
    compute_loss, loss_sha = _method(tree, text, "BradleyTerryTrainer", "compute_loss")
    model_forward, forward_sha = _method(tree, text, "BradleyTerryRewardModel", "forward")
    cases = []
    wrong_orientation_detected = False
    for dtype in (torch.float32, torch.float64):
        tolerance = 2e-6 if dtype == torch.float32 else 1e-12
        for count in (1, 6, 7, 8):
            for score_case in ("ordinary", "extreme", "ties"):
                for sign_case in ("positive", "mixed"):
                    if score_case == "ordinary":
                        initial = torch.linspace(-1.7, 2.3, 2 * count, dtype=dtype)
                    elif score_case == "extreme":
                        initial = torch.linspace(-80.0, 80.0, 2 * count, dtype=dtype)
                    else:
                        initial = torch.zeros(2 * count, dtype=dtype)
                    scores = initial.clone().requires_grad_(True)
                    signs = torch.ones(count, dtype=dtype)
                    if sign_case == "mixed":
                        signs[::2] = -1
                    a, b = scores[:count], scores[count:]
                    winner_first = torch.cat((
                        torch.where(signs > 0, a, b),
                        torch.where(signs > 0, b, a),
                    ))
                    model = lambda **_inputs: {"logits": winner_first}
                    source_loss = compute_loss(None, model, {})
                    reference_loss = torch.nn.functional.softplus(-signs * (a - b)).mean()
                    source_gradient = torch.autograd.grad(source_loss, scores, retain_graph=True)[0]
                    reference_gradient = torch.autograd.grad(reference_loss, scores)[0]
                    torch.testing.assert_close(source_loss, reference_loss, rtol=tolerance, atol=tolerance)
                    torch.testing.assert_close(source_gradient, reference_gradient, rtol=tolerance, atol=tolerance)
                    unadapted_loss = compute_loss(None, lambda **_inputs: {"logits": scores}, {})
                    if sign_case == "mixed" and score_case != "ties":
                        wrong_orientation_detected |= abs(float((unadapted_loss - source_loss).detach())) > 1e-3
                    cases.append({
                        "dtype": str(dtype),
                        "pairs": count,
                        "scores": score_case,
                        "signs": sign_case,
                        "loss_max_abs_error": float((source_loss - reference_loss).detach().abs()),
                        "gradient_max_abs_error": float((source_gradient - reference_gradient).detach().abs().max()),
                    })
    if not wrong_orientation_detected:
        raise ValueError("orientation_negative_control_not_detected")

    rows, width, features = 8, 9, 3
    lengths = torch.arange(1, rows + 1)
    mask = torch.arange(width).unsqueeze(0) < lengths.unsqueeze(1)
    hidden = (torch.arange(rows * width * features, dtype=torch.float64).reshape(rows, width, features) / 100).requires_grad_(True)
    head_weight = torch.tensor([[0.3], [-0.2], [0.7]], dtype=torch.float64)
    holder = SimpleNamespace(
        backbone=lambda **_inputs: SimpleNamespace(last_hidden_state=hidden),
        head=lambda values: values @ head_weight,
    )
    logits = model_forward(holder, input_ids=torch.zeros(rows, width, dtype=torch.long), attention_mask=mask.long())["logits"]
    reference = torch.stack([hidden[row, int(lengths[row]) - 1] @ head_weight for row in range(rows)]).squeeze(-1).float()
    torch.testing.assert_close(logits, reference, rtol=0, atol=0)
    if logits.dtype != torch.float32:
        raise ValueError("source_output_dtype_changed")
    logits.sum().backward()
    allowed = torch.zeros_like(hidden, dtype=torch.bool)
    allowed[torch.arange(rows), lengths - 1, :] = True
    if torch.count_nonzero(hidden.grad[~allowed]):
        raise ValueError("pooling_gradient_on_wrong_position")
    changed = hidden.detach().clone()
    changed[~mask] = 1000000.0
    holder.backbone = lambda **_inputs: SimpleNamespace(last_hidden_state=changed)
    changed_logits = model_forward(holder, input_ids=torch.zeros(rows, width, dtype=torch.long), attention_mask=mask.long())["logits"]
    torch.testing.assert_close(logits.detach(), changed_logits, rtol=0, atol=0)
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("source_drift_during_validation")
    if torch.cuda.is_initialized():
        raise ValueError("unexpected_cuda_context")
    return {
        "status": "PASS_SOURCE_BOUND_LOSS_AND_POOLING_BRIDGE_NOT_REAL_MODEL",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": SOURCE_SHA256,
        "method_sha256": {"compute_loss": loss_sha, "reward_model_forward": forward_sha},
        "credential_shape_hits": hits,
        "loss_gradient_cases": cases,
        "loss_gradient_case_count": len(cases),
        "canonical_sign_vs_winner_first_loss_and_gradient_match": True,
        "unadapted_canonical_orientation_negative_control_detected": wrong_orientation_detected,
        "pooling_rows": rows,
        "last_valid_token_pooling_exact": True,
        "pooling_padding_change_invariant": True,
        "source_logits_dtype": "torch.float32",
        "real_model_constructor_called": False,
        "real_data_opened": False,
        "gpu_context_created": False,
        "model_fits": 0,
        "api_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_relative_to(Path("/tmp")) or args.output.exists():
        raise ValueError("new_tmp_output_required")
    report = run()
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps({
        "status": report["status"],
        "loss_gradient_case_count": report["loss_gradient_case_count"],
        "pooling_rows": report["pooling_rows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
