"""Connect the FINAL reader to job 12573's actual, independently accepted shards.

CPU-only engineering, not a corpus/effect reader, submitter or GPU qualification.
Do not call until the original terminal + payload acceptance is complete.
Separate trace/security review remains required before publishing acceptance.
The caller supplies the authenticated acceptance hash, never an arbitrary model.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

JOB = '12573'
TRAINING_COMMIT = 'b84e8baea4de65a16038b4136cee094d29716964'
BASE = Path('/research/d7/spc/yzyang4')
JOB_ROOT = BASE / 'critic-zero3-engineering/job-12573'
OUTPUT = BASE / 'critic-zero3-final-readout-12573-20260906'
SOURCE = BASE / 'worktrees/critic-g0-final-only-20260903-b'
FINALS = ('full', 'resume2', 'resume3')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def acceptance_gate(value):
    require(type(value) is dict and value.get('classification') ==
            'INDEPENDENT_TINY_ZERO3_RESUME_ACCEPTANCE_NOT_EFFECT', 'prior_acceptance_classification')
    require(value.get('job_id') == JOB and value.get('code_commit') == TRAINING_COMMIT,
            'prior_acceptance_identity')
    require(value.get('gpu_initialized') is False, 'prior_acceptance_cuda')
    records = value.get('actual_checkpoint_payload_comparisons')
    require(type(records) is list and len(records) == 12, 'prior_payload_comparison_count')
    expected = {(rank, case, name) for rank in (0, 1) for case in ('resume2', 'resume3')
                for name in (f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
                             f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',
                             f'random_states_{rank}.pkl')}
    seen = set()
    for row in records:
        require(type(row) is dict and set(row) == {'rank', 'case', 'file', 'all_payload_bits_equal'}
                and type(row['rank']) is int and row['all_payload_bits_equal'] is True,
                'prior_payload_comparison_schema')
        key = (row['rank'], row['case'], row['file'])
        require(key in expected and key not in seen, 'prior_payload_comparison_identity')
        seen.add(key)
    require(seen == expected, 'prior_payload_comparison_coverage')


def fresh_model():
    import torch
    from torch import nn
    from transformers import Qwen3Config, Qwen3Model
    from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions
    cls = source_definitions(SOURCE)['BradleyTerryRewardModel']
    model = cls.__new__(cls)
    nn.Module.__init__(model)
    model.backbone = Qwen3Model(Qwen3Config(vocab_size=128, hidden_size=16, intermediate_size=32,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=8,
        max_position_embeddings=64, pad_token_id=0, use_cache=False,
        attn_implementation='eager', attention_dropout=0.1))
    model.head = nn.Linear(16, 1, dtype=torch.float32)
    model.to(dtype=torch.bfloat16).eval()
    require(sum(p.numel() for p in model.parameters()) == 4433, 'tiny_model_schema')
    return model


def compare_models(models):
    """Fixed synthetic token inputs; no tokenizer, labels, candidate IDs or files."""
    import torch
    from phase1.global_local_critic_session import state_fingerprint
    require(type(models) is list and len(models) == 3, 'final_model_count')
    for model in models:
        require(all(not m.training for m in model.modules()), 'final_eval_required')
        require(all(p.device.type == 'cpu' and p.dtype == torch.bfloat16 for p in model.parameters()),
                'final_cpu_bf16_required')
    states = [state_fingerprint(m.state_dict()) for m in models]
    require(len(set(states)) == 1, 'final_weight_mismatch')
    ids = torch.tensor([[1, 2, 3, 4], [5, 6, 0, 0], [7, 8, 9, 0]])
    mask = torch.tensor([[1, 1, 1, 1], [1, 1, 0, 0], [1, 1, 1, 0]])
    with torch.inference_mode():
        outputs = [m(input_ids=ids, attention_mask=mask)['logits'] for m in models]
    require(all(tuple(x.shape) == (3,) and x.is_floating_point() and bool(torch.isfinite(x).all())
                for x in outputs), 'synthetic_forward_schema')
    require(all(torch.equal(outputs[0], x) for x in outputs[1:]), 'synthetic_forward_mismatch')
    require(states == [state_fingerprint(m.state_dict()) for m in models], 'forward_mutated_weights')
    require(all(p.grad is None for m in models for p in m.parameters()), 'unexpected_gradient')
    return {'final_models': 3, 'state_sha256': states[0], 'synthetic_input_rows': 3,
            'synthetic_output_sha256': state_fingerprint(outputs[0]),
            'bitwise_final_weights_equal': True, 'bitwise_synthetic_outputs_equal': True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--acceptance-sha256', required=True)
    args = p.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and os.environ.get('HF_HUB_OFFLINE') == '1'
            and os.environ.get('TRANSFORMERS_OFFLINE') == '1', 'cpu_offline_environment_required')
    require(re.fullmatch('[0-9a-f]{64}', args.acceptance_sha256), 'prior_acceptance_hash_required')
    require(not OUTPUT.exists(), 'exclusive_output_exists')
    from phase1.scripts.verify_zero3_engineering_20260905 import read, digest, verify_manifests
    prior = JOB_ROOT / 'independent_acceptance.json'
    accepted = read(prior)
    require(digest(prior) == args.acceptance_sha256, 'prior_acceptance_hash_changed')
    acceptance_gate(accepted)
    root = JOB_ROOT / 'trajectories'
    full = read(root / 'full/trajectory.json')
    binding = full['binding']
    require(binding['total_steps'] == 4 and binding['world'] == 2 and full['seed'] == 6,
            'actual_final_binding')
    manifests = verify_manifests(root, binding)
    require(manifests == accepted['manifests'], 'accepted_checkpoint_inventory_changed')
    by_path = {r['path']: r['manifest_sha256'] for r in manifests}
    import torch
    import transformers
    require(torch.__version__ == '2.11.0+cu128' and transformers.__version__ == '5.12.1', 'runtime_drift')
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    require(not torch.cuda.is_initialized(), 'cuda_initialized')
    from phase1.critic_zero3_final_state import load_final_into_cpu
    models, loads = [], []
    for case in FINALS:
        model = fresh_model()
        name = case + '/checkpoint-4'
        loads.append(load_final_into_cpu(model, root / name, binding=binding,
            manifest_sha256=by_path[name], expected_tokens=full['planned_tokens']))
        models.append(model)
    comparison = compare_models(models)
    require(manifests == verify_manifests(root, binding) and digest(prior) == args.acceptance_sha256,
            'input_changed_during_readout')
    require(not torch.cuda.is_initialized(), 'cuda_initialized')
    report = dict(classification='ACTUAL_TINY_ZERO3_FINAL_READOUT_NOT_1P7B_OR_EFFECT',
        job_id=JOB, training_commit=TRAINING_COMMIT,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        prior_payload_acceptance_sha256=args.acceptance_sha256,
        trace_acceptance='SEPARATE_REVIEW_REQUIRED',
        loads=loads, **comparison, gpu_initialized=False, corpus_reads=0,
        new_gpu_jobs=0, new_model_fits=0, production_admission=False)
    OUTPUT.mkdir(mode=0o700)
    receipt = OUTPUT / 'receipt.json'
    with receipt.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
    print(json.dumps({'status': report['classification'], 'receipt_sha256': digest(receipt),
                      'final_models': comparison['final_models']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch('[a-z0-9_]+', str(exc)) else 'detail_withheld'
        print(json.dumps({'status': 'ZERO3_FINAL_READOUT_FAILED_CLOSED', 'reason': reason}))
        raise SystemExit(1)
