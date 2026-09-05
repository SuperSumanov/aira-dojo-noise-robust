import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile

os.umask(0o077)
out = Path('/tmp/critic-boundary-evidence-20260906')
assert not out.exists(); out.mkdir()
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1<<20), b''): h.update(b)
    return h.hexdigest()
def put(name, value):
    with (out/name).open('x') as f: json.dump(value, f, sort_keys=True, indent=2)
def read(p): return json.loads(p.read_bytes())

bindings = []
for archive, code, expected in (
    ('/tmp/critic_accum8_064da23.tar', '/tmp/critic-accum8-code-064da23', '62c29b95b37dbba6d76b9a9786265f02fc2437dce6ee61bfc9f99f0b51c5cdf3'),
    ('/tmp/critic_zero3_readout_8f96819.tar', '/tmp/critic-zero3-readout-code-8f96819', '0538e582a7359edc4b750575d975e159e4caab88fd8bfa765868e0747a107a9d')):
    assert sha(Path(archive)) == expected
    with tarfile.open(archive) as tar:
        n = 0
        for m in tar:
            if m.isfile():
                assert tar.extractfile(m).read() == (Path(code)/m.name).read_bytes(); n += 1
    bindings.append({'archive_sha256': expected, 'files_unchanged_after_execution': n})
put('source_verification.json', bindings)
markers = (b'/external/senior_data/', b'/prospective_decision_v1/', b'label_vault.jsonl',
    b'/d_test/', b'cards_current_', b'decision_clean_', b'decision_pairs_runsplit')
checks = []
for repeat in ('a', 'b'):
    path = Path('/tmp/critic-accum8-code-064da23')/f'trace-{repeat}.private'
    hits = {m.decode(): 0 for m in markers}; lines = 0
    with path.open('rb') as f:
        for line in f:
            lines += 1
            for m in markers: hits[m.decode()] += int(m in line)
    assert not any(hits.values())
    checks.append({'repeat': repeat, 'sha256': sha(path), 'bytes': path.stat().st_size,
                   'lines': lines, 'forbidden_literal_path_hits': hits})
put('trace_negative_scan.json', {'checks': checks, 'scope': 'accum8 file/process literal path checks only',
    'not_OS_or_network_isolation': True, 'converter_tests_not_straced': True})
rows = []
for repeat in ('a', 'b'):
    root = Path('/tmp/critic-entry-cpu-accum8-064da23-'+repeat)
    shutil.copyfile(root/'summary.json', out/f'{repeat}_summary.json')
    for seq, mode in [(1,'full'), (2,'full'), (1,'prefix'), (1,'resume'), (2,'prefix'), (2,'resume')]:
        directory = root/f'fit{seq}-{mode}'
        r = read(directory/'run_receipt.json')
        logs = [[json.loads(s) for s in (directory/f'rank_{rank}_updates.jsonl').read_text().splitlines()] for rank in (0, 1)]
        rows.append({'code_commit': '064da23b6643437d8f7aca4dc393e7b58989c456', 'repeat': repeat,
            'sequence': seq, 'arm': r['arm'], 'seed': r['seed'], 'trajectory': mode,
            'parameters': 4433, 'world': 2, 'pairs_per_rank': 8, 'accumulation': 8,
            'dtype': 'float32', 'optimizer': 'AdamW', 'weight_decay': 0, 'dropout': .1,
            'start_step': r['start_step'], 'end_step': r['stop_step'], 'status': r['status'],
            'actual_pair_visits': sum(x['local_pair_visits'] for log in logs for x in log),
            'actual_valid_tokens': sum(x['local_valid_tokens'] for log in logs for x in log),
            'plan_sha256': r['plan_sha256'], 'segment_seconds_max_rank': max(x['segment_elapsed_seconds'] for x in r['ranks']),
            'warmup_first_update_seconds_max_rank': max(x['first_update_seconds'][0] for x in r['ranks']),
            'later_update_seconds_max_rank': max(s for x in r['ranks'] for s in x['later_update_seconds']),
            'GPU_hours': 0, 'classification': 'ENGINEERING_ONLY_NOT_EFFECT', 'setup_or_queue_time_included': False})
with (out/'runs.csv').open('x', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
assert len(rows) == 12
shutil.copyfile('/tmp/critic-entry-cpu-accum8-064da23-a/independent_verification.json', out/'independent_verification.json')
for sub, prefix in (('', 'converter_initial_failure'), ('retry-tests-with-pytest/', 'converter_tests')):
    root = Path('/tmp/critic-zero3-readout-code-8f96819')/sub
    for name in ('receipt.json', 'tests.txt'): shutil.copyfile(root/name, out/f'{prefix}_{name}')
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
for p in out.iterdir(): assert not secret.search(p.read_bytes())
manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(out.iterdir())}
put('manifest.json', manifest)
archive = Path('/tmp/critic-boundary-evidence-20260906.tar')
assert not archive.exists()
with tarfile.open(archive, 'w') as t:
    for p in sorted(out.iterdir()): t.add(p, arcname=p.name, recursive=False)
print(json.dumps({'archive_sha256': sha(archive), 'bytes': archive.stat().st_size,
    'files': len(manifest)+1, 'engineering_trajectories': len(rows),
    'independent_verification_sha256': sha(out/'independent_verification.json'), 'secret_hits': 0}, sort_keys=True))
