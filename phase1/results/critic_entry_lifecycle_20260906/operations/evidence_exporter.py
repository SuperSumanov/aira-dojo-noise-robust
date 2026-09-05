import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

OUT = Path('/tmp/critic-entry-shareable-20260906')
assert not OUT.exists(); OUT.mkdir(mode=0o700)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1<<20), b''): h.update(block)
    return h.hexdigest()


def document(name, obj):
    with (OUT/name).open('x') as f: json.dump(obj, f, sort_keys=True, indent=2)


def read(path): return json.loads(path.read_bytes())


sources = []
for archive, code, expected in (
    ('/tmp/critic_entry_95e72f3.tar', '/tmp/critic-entry-code-95e72f3-r2', 'e54c299dbe7e3c85b1d2ab99f3327fe7eb68366e0b80f092774271fc5700de71'),
    ('/tmp/development_pipeline_0d0bcb7.tar', '/tmp/development-pipeline-code-0d0bcb7', '3e23a38382057b60d8e167d746d6b67da7039e3a63f3c566d3fc682a9815cac0')):
    assert digest(Path(archive)) == expected
    with tarfile.open(archive) as tar:
        count = 0
        for member in tar:
            if member.isfile():
                assert tar.extractfile(member).read() == (Path(code)/member.name).read_bytes()
                count += 1
    sources.append({'archive_sha256': expected, 'members_equal_after_execution': count})
document('source_verification.json', sources)
markers = (b'/external/senior_data/', b'/prospective_decision_v1/', b'label_vault.jsonl', b'/d_test/',
           b'cards_current_', b'decision_clean_', b'decision_pairs_runsplit')
scans = []
for label, path in (
    ('cpu-a', Path('/tmp/critic-entry-code-95e72f3-r2/trace-a.private')),
    ('cpu-b', Path('/tmp/critic-entry-code-95e72f3-r2/trace-b.private')),
    ('pipeline-tfidf', Path('/tmp/development-pipeline-code-0d0bcb7/pipeline-tfidf.trace.private')),
    ('pipeline-neural', Path('/tmp/development-pipeline-code-0d0bcb7/pipeline-neural.trace.private'))):
    hits = {marker.decode(): 0 for marker in markers}; lines = 0
    with path.open('rb') as f:
        for line in f:
            lines += 1
            for marker in markers: hits[marker.decode()] += int(marker in line)
    assert not any(hits.values())
    scans.append({'trace': label, 'sha256': digest(path), 'bytes': path.stat().st_size, 'lines': lines,
        'forbidden_literal_path_hits': hits})
document('trace_negative_scan.json', {'checks': scans, 'scope': 'literal markers in file/process strace only',
    'not_complete_path_resolution_or_OS_sandbox': True, 'network_syscalls_not_traced': True})
rows = []
for repeat in ('a', 'b'):
    root = Path('/tmp/critic-entry-cpu-95e72f3-'+repeat)
    shutil.copyfile(root/'summary.json', OUT/f'cpu_{repeat}_summary.json')
    for seq, mode in [(i, 'full') for i in (1,2,3,4)]+[(i, m) for i in (1,2) for m in ('prefix','resume')]:
        receipt = read(root/f'fit{seq}-{mode}'/'run_receipt.json')
        ranks = receipt['ranks']
        totals = []
        for rank in (0,1):
            records = [json.loads(line) for line in (root/f'fit{seq}-{mode}'/f'rank_{rank}_updates.jsonl').read_text().splitlines()]
            totals.append(sum(r['local_valid_tokens'] for r in records))
        rows.append({'code_commit': '95e72f37c1b745ca101390c887c41eed6e9b6f28', 'repeat': repeat,
            'sequence': seq, 'arm': receipt['arm'], 'seed': receipt['seed'], 'trajectory': mode,
            'parameters': 4433, 'world_size': 2, 'dtype': 'float32', 'optimizer': 'AdamW', 'weight_decay': 0,
            'max_context_contract': 16384, 'actual_tokens_this_segment': sum(totals),
            'start_step': receipt['start_step'], 'end_step': receipt['stop_step'],
            'plan_sha256': receipt['plan_sha256'], 'status': receipt['status'],
            'segment_seconds_max_rank': max(r['segment_elapsed_seconds'] for r in ranks),
            'first_update_seconds_max_rank': max(r['first_update_seconds'][0] for r in ranks),
            'later_update_seconds_max_rank': max((s for r in ranks for s in r['later_update_seconds']), default=None),
            'checkpoint_seconds_max_rank': max(sum(s['save_seconds'] for s in r['saved']) for r in ranks),
            'GPU_hours': 0, 'classification': 'ENGINEERING_ONLY_NOT_EFFECT', 'queue_and_setup_time_included': False})
with (OUT/'runs.csv').open('x', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for src, dst in (
    ('/tmp/critic-entry-cpu-95e72f3-a/independent_verification.json', 'independent_verification.json'),
    ('/tmp/development-final-pipeline-0d0bcb7/summary.json', 'development_pipeline_summary.json'),
    ('/tmp/development-final-pipeline-0d0bcb7/final_model_lock.json', 'development_final_model_lock.json'),
    ('/tmp/development-readout-code-0001c03/test_receipt.json', 'readout_initial_failure.json'),
    ('/tmp/development-readout-code-6394e37/test_receipt.json', 'readout_repaired_tests.json')):
    shutil.copyfile(src, OUT/dst)
assert len(rows) == 16
manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(OUT.iterdir())}
document('manifest.json', manifest)
archive = Path('/tmp/critic-entry-shareable-20260906.tar')
assert not archive.exists()
with tarfile.open(archive, 'w') as tar:
    for p in sorted(OUT.iterdir()): tar.add(p, arcname=p.name, recursive=False)
print(json.dumps({'archive_sha256': digest(archive), 'archive_bytes': archive.stat().st_size,
    'artifact_files': len(manifest)+1, 'engineering_trajectories': len(rows),
    'independent_verification_sha256': digest(OUT/'independent_verification.json'), 'forbidden_trace_marker_hits': 0}, sort_keys=True))
