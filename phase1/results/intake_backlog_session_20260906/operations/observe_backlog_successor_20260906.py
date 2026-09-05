"""Independently check both bounded session receipt chains and latest audit."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

BASE = Path('/research/d7/spc/yzyang4')
STATE = BASE/'prospective_decision_v1'
roots = [(BASE/'session-0904-maturity-intake-20260906',
          'f780e525f0c060ea417f4ab0a1357f52d8a859e43846c2cfdaadf4e1ce2158f6'),
         (BASE/'session-intake-backlog-successor-20260906',
          '08006e4ca6ed17bdc8cf19900c7806a5897da1cb34141a9e2f1f303e7e68e21c')]
counts = ('all_physical_runs', 'eligible_runs', 'eligible_endpoints', 'eligible_structural_pairs', 'eligible_tasks')
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    assert p.resolve(strict=True) == p and p.is_file() and p.stat().st_size < 2_000_000
    raw = p.read_bytes(); assert not secret.search(raw)
    return json.loads(raw)
prior = '76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285'
rows = []; last = None; first = None
for group, (root, code_sha) in enumerate(roots):
    wrappers = sorted(root.glob('wrapper-*.json'))
    assert len(wrappers) == 7 if group == 0 else 1 <= len(wrappers) <= 8
    assert len(list(root.glob('poll-*'))) == len(wrappers)
    assert [p.name for p in wrappers] == [f'wrapper-{i:03d}.json' for i in range(len(wrappers))]
    for i, p in enumerate(wrappers):
        w = read(p); rp = root/f'poll-{i:03d}'/'receipt.json'; r = read(rp)
        assert w['poll'] == i and w['wrapper_sha256'] == code_sha
        assert w['foreground_receipt_sha256'] == digest(rp)
        assert r['returncode'] == r['stream_credential_shape_hits'] == 0
        assert r['before']['latest'] == prior and r['no_gpu_api_or_model_fit'] and not r['values_or_private_identities_emitted']
        if first is None: first = r['before']
        if last is not None: assert r['started_epoch'] >= last['finished_epoch']+300
        if group == 1:
            assert r['started_epoch'] >= dt.datetime.fromisoformat('2026-09-05T20:39:13+00:00').timestamp()
            assert w['predecessor_final_receipt_sha256'] == 'e2235374374ff3b6cb99fa1f7d8b092d0e88a11de9b9b3607cbefd33b296122b'
        assert all(type(r['after'][k]) is int and r['after'][k] >= r['before'][k] for k in counts)
        prior = r['after']['latest']; last = r
        rows.append({'session': group, 'poll': i, 'receipt_sha256': digest(rp), 'latest': prior,
            'finished_utc': dt.datetime.fromtimestamp(r['finished_epoch'], dt.timezone.utc).isoformat(),
            'counts': {k: r['after'][k] for k in counts},
            'delta': {k: r['after'][k]-r['before'][k] for k in counts}})
assert (STATE/'LATEST').read_text().strip() == prior
assert digest(STATE/'snapshots'/prior/'accumulator/summary.json') == last['after']['summary_sha256']
snapshot, artifact_name, manifest = (BASE/'prospective-snapshot-delta-chain/monitor_v1/state.tsv').read_text().strip().split('\t')
artifact = Path(artifact_name)
assert snapshot == prior and artifact.is_relative_to(BASE/'prospective-snapshot-delta-chain/artifacts_v1')
assert digest(artifact/'SHA256SUMS') == manifest
assert not (artifact/'FAILED').exists() and (artifact/'COMPLETE').is_file()
assert all(not p.is_symlink() and (not p.is_file() or not p.stat().st_mode & 0o222) for p in artifact.rglob('*'))
lines = (artifact/'SHA256SUMS').read_text().splitlines()
for line in lines:
    h, name = line.split('  ', 1); p = Path(name)
    assert p.is_relative_to(artifact) and digest(p) == h
assert (artifact/'receipt_a.json').read_bytes() == (artifact/'receipt_b.json').read_bytes()
assert (artifact/'grounded_a.json').read_bytes() == (artifact/'grounded_b.json').read_bytes()
a,b = read(artifact/'receipt_a.json'),read(artifact/'grounded_a.json')
assert a['status'] == 'PROSPECTIVE_SNAPSHOT_APPEND_ONLY_DELTA_VERIFIED'
assert b['status'] == 'GROUNDED_PROSPECTIVE_SNAPSHOT_DELTA_VERIFIED'
assert a['current_snapshot_sha256'] == prior and a['security'] == b['security']
assert a['transactions'] == b['transactions'] and a['inventory']['delta'] == b['inventory_delta']
assert not a['security']['outcomes_predictions_accuracy_utility_read']
assert not a['security']['archive_drop_run_endpoint_pair_candidate_identities_emitted']
assert (artifact/'security.txt').read_text() == 'network_hits=0\nforbidden_path_hits=0\ncredential_hits=0\n'
print(json.dumps({'classification': 'INDEPENDENT_TWO_SESSION_RECEIPT_CHAIN_ONLY', 'observations': rows,
    'initial': first, 'current': last['after'], 'total_delta': {k: last['after'][k]-first[k] for k in counts},
    'next_call_not_before_utc': dt.datetime.fromtimestamp(last['finished_epoch']+300,dt.timezone.utc).isoformat(),
    'audit_manifest_sha256': manifest, 'audit_artifact': artifact_name, 'audit_files_rehashed': len(lines),
    'label_outcome_prediction_values_read': False, 'all_audit_files_readonly': True}, sort_keys=True))
