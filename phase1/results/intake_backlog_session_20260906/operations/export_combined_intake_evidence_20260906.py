"""Final export ONLY after the measured backlog and a genuine empty observation.

Date attribution comes from transaction metadata, never from number of calls.
Public output contains aggregate receipts, no source archive identifiers.
"""
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

os.umask(0o077)
BASE = Path('/research/d7/spc/yzyang4')
STATE = BASE/'prospective_decision_v1'
roots = [BASE/'session-0904-maturity-intake-20260906', BASE/'session-intake-backlog-successor-20260906']
out = Path('/tmp/intake-complete-session-evidence-20260906')
assert not out.exists()
assert len(list(roots[0].glob('wrapper-*.json'))) == 7 and len(list(roots[1].glob('wrapper-*.json'))) == 8
observed_raw = subprocess.check_output(['/research/d7/spc/yzyang4/venvs/exp/bin/python',
    '/tmp/observe_backlog_successor_20260906.py'], timeout=60)
observed = json.loads(observed_raw)
last_path = roots[1]/'poll-007/receipt.json'
last = json.loads(last_path.read_bytes())
stream = (roots[1]/'poll-007/stdout.private').read_bytes()
assert hashlib.sha256(stream).hexdigest() == last['stream_sha256']['stdout.private']
empty = re.fullmatch(rb'PROSPECTIVE_ARCHIVE_OBSERVATION_COMPLETE archives=(\d+) baseline=(\d+) ready=(\d+) rejected=(\d+) transactions=(\d+) outcomes_read=false\s*', stream)
assert empty is not None and int(empty.group(3)) == 0 and last['before'] == last['after']
initial = observed['initial']['latest']; latest = observed['current']['latest']
old_raw = (STATE/'snapshots'/initial/'transactions.jsonl').read_bytes()
new_raw = (STATE/'snapshots'/latest/'transactions.jsonl').read_bytes()
assert new_raw.startswith(old_raw)
old = [json.loads(x) for x in old_raw.splitlines()]; new = [json.loads(x) for x in new_raw.splitlines()]
for key in ('archive_relative_path','archive_sha256','drop_id'):
    assert len({r[key] for r in new}) == len(new)
days = Counter()
for r in new[len(old):]:
    p = Path(r['archive_relative_path'])
    assert not p.is_absolute() and len(p.parts) == 2 and re.fullmatch(r'\d{4}',p.parts[0])
    days[p.parts[0]] += 1
assert dict(days) == {'0903':8,'0904':6} and len(new)-len(old) == 14
out.mkdir()
(out/'independent_session_verification.json').write_bytes(observed_raw)
rows = []; snapshots = [initial]
for group, root in enumerate(roots):
    for i, wp in enumerate(sorted(root.glob('wrapper-*.json'))):
        directory = out/f'session-{group}-poll-{i:03d}'; directory.mkdir()
        rp = root/f'poll-{i:03d}/receipt.json'; r = json.loads(rp.read_bytes())
        shutil.copyfile(wp,directory/'wrapper.json'); shutil.copyfile(rp,directory/'receipt.json')
        if r['before']['latest'] != r['after']['latest']: snapshots.append(r['after']['latest'])
        rows.append({'session':group,'poll':i,'elapsed_seconds':r['elapsed_seconds'],'returncode':r['returncode'],
            'physical_runs':r['after']['all_physical_runs'],'eligible_runs':r['after']['eligible_runs'],
            'structural_pairs':r['after']['eligible_structural_pairs'],'eligible_tasks':r['after']['eligible_tasks'],
            'new_eligible_runs':r['after']['eligible_runs']-r['before']['eligible_runs'],
            'latest_sha256':r['after']['latest'],'GPU_hours':0,'model_effect_fit':False})
assert len(snapshots) == 15 and len(set(snapshots)) == 15
artifacts = BASE/'prospective-snapshot-delta-chain/artifacts_v1'
chain = []
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''): h.update(block)
    return h.hexdigest()
for i,snapshot in enumerate(snapshots):
    candidates = [p for p in artifacts.iterdir() if p.is_dir() and p.name.endswith('_'+snapshot[:12])
                  and p.name >= '20260905T194400Z']
    assert len(candidates) == 1
    source = candidates[0]
    assert (source/'COMPLETE').is_file() and not (source/'FAILED').exists()
    manifest = (source/'MANIFEST_SHA256').read_text().strip()
    assert sha(source/'SHA256SUMS') == manifest
    for line in (source/'SHA256SUMS').read_text().splitlines():
        expected,name = line.split('  ',1); p = Path(name)
        assert p.is_relative_to(source) and not p.is_symlink() and p.is_file()
        assert p.stat().st_mode & 0o222 == 0 and sha(p) == expected
    assert (source/'receipt_a.json').read_bytes() == (source/'receipt_b.json').read_bytes()
    assert (source/'grounded_a.json').read_bytes() == (source/'grounded_b.json').read_bytes()
    a,b = [json.loads((source/n).read_bytes()) for n in ('receipt_a.json','grounded_a.json')]
    assert a['current_snapshot_sha256'] == snapshot and a['security'] == b['security']
    assert a['transactions'] == b['transactions'] and a['inventory']['delta'] == b['inventory_delta']
    assert not a['security']['outcomes_predictions_accuracy_utility_read']
    assert not a['security']['archive_drop_run_endpoint_pair_candidate_identities_emitted']
    assert (source/'security.txt').read_text() == 'network_hits=0\nforbidden_path_hits=0\ncredential_hits=0\n'
    target = out/('prior_anchor_catchup' if i == 0 else f'delta-{i:03d}'); target.mkdir()
    for name in ('receipt_a.json','receipt_b.json','grounded_a.json','grounded_b.json','security.txt','COMPLETE','environment.txt','MANIFEST_SHA256'):
        shutil.copyfile(source/name,target/name)
    chain.append({'snapshot':snapshot,'artifact':str(source),'manifest_sha256':manifest,
                  'role':'prior_anchor_catchup_not_new_accrual' if i==0 else 'new_accrual'})
summary = {'classification':'OUTCOME_BLIND_ACCRUAL_NOT_METHOD_EFFECT','foreground_calls':len(rows),
    'new_transactions':len(new)-len(old),'new_transactions_by_archive_date':dict(days),
    'ready_after_last_observation':0,'current_archives':int(empty.group(1)),
    'current_transactions':int(empty.group(5)),'before':observed['initial'],'after':observed['current'],
    'total_delta':observed['total_delta'],'closure_provided':observed['current']['closure_provided'],
    'chain':chain,'labels_or_predictions_read':False,
    'correction':'First seven calls were 0903 backlog; six calls did not prove the six 0904 downloads were processed.'}
(out/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
shutil.copyfile('/tmp/intake-backlog-20260906-metadata.json',out/'backlog_diagnosis.json')
with (out/'runs.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
manifest = {}
for p in sorted(out.rglob('*')):
    if p.is_file():
        assert not secret.search(p.read_bytes())
        manifest[p.relative_to(out).as_posix()]={'bytes':p.stat().st_size,'sha256':sha(p)}
(out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
archive=Path('/tmp/intake-complete-session-evidence-20260906.tar'); assert not archive.exists()
with tarfile.open(archive,'w') as t:
    for p in sorted(out.rglob('*')):
        if p.is_file():t.add(p,arcname=p.relative_to(out).as_posix(),recursive=False)
print(json.dumps({'tar_sha256':sha(archive),'bytes':archive.stat().st_size,'files':len(manifest)+1,
    'summary':{k:v for k,v in summary.items() if k!='chain'}},sort_keys=True))
