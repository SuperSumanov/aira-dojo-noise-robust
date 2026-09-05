"""Two-process, real random-Qwen training via pinned TRAIN files; not effects.

Four fixed screen plans plus two prefix/resume pairs. Only generated synthetic
inputs and a hash-pinned source definition are read. No pretrained snapshot,
GPU, dev split or production release is admitted. Parent bounds child groups.
"""
import argparse
from dataclasses import asdict, replace
from datetime import timedelta
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

from phase1.critic_train_projection import PinnedFile, TrainProjectionSpec, load_training_inputs
from phase1.critic_training_run import atomic_json, connect_training, run_session
from phase1.global_local_execution_plan import EncoderBinding


ENCODER = EncoderBinding(hashlib.sha256(b'synthetic-mod127').hexdigest(),
    hashlib.sha256(b'engineering-task-head25-tail75').hexdigest(), 16384)
PROTOCOL = hashlib.sha256(Path(__file__).parents[1].joinpath('g_reuse_development_screen_v1.json').read_bytes()).hexdigest()


class Tokenizer:
    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {'input_ids': [1+ord(c)%127 for c in text]}


def fixture_layout(layout):
    if layout == 'tiny':
        cards = [{'endpoint_id': f'synthetic{i}', 'task_name': 'synthetic-task', 'code': f'x={i}\n'} for i in range(8)]
        g = [(f'synthetic{i}', f'synthetic{i+2}') for i in (0, 1, 4, 5)]
        l = [(f'synthetic{i}', f'synthetic{i+1}') for i in (0, 2, 4, 6)]
        return cards, g, l
    assert layout == 'accum8'
    cards = [{'endpoint_id': f'synthetic{i:02}', 'task_name': 'synthetic-task', 'code': f'x={i:02}\n'} for i in range(32)]
    edges = list(combinations([c['endpoint_id'] for c in cards], 2))
    # All endpoints occur in L. Disjoint G edges reuse only those endpoints.
    return cards, edges[134:264], edges[:134]


def cases_for(layout):
    complete = (1, 2, 3, 4) if layout == 'tiny' else (1, 2)
    return [(i, 'full') for i in complete]+[(i, m) for i in (1, 2) for m in ('prefix', 'resume')]


def write_fixture(root, layout='tiny'):
    root.mkdir(mode=0o700)
    header = {'role': 'train', 'source_package_sha256': 'a'*64, 'split_receipt_sha256': 'b'*64}
    cards, g, l = fixture_layout(layout)
    def put(name, obj):
        atomic_json(root/name, obj)
        raw = (root/name).read_bytes()
        return PinnedFile(name, hashlib.sha256(raw).hexdigest(), len(raw))
    top = put('topology.json', dict(header, protocol='critic-train-topology-v1', cards=cards,
        global_edges=g, local_edges=l))
    spec = TrainProjectionSpec('a'*64, 'b'*64, top, PinnedFile('local.json', 'c'*64, 1), PinnedFile('global.json', 'd'*64, 1))
    data = load_training_inputs(root, spec, Tokenizer(), encoder=ENCODER, protocol_sha256=PROTOCOL)
    files = {}
    for source, pool, name in (('G', data.pools[0], 'global.json'), ('L', data.pools[1], 'local.json')):
        files[source] = put(name, dict(header, protocol='critic-train-targets-v1', source=source,
            winners={row.key: (row.a.card_id if i%2 == 0 else row.b.card_id) for i, row in enumerate(pool)}))
    spec = replace(spec, global_targets=files['G'], local_targets=files['L'])
    atomic_json(root/'spec.json', asdict(spec))
    # Not a real evaluation set. Any opening of this sentinel is a driver bug.
    atomic_json(root/'forbidden_dev.json', {'must_not_open': True})


def worker(args):
    assert os.environ['CUDA_VISIBLE_DEVICES'] == '' and os.environ['WORLD_SIZE'] == '2'
    import numpy as np
    import torch
    import torch.distributed as dist
    from torch import nn
    from accelerate import Accelerator
    from accelerate.utils import InitProcessGroupKwargs
    from transformers import Qwen3Config, Qwen3Model
    from phase1.global_local_critic_consumer import PlannedCriticConsumer
    from phase1.global_local_critic_session import CriticSession, current_state, state_fingerprint
    from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    reference = source_definitions(args.source_root)
    obj = json.loads((args.root/'inputs'/'spec.json').read_bytes())
    spec = TrainProjectionSpec(obj['source_package_sha256'], obj['split_receipt_sha256'],
        **{k: PinnedFile(**obj[k]) for k in ('topology', 'local_targets', 'global_targets')})
    opened = []
    from phase1 import critic_train_projection as reader
    original = reader.read_pinned
    def observed(root, pinned):
        opened.append(pinned.name)
        return original(root, pinned)
    reader.read_pinned = observed
    initial = {}
    def setup(plan, pools, encode, truth, *, training_contract_sha256):
        assert len({encode(r.context_sha256, e.card_id) for pool in pools for r in pool for e in (r.a, r.b)}) == (8 if args.layout == 'tiny' else 32)
        torch.manual_seed(plan.seed)
        cls = reference['BradleyTerryRewardModel']
        model = cls.__new__(cls); nn.Module.__init__(model)
        model.backbone = Qwen3Model(Qwen3Config(vocab_size=128, hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=8,
            max_position_embeddings=256, pad_token_id=0, use_cache=False,
            attn_implementation='eager', attention_dropout=0.1))
        model.head = nn.Linear(16, 1, dtype=torch.float32); model.train()
        assert sum(p.numel() for p in model.parameters()) == 4433
        initial['model'] = state_fingerprint(model.state_dict())
        accelerator = Accelerator(cpu=True, mixed_precision='no', gradient_accumulation_steps=plan.shape.accumulation,
            kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=60))])
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
        model, optimizer = accelerator.prepare(model, optimizer)
        consumer = PlannedCriticConsumer(plan=plan, pools=pools, accelerator=accelerator,
            model=model, optimizer=optimizer, encoding_provider=encode, true_sign=truth, pad_id=0)
        session = CriticSession(consumer, training_contract_sha256=training_contract_sha256)
        seed = (90000 if args.mode == 'resume' else plan.seed*1000)+consumer.rank
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
        return session
    contract = hashlib.sha256(('entry-fixture:'+os.environ['CRITIC_ENTRY_COMMIT']).encode()).hexdigest()
    fit, session = connect_training(args.root/'inputs', spec, Tokenizer(), encoder=ENCODER,
        protocol_sha256=PROTOCOL, sequence=args.sequence, setup=setup, training_contract_sha256=contract)
    assert opened == (['topology.json', 'local.json'] if fit.plan.arm == 'Lbudget' else
                       ['topology.json', 'local.json', 'global.json'])
    final_step = 2 if args.layout == 'tiny' else 4
    prefix_step = 1 if args.layout == 'tiny' else 2
    assert fit.plan.steps == final_step
    if args.layout == 'accum8':
        for rank in (0, 1):
            assert [len([b for b in fit.plan.batches if b.rank == rank and b.optimizer_step == s])
                    for s in range(final_step)] == [8, 1, 8, 1]
    resume = args.root/f'fit{args.sequence}-prefix'/f'checkpoint-{prefix_step}' if args.mode == 'resume' else None
    sha = None if resume is None else hashlib.sha256((resume/'manifest.json').read_bytes()).hexdigest()
    end = prefix_step if args.mode == 'prefix' else final_step
    stops = list(range(prefix_step+1, end+1)) if resume is not None else list(range(1, end+1))
    out = args.root/f'fit{args.sequence}-{args.mode}'
    result = run_session(session, fit, out, stop_after=end, checkpoint_steps=stops,
        resume=resume, resume_manifest_sha256=sha)
    state = current_state(session.consumer)
    assert state['model'] != initial['model'] and not torch.cuda.is_initialized()
    row = {'rank': session.consumer.rank, 'initial_model_sha256': initial['model'],
           'final_state': state, 'projection_files_opened': opened, 'status': result['status']}
    gathered = [None, None]; dist.all_gather_object(gathered, row)
    if session.consumer.rank == 0:
        atomic_json(out/'engineering_state.json', {'sequence': args.sequence, 'seed': fit.plan.seed,
            'arm': fit.reported_arm, 'plan_sha256': fit.plan.sha256, 'reference_tokens': fit.plan.reference_valid_tokens,
            'tokens': fit.plan.planned_valid_tokens, 'ranks': sorted(gathered, key=lambda x: x['rank'])})
    session.consumer.accelerator.wait_for_everyone(); dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--sequence', type=int, choices=(1, 2, 3, 4))
    parser.add_argument('--mode', choices=('full', 'prefix', 'resume'))
    parser.add_argument('--layout', choices=('tiny', 'accum8'), default='tiny')
    args = parser.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and len(os.environ.get('CRITIC_ENTRY_COMMIT', '')) == 40
    if args.worker:
        return worker(args)
    assert args.root.is_absolute() and args.root.parent == Path('/tmp') and not args.root.exists()
    assert args.root.name.startswith('critic-entry-cpu-')
    args.root.mkdir(mode=0o700); write_fixture(args.root/'inputs', args.layout)
    started = time.monotonic()
    for sequence, mode in cases_for(args.layout):
        assert time.monotonic()-started < 900, 'CPU_budget_exceeded'
        env = dict(os.environ, OMP_NUM_THREADS='1', ACCELERATE_USE_CPU='true', GLOO_SOCKET_IFNAME='lo')
        argv = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nnodes=1', '--nproc_per_node=2',
            '-m', 'phase1.scripts.validate_critic_entry_cpu_20260906', '--worker', '--root', str(args.root),
            '--source-root', args.source_root, '--sequence', str(sequence), '--mode', mode, '--layout', args.layout]
        log = args.root/f'fit{sequence}-{mode}.log'
        with log.open('xb') as out:
            p = subprocess.Popen(argv, env=env, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                rc = p.wait(timeout=150)
            except BaseException:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
                raise
        assert rc == 0, f'engineering_worker_failed_fit{sequence}_{mode}'
        print(json.dumps({'completed': f'fit{sequence}-{mode}'}), flush=True)
    summary = {'classification': 'PINNED_TRAIN_FILES_TO_RANDOM_QWEN_CPU_LIFECYCLE_NOT_EFFECT',
        'code_commit': os.environ['CRITIC_ENTRY_COMMIT'], 'parameters': 4433, 'world': 2,
        'layout': args.layout,
        'matrix_complete_trajectories': 4 if args.layout == 'tiny' else 2, 'additional_prefix_resume_trajectories': 4,
        'seeds': [6, 7] if args.layout == 'tiny' else [6], 'dtype': 'float32', 'optimizer': 'AdamW', 'weight_decay': 0.0,
        'max_len_contract': 16384, 'tiny_fixture_not_16k_memory_test': True,
        'gpu_used': False, 'production_release_admitted': False, 'real_data_read': False,
        'independent_verification_still_required': True}
    atomic_json(args.root/'summary.json', summary)
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
