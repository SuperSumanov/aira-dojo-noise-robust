"""Random tiny Qwen3 CPU-DDP gradient oracle; no real weights/data/evaluation.

SGD is deliberately used as a transparent gradient-to-parameter oracle. This
does not validate production AdamW, ZeRO-3, bf16 or checkpoint/resume.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket

import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch import nn
from accelerate import Accelerator
from transformers import Qwen3Config, Qwen3Model

from phase1.global_local_batch_adapter import encoding_digest
from phase1.global_local_critic_consumer import PlannedCriticConsumer
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair
from phase1.global_local_token_budget_plan import build_plan
from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import SOURCE_COMMIT, SOURCE_HASHES, source_definitions

ARMS = ('L1', 'Lbudget', 'Gbudget', 'G_to_L', 'Ghash_to_L')
GRAD_ATOL, GRAD_RTOL, PARAM_ATOL = 3e-6, 5e-5, 1e-7


def fixture(arm):
    h = lambda x: hashlib.sha256(x.encode()).hexdigest()
    context, encoded, truth, pools = h('synthetic:qwen-consumer'), {}, {}, []
    for source, count in (('G', 11), ('L', 13)):
        rows = []
        for i in range(count):
            ends = []
            length = 2 + i % 3
            for side, n in enumerate((length, 8-length)):
                name = f'synthetic:qwen:{source}:{i}:{side}'
                ids = tuple(1 + (i * 7 + side * 13 + pos + (source == 'L')) % 127 for pos in range(n))
                encoded[(context, name)] = ids
                ends.append(Endpoint(name, n, encoding_digest(ids)))
            row = Pair.canonical(source, *ends, context)
            truth[row.key] = 1 if i % 2 else -1
            rows.append(row)
        pools.append(tuple(rows))
    plan = build_plan(arm, *pools, seed=6, shape=BatchShape(2, 2, 2),
                      encoder=EncoderBinding(h('synthetic:integer'), h('synthetic:serialization'), 8),
                      protocol_sha256=h('synthetic:qwen-gradient-oracle-not-research'))
    return plan, pools, encoded, truth


def true_or_hash(row, arm, truth):
    if arm == 'Ghash_to_L' and row.source == 'G':
        # Independent of the producer's target function.
        a = hashlib.sha256(('20260823|' + row.a.card_id).encode()).digest()
        b = hashlib.sha256(('20260823|' + row.b.card_id).encode()).digest()
        return 1 if a > b else -1
    return truth[row.key]


def flat_grads(model):
    return torch.cat([(torch.zeros_like(p) if p.grad is None else p.grad).detach().flatten().cpu()
                      for p in model.parameters()])


def worker(rank, port, output, source_root):
    os.environ.update(RANK=str(rank), LOCAL_RANK=str(rank), WORLD_SIZE='2', MASTER_ADDR='127.0.0.1',
                      MASTER_PORT=str(port), GLOO_SOCKET_IFNAME='lo', ACCELERATE_USE_CPU='true',
                      OMP_NUM_THREADS='1')
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    ref = source_definitions(source_root)
    records = []
    for arm in ARMS:
        torch.manual_seed(6)
        cls = ref['BradleyTerryRewardModel']
        model = cls.__new__(cls)
        nn.Module.__init__(model)
        model.backbone = Qwen3Model(Qwen3Config(vocab_size=128, hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=8,
            max_position_embeddings=64, pad_token_id=0, use_cache=False, attn_implementation='eager'))
        model.head = nn.Linear(16, 1, dtype=torch.float32)
        model.train()
        reference = deepcopy(model)
        reference_optimizer = torch.optim.SGD(reference.parameters(), lr=1e-5)
        plan, pools, encoded, truth = fixture(arm)
        global_keys = {r.key for r in pools[0]}
        def target(key):
            if arm == 'Ghash_to_L' and key in global_keys:
                raise RuntimeError('forbidden_true_global_label_read')
            return truth[key]
        accelerator = Accelerator(cpu=True, mixed_precision='no', gradient_accumulation_steps=2)
        optimizer = torch.optim.SGD(model.parameters(), lr=1e-5)
        model, optimizer = accelerator.prepare(model, optimizer)
        obj = PlannedCriticConsumer(plan=plan, pools=pools, accelerator=accelerator, model=model,
            optimizer=optimizer, encoding_provider=lambda ctx, card: encoded[(ctx, card)],
            true_sign=target, pad_id=0)
        actual_gradients = []
        original_clip = accelerator.clip_grad_norm_
        def observed_clip(parameters, norm):
            actual_gradients.append(flat_grads(model))
            return original_clip(parameters, norm)
        accelerator.clip_grad_norm_ = observed_clip
        for step in range(plan.steps):
            batches = [b for b in plan.batches if b.optimizer_step == step]
            rows = [row for b in batches for row in b.rows]
            pairs = []
            for row in rows:
                sign = true_or_hash(row, arm, truth)
                a, b = encoded[(row.context_sha256, row.a.card_id)], encoded[(row.context_sha256, row.b.card_id)]
                pairs.append({'b': list(a if sign > 0 else b), 'w': list(b if sign > 0 else a)})
            packed = ref['pair_collate'](pairs, pad_token_id=0)
            scores = reference(**packed)['logits']
            n = len(rows)
            loss = -torch.nn.functional.logsigmoid(scores[:n] - scores[n:]).mean()
            reference_optimizer.zero_grad(set_to_none=True)
            loss.backward()
            expected_grad = flat_grads(reference)
            torch.nn.utils.clip_grad_norm_(reference.parameters(), 1.0)
            lr = float(plan.peak_lr_decimal) * batches[0].lr_scale_numerator / batches[0].lr_scale_denominator
            reference_optimizer.param_groups[0]['lr'] = lr
            reference_optimizer.step()
            event = obj.run_next_update()
            actual_grad = actual_gradients[-1]
            torch.testing.assert_close(actual_grad, expected_grad, atol=GRAD_ATOL, rtol=GRAD_RTOL)
            observed = accelerator.unwrap_model(model)
            param_error = max(float((a.detach() - b.detach()).abs().max())
                              for a, b in zip(observed.parameters(), reference.parameters()))
            assert param_error <= PARAM_ATOL
            assert event.completed_steps == step + 1 and event.learning_rate == lr
            assert event.cumulative_global_valid_tokens == batches[0].cumulative_valid_tokens_after_update
            records.append({'arm': arm, 'seed': 6, 'rank': rank, 'completed_steps': step+1,
                'source': event.source, 'global_update_pairs': event.global_update_pairs,
                'local_pair_visits': event.local_pair_visits, 'local_valid_tokens': event.local_valid_tokens,
                'cumulative_global_valid_tokens': event.cumulative_global_valid_tokens,
                'max_abs_gradient_error': float((actual_grad-expected_grad).abs().max()),
                'max_abs_parameter_error': param_error, 'pass': True})
        assert not torch.cuda.is_initialized()
        assert obj.completed_steps == plan.steps
        accelerator.wait_for_everyone()
    all_records = [None, None]
    dist.all_gather_object(all_records, records)
    if rank == 0:
        results = [row for group in all_records for row in group]
        for arm in ARMS:
            plan, _, _, _ = fixture(arm)
            subset = [r for r in results if r['arm'] == arm]
            assert sum(r['local_valid_tokens'] for r in subset) == plan.planned_valid_tokens
            assert sum(r['local_pair_visits'] for r in subset) == plan.planned_pair_visits
        out = Path(output)
        with (out/'cases.csv').open('x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
        summary = {'classification': 'RANDOM_QWEN_CPU_DDP_GRADIENT_PARITY_NOT_EFFECT',
            'source_commit': SOURCE_COMMIT, 'source_hashes': SOURCE_HASHES,
            'code_commit': os.environ['CONSUMER_CODE_COMMIT'], 'runtime': obj.runtime,
            'arms': list(ARMS), 'seeds': [6], 'world_size': 2, 'dtype': 'float32',
            'parameters': sum(p.numel() for p in reference.parameters()), 'optimizer': 'SGD-gradient-oracle-only',
            'cases': len(results), 'grad_atol': GRAD_ATOL, 'grad_rtol': GRAD_RTOL, 'param_atol': PARAM_ATOL,
            'max_abs_gradient_error': max(r['max_abs_gradient_error'] for r in results),
            'max_abs_parameter_error': max(r['max_abs_parameter_error'] for r in results),
            'consumer_sha256': hashlib.sha256(Path(__file__).parents[1].joinpath('global_local_critic_consumer.py').read_bytes()).hexdigest(),
            'validation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'gpu_used': False, 'real_checkpoint_loaded': False, 'real_data_read': False,
            'production_adam_zero_bf16_resume_validated': False}
        with (out/'summary.json').open('x') as f:
            json.dump(summary, f, sort_keys=True, indent=2); f.write('\n')
        print(json.dumps(summary, sort_keys=True))
    dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (os.environ.get('CUDA_VISIBLE_DEVICES') != '' or torch.cuda.is_initialized()
            or not os.environ.get('CONSUMER_CODE_COMMIT')):
        raise RuntimeError('explicit_cpu_scope_and_code_binding_required')
    if args.output.exists() or not args.output.resolve().is_relative_to(Path('/tmp')):
        raise RuntimeError('new_tmp_output_required')
    args.output.mkdir(mode=0o700)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    mp.spawn(worker, args=(port, str(args.output), args.source_root), nprocs=2, join=True)


if __name__ == '__main__':
    main()
