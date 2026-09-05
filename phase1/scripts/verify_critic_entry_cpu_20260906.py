"""Independent actual state/consumption checks of our synthetic CPU runs only."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    assert path.is_file() and path.stat().st_uid == os.getuid() and path.stat().st_nlink == 1
    assert not any(x.is_symlink() for x in (path, *path.parents)) and path.stat().st_size < 1_000_000
    return json.loads(path.read_bytes())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--a', type=Path, required=True); p.add_argument('--b', type=Path, required=True)
    p.add_argument('--layout', choices=('tiny', 'accum8'), default='tiny')
    args = p.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    import torch
    from safetensors.torch import load_file
    from phase1.scripts.verify_zero3_engineering_20260905 import same
    torch.set_num_threads(1)
    full_sequences = (1, 2, 3, 4) if args.layout == 'tiny' else (1, 2)
    cases = [(i, 'full') for i in full_sequences]+[(i, m) for i in (1, 2) for m in ('prefix', 'resume')]
    final_step, prefix_step = (2, 1) if args.layout == 'tiny' else (4, 2)
    total_tokens = 592 if args.layout == 'tiny' else 20064
    files = {'model.safetensors', 'optimizer.bin', 'random_states_0.pkl', 'random_states_1.pkl',
             'observed_0.json', 'observed_1.json'}
    checkpoints = []; actual_compares = 0; state_compares = 0
    for root in (args.a, args.b):
        assert root.parent == Path('/tmp') and root.name.startswith('critic-entry-cpu-')
        for seq, mode in cases:
            directory = root/f'fit{seq}-{mode}'
            receipt = read(directory/'run_receipt.json')
            states = read(directory/'engineering_state.json')
            stop = prefix_step if mode == 'prefix' else final_step
            assert receipt['status'] == ('CHECKPOINTED_NOT_COMPLETED' if mode == 'prefix' else 'COMPLETED')
            assert receipt['sequence'] == seq and receipt['stop_step'] == stop
            expected_saves = list(range(prefix_step+1, stop+1)) if mode == 'resume' else list(range(1, stop+1))
            for step in expected_saves:
                cp = directory/f'checkpoint-{step}'
                manifest = read(cp/'manifest.json')
                assert set(manifest['files']) == files and {p.name for p in cp.iterdir()} == files|{'manifest.json'}
                for name, descriptor in manifest['files'].items():
                    path = cp/name
                    assert path.stat().st_uid == os.getuid() and path.stat().st_nlink == 1 and not path.is_symlink()
                    assert descriptor == {'bytes': path.stat().st_size, 'sha256': sha(path)}
                for rank in (0, 1):
                    saved = [x for x in receipt['ranks'][rank]['saved'] if x['step'] == step]
                    assert len(saved) == 1 and saved[0]['manifest_sha256'] == sha(cp/'manifest.json')
                    observed = read(cp/f'observed_{rank}.json')
                    assert observed['binding'] == manifest['binding'] and observed['completed_steps'] == step
                    if step == stop:
                        assert observed['state'] == states['ranks'][rank]['final_state']
                checkpoints.append({'repeat': 'a' if root == args.a else 'b', 'case': f'fit{seq}-{mode}',
                    'step': step, 'manifest_sha256': sha(cp/'manifest.json'),
                    'payload_bytes': sum(x['bytes'] for x in manifest['files'].values())})
            for rank in (0, 1):
                logs = [json.loads(line) for line in (directory/f'rank_{rank}_updates.jsonl').read_text().splitlines()]
                assert [x['step'] for x in logs] == expected_saves
                # Independently fixed fixture expectations; not imported from
                # the producer's plan or its cumulative token declarations.
                counts = [4, 4] if args.layout == 'tiny' else ([128, 6, 128, 2] if seq == 1 else [128, 2, 128, 6])
                tokens_per_pair = 74 if args.layout == 'tiny' else 76
                for x in logs:
                    expected_pairs = counts[x['step']-1]
                    assert x['global_update_pairs'] == expected_pairs
                    assert x['local_pair_visits'] == expected_pairs//2
                    assert x['local_valid_tokens'] == expected_pairs//2*tokens_per_pair
                    assert x['cumulative_global_valid_tokens'] == sum(counts[:x['step']])*tokens_per_pair
        for left, right in (((1, 2), (4, 3)) if args.layout == 'tiny' else ((1, 2),)):
            a = read(root/f'fit{left}-full'/'engineering_state.json')
            b = read(root/f'fit{right}-full'/'engineering_state.json')
            assert a['seed'] == b['seed'] and a['tokens'] == b['tokens'] == total_tokens
            assert all(a['ranks'][r]['initial_model_sha256'] == b['ranks'][r]['initial_model_sha256'] for r in (0, 1))
        if args.layout == 'tiny':
            assert read(root/'fit1-full'/'engineering_state.json')['ranks'][0]['initial_model_sha256'] != read(root/'fit4-full'/'engineering_state.json')['ranks'][0]['initial_model_sha256']
        for seq in (1, 2):
            paths = {mode: root/f'fit{seq}-{mode}' for mode in ('full', 'prefix', 'resume')}
            for rank in (0, 1):
                logs = {mode: [json.loads(x) for x in (path/f'rank_{rank}_updates.jsonl').read_text().splitlines()]
                        for mode, path in paths.items()}
                stable = lambda rows: [{k: v for k, v in x.items() if k not in ('update_seconds', 'first_update_of_process')} for x in rows]
                assert stable(logs['prefix']+logs['resume']) == stable(logs['full'])
                assert read(paths['resume']/'engineering_state.json')['ranks'][rank]['final_state'] == read(paths['full']/'engineering_state.json')['ranks'][rank]['final_state']
                state_compares += 1
            for mode, step in (('prefix', prefix_step), ('resume', final_step)):
                a, b = paths['full']/f'checkpoint-{step}', paths[mode]/f'checkpoint-{step}'
                # All bytes were checked against the run's own pinned manifests
                # above. These are generated here, not arbitrary external pickle.
                same(load_file(str(a/'model.safetensors')), load_file(str(b/'model.safetensors')))
                same(torch.load(a/'optimizer.bin', weights_only=True, map_location='cpu'),
                     torch.load(b/'optimizer.bin', weights_only=True, map_location='cpu'))
                for rank in (0, 1):
                    same(torch.load(a/f'random_states_{rank}.pkl', weights_only=False, map_location='cpu'),
                         torch.load(b/f'random_states_{rank}.pkl', weights_only=False, map_location='cpu'))
                actual_compares += 1
    for seq, mode in cases:
        assert (args.a/f'fit{seq}-{mode}'/'engineering_state.json').read_bytes() == (args.b/f'fit{seq}-{mode}'/'engineering_state.json').read_bytes()
    assert not torch.cuda.is_initialized()
    result = {'classification': 'INDEPENDENT_PINNED_TRAIN_CPU_LIFECYCLE_NOT_EFFECT',
        'verifier_sha256': sha(Path(__file__)), 'trajectories': len(cases)*2,
        'layout': args.layout,
        'checkpoint_bundles': len(checkpoints), 'actual_state_comparisons': actual_compares,
        'rank_final_state_comparisons': state_compares, 'exact_resumed_consumption': True,
        'AB_engineering_state_bytes_equal': True, 'timings_not_expected_equal': True,
        'CUDA_initialized': False, 'checkpoint_receipts': checkpoints,
        'source_qualification_or_GPU_acceptance': False}
    with (args.a/'independent_verification.json').open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
