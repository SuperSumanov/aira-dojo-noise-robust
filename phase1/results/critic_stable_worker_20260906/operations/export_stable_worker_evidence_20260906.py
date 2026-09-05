import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile

os.umask(0o077)
out = Path('/tmp/critic-stable-worker-evidence-20260906')
assert not out.exists()
out.mkdir()
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1<<20), b''): h.update(block)
    return h.hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def put(name, value):
    with (out/name).open('x') as f: json.dump(value, f, sort_keys=True, indent=2)
source = []
for name, code, expected in [
    ('critic_stable_resume_e5c9b69.tar', 'critic-stable-resume-code-e5c9b69', 'd78cbdecc4c6535aa00b5c2aca64fc2a0bd1b0ff900c15783a62cda333bbe841'),
    ('critic_stable_resume_cfee2b0.tar', 'critic-stable-resume-code-cfee2b0', 'f2ec10ae954abd7dfb71837726b8fa96e40bf1c1d08c0a477d30678873105a7b'),
    ('critic_worker_b361b5b.tar', 'critic-worker-code-b361b5b', '1e79cbb400711a0db5514e695e293a343ac64a9572326dd19f72651c3d3da15e')]:
    archive = Path('/tmp')/name
    assert sha(archive) == expected
    count = 0
    with tarfile.open(archive) as t:
        for m in t:
            if m.isfile():
                assert t.extractfile(m).read() == (Path('/tmp')/code/m.name).read_bytes()
                count += 1
    source.append({'archive': name, 'sha256': expected, 'source_files_verified': count})
put('source_verification.json', source)
ind = Path('/tmp/critic-entry-cpu-stable-cfee2b0-a/independent_verification.json')
v = read(ind)
assert v['contract_mode'] == 'split' and v['trajectories'] == 12 and v['checkpoint_bundles'] == 32
assert v['actual_state_comparisons'] == 8 and v['rank_final_state_comparisons'] == 8
shutil.copyfile(ind, out/'independent_verification.json')
rows, bindings, trace = [], [], []
markers = (b'/external/senior_data/', b'/prospective_decision_v1/', b'label_vault.jsonl',
    b'/d_test/', b'cards_current_', b'decision_clean_', b'decision_pairs_runsplit')
for repeat in ('a', 'b'):
    root = Path('/tmp/critic-entry-cpu-stable-cfee2b0-'+repeat)
    shutil.copyfile(root/'summary.json', out/f'{repeat}_summary.json')
    path = Path('/tmp/critic-stable-resume-code-cfee2b0')/f'trace-{repeat}.private'
    hits = {x.decode(): 0 for x in markers}; lines = 0; sentinel = 0
    with path.open('rb') as f:
        for line in f:
            lines += 1
            for marker in markers:
                hits[marker.decode()] += int(marker in line)
            # Creating/renaming/stat-ing our sentinel is not a read-open.
            sentinel += bool(re.search(rb'(?:open|openat|openat2)\(.*forbidden_dev\.json".*O_(?:RDONLY|RDWR)', line))
    assert not any(hits.values()) and sentinel == 0, hits
    trace.append({'repeat': repeat, 'sha256': sha(path), 'bytes': path.stat().st_size,
        'lines': lines, 'forbidden_literal_path_hits': hits, 'sentinel_read_open_hits': sentinel})
    for seq, mode in [(1,'full'), (2,'full'), (1,'prefix'), (1,'resume'), (2,'prefix'), (2,'resume')]:
        directory = root/f'fit{seq}-{mode}'
        r = read(directory/'run_receipt.json')
        binding = read(directory/'launch_binding_receipt.json')
        bindings.append({'repeat': repeat, 'sequence': seq, 'mode': mode, **binding})
        logs = [[json.loads(line) for line in (directory/f'rank_{rank}_updates.jsonl').read_text().splitlines()] for rank in (0, 1)]
        rows.append({'commit': 'cfee2b099fa4524892463c9d8c95f4e98f6e05d3', 'repeat': repeat, 'sequence': seq,
            'arm': r['arm'], 'seed': r['seed'], 'trajectory': mode, 'status': r['status'],
            'parameters': 4433, 'world': 2, 'pairs_per_rank': 8, 'accumulation': 8,
            'dtype': 'float32', 'optimizer': 'AdamW', 'weight_decay': 0, 'dropout': .1,
            'start_step': r['start_step'], 'end_step': r['stop_step'],
            'actual_pair_visits': sum(x['local_pair_visits'] for log in logs for x in log),
            'actual_valid_tokens': sum(x['local_valid_tokens'] for log in logs for x in log),
            'segment_seconds_max_rank': max(x['segment_elapsed_seconds'] for x in r['ranks']),
            'plan_sha256': r['plan_sha256'], 'GPU_hours': 0, 'model_effect_test': False})
with (out/'runs.csv').open('x', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
put('launch_definition_bindings.json', bindings)
put('trace_negative_scan.json', {'checks': trace, 'scope': 'literal file/process path negative checks only',
    'OS_or_network_isolation_claim': False, 'worker_tests_straced': False})
failed = Path('/tmp/critic-entry-cpu-stable-e5c9b69-a/fit1-full.log')
assert failed.is_file() and b'assert opened ==' in failed.read_bytes()
assert not list(failed.parent.glob('fit*/checkpoint-*'))
shutil.copyfile(failed, out/'initial_reader_list_failure.log')
put('initial_failure.json', {'commit': 'e5c9b6935cde07849ab4a9067a9fb0ad16c3a038',
    'failure': 'fixture observed-read expectation omitted newly opened definition.json',
    'before_training_updates': True, 'checkpoint_directories': 0, 'log_sha256': sha(failed)})
for name in ('tests.txt', 'receipt.json'):
    shutil.copyfile(Path('/tmp/critic-worker-code-b361b5b')/name, out/('worker_'+name))
assert read(out/'worker_receipt.json')['returncode'] == 0
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
for p in out.iterdir(): assert not secret.search(p.read_bytes())
manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(out.iterdir())}
put('manifest.json', manifest)
archive = Path('/tmp/critic-stable-worker-evidence-20260906.tar')
assert not archive.exists()
with tarfile.open(archive, 'w') as t:
    for p in sorted(out.iterdir()): t.add(p, arcname=p.name, recursive=False)
print(json.dumps({'archive_sha256': sha(archive), 'bytes': archive.stat().st_size, 'files': len(manifest)+1,
    'independent_verification_sha256': sha(ind), 'engineering_trajectories': len(rows),
    'secret_hits': 0}, sort_keys=True))
