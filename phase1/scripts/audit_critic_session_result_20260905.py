"""Independently inspect this turn's OWN synthetic checkpoints, never a corpus.

No producer/consumer implementation imports. Only the fixed private /tmp output
is admitted. Verify manifest hashes before loading the locally generated pickle
RNG files (which contain NumPy objects). This is not an untrusted-file loader.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tarfile

import numpy as np
import torch
from safetensors.torch import load_file


ROOT = Path('/tmp/critic-session-33ad8ba-vod7xI')
DS = Path('/tmp/ds-restore-6d42547-ufPK0D')
SOURCE_COMMIT = '33ad8baca0f23fd54ea4e79c5c23f3c44bbef2ec'
OBSERVER_COMMIT = '6d425476aff3394f10442befc4d1f7c7bccd4e04'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def obj(path):
    return json.loads(path.read_text())


def same(a, b):
    assert type(a) is type(b), (type(a), type(b))
    if isinstance(a, torch.Tensor):
        assert a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    elif isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape and np.array_equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a: same(a[k], b[k])
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for x, y in zip(a, b): same(x, y)
    else:
        assert a == b


def validate_checkpoint(path):
    m = obj(path/'manifest.json')
    assert set(p.name for p in path.iterdir()) == set(m['files']) | {'manifest.json'}
    for name, record in m['files'].items():
        p = path/name
        assert p.is_file() and not p.is_symlink() and p.stat().st_nlink == 1
        assert record == {'bytes': p.stat().st_size, 'sha256': sha(p)}
    return m


def compare_checkpoint(a, b):
    same(load_file(str(a/'model.safetensors')), load_file(str(b/'model.safetensors')))
    same(torch.load(a/'optimizer.bin', map_location='cpu', weights_only=True),
         torch.load(b/'optimizer.bin', map_location='cpu', weights_only=True))
    for rank in range(2):
        # Only our hash-checked synthetic RNG snapshots; no data pickle admitted.
        same(torch.load(a/f'random_states_{rank}.pkl', weights_only=False, map_location='cpu'),
             torch.load(b/f'random_states_{rank}.pkl', weights_only=False, map_location='cpu'))


def code_archive_unchanged(archive, code):
    count = 0
    with tarfile.open(archive) as tar:
        for member in tar:
            if member.isfile():
                expected = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                assert sha(code/member.name) == expected
                count += 1
    return count


def main():
    assert not torch.cuda.is_initialized()
    assert '40 passed' in (ROOT/'tests.txt').read_text()
    assert '25 passed' in (DS/'tests.txt').read_text()
    files, checkpoints, direct_comparisons, rank_trajectories = [], 0, 0, 0
    for tag in ('a', 'b'):
        run = ROOT/tag
        assert obj(run/'summary.json')['code_commit'] == SOURCE_COMMIT
        files += [(run/'summary.json', tag+'/summary.json'), (run/'runs.csv', tag+'/runs.csv')]
        for arm in ('G_to_L', 'Ghash_to_L'):
            paths = {name: run/(arm+'-'+name) for name in ('full','prefix2','resume2','prefix3','resume3')}
            trajectories = {name: obj(p/'trajectory.json') for name,p in paths.items()}
            for name, p in paths.items():
                row = trajectories[name]
                assert row['arm'] == arm and row['seed'] == 6
                assert [r['rank'] for r in row['ranks']] == [0, 1]
                files.append((p/'trajectory.json', tag+'/'+p.name+'/trajectory.json'))
                for cp in sorted(p.glob('checkpoint-*')):
                    manifest = validate_checkpoint(cp); checkpoints += 1
                    assert manifest['binding']['world'] == 2
                    for entry in ['manifest.json', 'observed_0.json', 'observed_1.json']:
                        files.append((cp/entry, tag+'/'+p.name+'/'+cp.name+'/'+entry))
            full = trajectories['full']
            assert sum(e['local_valid_tokens'] for r in full['ranks'] for e in r['records']) == full['planned_tokens']
            for cut in (2, 3):
                prefix, resume = trajectories[f'prefix{cut}'], trajectories[f'resume{cut}']
                for rank in (0, 1):
                    ref, pre, res = (t['ranks'][rank] for t in (full, prefix, resume))
                    assert pre['start'] == 0 and pre['end'] == res['start'] == cut and res['end'] == 4
                    assert pre['restored'] is False and res['restored'] is True
                    assert pre['records'] + res['records'] == ref['records']
                    assert res['state'] == ref['state']
                    rank_trajectories += 1
                for other, step in ((f'prefix{cut}', cut), (f'resume{cut}', 4)):
                    compare_checkpoint(paths['full']/f'checkpoint-{step}', paths[other]/f'checkpoint-{step}')
                    direct_comparisons += 1
    for a, relative in list(files):
        if relative.startswith('a/'):
            b = ROOT/'b'/Path(relative).relative_to('a')
            # Framework binary serialization need not be byte-identical; the
            # manifest embeds those file hashes. Compare trajectory/summary CSV.
            if a.name in ('trajectory.json','summary.json','runs.csv'):
                assert a.read_bytes() == b.read_bytes()
    ds = obj(DS/'source_control_flow.json')
    assert ds['code_commit'] == OBSERVER_COMMIT and ds['unguarded_failure_invoked_fallback'] is True
    assert len(ds['cases']) == 2 and all(c['pass'] is True for c in ds['cases'])
    source_counts = {
        'ddp': code_archive_unchanged(Path('/tmp/critic_session_code_20260905_33ad8ba.tar'), ROOT/'code'),
        'ds_observer': code_archive_unchanged(Path('/tmp/ds_restore_observer_20260905_6d42547.tar'), DS/'code')}
    result = {'classification':'INDEPENDENT_SYNTHETIC_CHECKPOINT_RECHECK_NOT_PRODUCTION',
        'code_commit':SOURCE_COMMIT, 'observer_commit':OBSERVER_COMMIT,
        'all_checkpoint_manifests_verified':checkpoints, 'direct_checkpoint_state_comparisons':direct_comparisons,
        'rank_prefix_plus_resume_equals_full':rank_trajectories,
        'a_b_summary_csv_trajectory_bytes_equal':True, 'code_files_unchanged':source_counts,
        'gpu_initialized':torch.cuda.is_initialized(), 'real_data_opened':False,
        'deserialized_only_own_hash_checked_synthetic_checkpoints':True,
        'packages':{k:importlib.metadata.version(k) for k in ('torch','accelerate','transformers','deepspeed','safetensors','numpy')},
        'auditor_sha256':sha(Path(__file__))}
    with (ROOT/'independent_verification.json').open('x') as f:
        json.dump(result,f,sort_keys=True,indent=2)
    files += [(ROOT/'tests.txt','tests.txt'), (ROOT/'a.log','a.log'), (ROOT/'b.log','b.log'),
              (ROOT/'independent_verification.json','independent_verification.json'),
              (DS/'tests.txt','ds/tests.txt'), (DS/'source_control_flow.json','ds/source_control_flow.json'),
              (DS/'source.log','ds/source.log')]
    inventory={dest:{'bytes':src.stat().st_size,'sha256':sha(src)} for src,dest in files}
    with (ROOT/'artifact_inventory.json').open('x') as f: json.dump(inventory,f,sort_keys=True,indent=2)
    files.append((ROOT/'artifact_inventory.json','artifact_inventory.json'))
    with tarfile.open(ROOT/'safe_artifacts.tar','x') as tar:
        for src,dest in files: tar.add(src,arcname=dest,recursive=False)
    print(json.dumps(result,sort_keys=True))
    print('SAFE_ARTIFACTS_SHA256='+sha(ROOT/'safe_artifacts.tar'))


if __name__ == '__main__': main()
