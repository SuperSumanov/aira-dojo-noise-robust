"""Connect our synthetic trained finals -> fixed scorers -> blind join -> stats.

No real cohort or pretrained weights. TF-IDF and neural stages use separately
pinned existing runtimes; no installing/mixing packages. Public output reports
only engineering coverage, never a synthetic accuracy as research evidence.
"""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import time

from phase1.critic_train_projection import PinnedFile, TrainProjectionSpec, load_training_inputs, load_training_targets, read_pinned
from phase1.critic_training_run import atomic_json
from phase1.g_reuse_development_screen_plan import prepare_screen
from phase1.g_reuse_development_predictions import blind_development_margins, join_development_truth
from phase1.g_reuse_development_readout import evaluate_development, PROTOCOL_SHA256, KEYS, FULL
from phase1.scripts.validate_critic_entry_cpu_20260906 import Tokenizer, ENCODER

TRAIN = Path('/tmp/critic-entry-cpu-95e72f3-a')
EXPECTED_MATRIX = ((1, 'Lbudget', 6), (2, FULL, 6), (3, FULL, 7), (4, 'Lbudget', 7))


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def ident(text): return hashlib.sha256(text.encode()).hexdigest()


def dev_fixture():
    cards = []; pairs = []
    for task in range(2):
        for pair in range(2):
            names = [f'synthetic-dev-t{task}-p{pair}-{side}' for side in (0, 1)]
            for side, name in enumerate(names):
                cards.append({'endpoint_id': name, 'task_name': f'synthetic-dev-{task}', 'code': f'x={10+pair+side}\n'})
            pairs.append({'pair_sha256': ident(f'pair{task}-{pair}'), 'task_sha256': ident(f'task{task}'),
                'parent_sha256': ident(f'parent{task}'), 'run_sha256': ident(f'run{task}'), 'a': names[0], 'b': names[1]})
    return cards, pairs


def lock_finals(expected_verification_sha):
    assert sha(TRAIN/'independent_verification.json') == expected_verification_sha
    verified = json.loads((TRAIN/'independent_verification.json').read_bytes())
    assert verified['classification'] == 'INDEPENDENT_PINNED_TRAIN_CPU_LIFECYCLE_NOT_EFFECT'
    assert verified['AB_engineering_state_bytes_equal'] and verified['exact_resumed_consumption']
    locked = []
    for seq, arm, seed in EXPECTED_MATRIX:
        folder = TRAIN/f'fit{seq}-full'; cp = folder/'checkpoint-2'
        receipt = json.loads((folder/'run_receipt.json').read_bytes())
        assert receipt['status'] == 'COMPLETED' and receipt['arm'] == arm and receipt['seed'] == seed
        manifest = json.loads((cp/'manifest.json').read_bytes())
        assert manifest['binding']['seed'] == seed and manifest['binding']['total_steps'] == 2
        for rank in (0, 1):
            assert receipt['ranks'][rank]['saved'][-1]['manifest_sha256'] == sha(cp/'manifest.json')
        for name, desc in manifest['files'].items():
            path = cp/name
            assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
            assert desc == {'bytes': path.stat().st_size, 'sha256': sha(path)}
        locked.append({'sequence': seq, 'arm': arm, 'seed': seed, 'manifest_sha256': sha(cp/'manifest.json'),
            'weights_sha256': sha(cp/'model.safetensors')})
    return locked


def tfidf_stage(args):
    from phase1.g_reuse_fixed_tfidf import fit_fixed_tfidf
    locked = lock_finals(args.verification_sha)
    assert not args.output.exists(); args.output.mkdir(mode=0o700)
    atomic_json(args.output/'final_model_lock.json', {'models': locked, 'independent_receipt_sha256': args.verification_sha})
    data_root = TRAIN/'inputs'
    obj = json.loads((data_root/'spec.json').read_bytes())
    spec = TrainProjectionSpec(obj['source_package_sha256'], obj['split_receipt_sha256'],
        **{key: PinnedFile(**obj[key]) for key in ('topology', 'local_targets', 'global_targets')})
    prepared = load_training_inputs(data_root, spec, Tokenizer(), encoder=ENCODER, protocol_sha256=PROTOCOL_SHA256)
    plan = prepare_screen(prepared)[0].plan
    truth = load_training_targets(data_root, spec, prepared, plan=plan)
    top = read_pinned(data_root, spec.topology)
    train_codes = {c['endpoint_id']: c['code'] for c in top['cards']}
    train_pairs = [(r.a.card_id, r.b.card_id) if truth(r.key) == 1 else (r.b.card_id, r.a.card_id) for r in prepared.pools[1]]
    baseline = fit_fixed_tfidf(train_codes, train_pairs)
    dev, pairs = dev_fixture()
    assert set(train_codes).isdisjoint(c['endpoint_id'] for c in dev)
    scores, query = baseline.score({c['endpoint_id']: c['code'] for c in dev})
    atomic_json(args.output/'tfidf_scores.synthetic.json', {'scores': scores, 'fit': baseline.fit_receipt, 'query': query})
    print(json.dumps({'stage': 'train_only_tfidf_complete', 'frozen_neural_models': len(locked),
        'train_pairs': len(train_pairs), 'dev_endpoints': len(dev), 'development_truths_joined': False}), flush=True)


def neural_stage(args):
    import torch
    from torch import nn
    from safetensors.torch import load_file
    from transformers import Qwen3Config, Qwen3Model
    from phase1.g_reuse_endpoint_inference import encode_endpoints, score_endpoints
    from phase1.global_local_critic_session import state_fingerprint
    from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    locked = lock_finals(args.verification_sha)
    assert json.loads((args.output/'final_model_lock.json').read_bytes())['models'] == locked
    reference = source_definitions(args.source_root)
    cards, pairs = dev_fixture(); encoded = encode_endpoints(cards, Tokenizer(), max_len=16384)
    baseline_path = args.output/'tfidf_scores.synthetic.json'; baseline_sha = sha(baseline_path)
    by_model = {'tfidf': json.loads(baseline_path.read_bytes())['scores']}; receipts = []
    for item in locked:
        cls = reference['BradleyTerryRewardModel']; model = cls.__new__(cls); nn.Module.__init__(model)
        model.backbone = Qwen3Model(Qwen3Config(vocab_size=128, hidden_size=16, intermediate_size=32,
            num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=8,
            max_position_embeddings=256, pad_token_id=0, use_cache=False, attn_implementation='eager', attention_dropout=.1))
        model.head = nn.Linear(16, 1, dtype=torch.float32)
        weights = TRAIN/f"fit{item['sequence']}-full"/'checkpoint-2'/'model.safetensors'
        assert sha(weights) == item['weights_sha256']
        before = time.monotonic(); model.load_state_dict(load_file(str(weights)), strict=True)
        load_seconds = time.monotonic()-before
        model.eval(); initial = state_fingerprint(model.state_dict())
        before = time.monotonic()
        scores, receipt = score_endpoints(model, encoded, pad_id=0, batch_size=2, device='cpu')
        query_seconds = time.monotonic()-before
        assert initial == state_fingerprint(model.state_dict()) and all(p.grad is None for p in model.parameters())
        by_model[f"{item['arm']}|{item['seed']}"] = scores
        receipts.append({'sequence': item['sequence'], 'load_seconds': load_seconds, 'query_seconds': query_seconds,
            'forward_calls': receipt['forward_calls'], 'endpoints': receipt['endpoints']})
    blind = blind_development_margins(pairs, by_model)
    atomic_json(args.output/'blinded_margins.synthetic.json', {'rows': blind, 'model_lock_sha256': sha(args.output/'final_model_lock.json')})
    margin_sha = sha(args.output/'blinded_margins.synthetic.json')
    # Synthetic truth is constructed only after every prediction is fixed. This
    # order is a functional check, NOT a real-data access-control demonstration.
    truth = {row['pair_sha256']: (1 if i%2 == 0 else -1) for i, row in enumerate(pairs)}
    joined = join_development_truth(blind, truth)
    report = evaluate_development(joined, protocol_sha256=PROTOCOL_SHA256,
        fit_status={key: 'COMPLETED' for key in KEYS-{'tfidf'}})
    # Independent exact task/seed recount, not importing credit or compare.
    for seed in (6, 7):
        task_values = []
        for task in sorted({r['task_sha256'] for r in joined}):
            rows = [r for r in joined if r['task_sha256'] == task]; numerator = 0
            for row in rows:
                vals = []
                for key in (f'{FULL}|{seed}', f'Lbudget|{seed}'):
                    m = row['margins'][key]; vals.append(1 if m == 0 else 2 if m*row['truth_sign'] > 0 else 0)
                numerator += vals[0]-vals[1]
            task_values.append(Fraction(numerator, 2*len(rows)))
        assert float(sum(task_values)/len(task_values)) == report['primary_full_minus_lbudget']['seed_effects'][str(seed)]
    assert baseline_sha == sha(baseline_path) and margin_sha == sha(args.output/'blinded_margins.synthetic.json')
    assert not torch.cuda.is_initialized()
    atomic_json(args.output/'readout.synthetic.json', report)
    result = {'classification': 'SYNTHETIC_TRAINED_FINAL_TO_DEVELOPMENT_READOUT_NOT_RESEARCH_EFFECT',
        'code_commit': os.environ['DEVELOPMENT_PIPELINE_COMMIT'], 'script_sha256': sha(Path(__file__)),
        'trained_models_loaded': len(locked), 'same_pool_models_including_tfidf': len(by_model),
        'development_pairs': len(joined), 'development_endpoints': len(encoded),
        'joint_predictions_fixed_before_synthetic_truth_join': True, 'independent_seed_recount_equal': True,
        'weights_unchanged_by_query': True, 'model_lock_sha256': sha(args.output/'final_model_lock.json'),
        'blind_margin_sha256': margin_sha, 'tfidf_artifact_sha256': baseline_sha,
        'readout_sha256': sha(args.output/'readout.synthetic.json'), 'query_receipts': receipts,
        'real_data_read': False, 'gpu_validated': False, 'method_gain_claimed': False}
    atomic_json(args.output/'summary.json', result)
    print(json.dumps(result, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--stage', choices=('tfidf', 'neural'), required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--verification-sha', required=True)
    parser.add_argument('--source-root', required=True); args = parser.parse_args()
    assert args.output.parent == Path('/tmp') and args.output.name.startswith('development-final-pipeline-')
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and len(os.environ.get('DEVELOPMENT_PIPELINE_COMMIT', '')) == 40
    assert args.output.resolve() == args.output
    (tfidf_stage if args.stage == 'tfidf' else neural_stage)(args)


if __name__ == '__main__': main()
