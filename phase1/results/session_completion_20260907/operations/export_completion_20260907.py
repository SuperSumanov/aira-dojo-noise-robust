"""Export completed program proof and explicitly incomplete GPU postflight."""
import csv, datetime, hashlib, io, json, os, re, subprocess
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
O = B / 'completion-safe-export-20260907-0909'
S = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def read(p, cap=2**20):
    assert p.resolve(strict=True) == p and p.is_file() and p.stat().st_nlink == 1
    assert 0 < p.stat().st_size <= cap
    raw = p.read_bytes()
    assert not S.search(raw)
    return raw, json.loads(raw)

def put(name, raw):
    assert not S.search(raw)
    with (O/name).open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    (O/name).chmod(0o400)

mapping = {
    'program_pack.json': ('historical-program-pack-f702ba2-r2-20260907/SUMMARY.json', '8384d2824c4105ea14c49d35ba20840713eaa5f3555924abc563e0918e7401fb'),
    'program_pack_independent.json': ('historical-program-pack-independent-20260907/VERIFIED.json', None),
    'ampere_authentication.json': ('critic-pivot-ampere-postflight-12664-20260907/AUTHENTICATED.json', None),
}
pending = {}; records = {}
for name, (rel, expected) in mapping.items():
    raw, value = read(B/rel)
    h = hashlib.sha256(raw).hexdigest()
    assert expected is None or h == expected
    if name == 'program_pack.json':
        assert value['A_B_identical'] and value['programs_executed'] == 0 and value['source_admitted'] is False
    elif name == 'program_pack_independent.json':
        assert value['producer_summary_sha256'] == mapping['program_pack.json'][1]
        assert value['python_and_gnu_hashes_agree'] and value['programs_executed'] == 0
    else:
        assert value['job_id'] == '12664' and value['source_commit'] == '88522f74cafcd45778751c5315fa0a89a1704965'
        assert len(value['segments']) == 2
        assert not (B/'critic-pivot-ampere-postflight-12664-20260907/VERIFIED.json').exists()
        assert not Path('/proc/1946993').exists()
        verifier=B/'worktrees/critic-pivot-ampere-88522f74cafc/phase1/scripts/verify_pivot_ampere_artifacts_20260907.py'
        assert hashlib.sha256(verifier.read_bytes()).hexdigest()==value['verifier_sha256']
    pending[name] = raw
    records[name] = {'bytes': len(raw), 'sha256': h, 'original_relative_path': rel}

# Existing structural summary only: never read protected labels, code or IDs.
state = B/'prospective_decision_v1'
latest = (state/'LATEST').read_text().strip()
assert re.fullmatch('[0-9a-f]{64}', latest)
raw, summary = read(state/'snapshots'/latest/'accumulator'/'summary.json')
keys = ('all_physical_runs', 'eligible_runs', 'eligible_endpoints', 'eligible_structural_pairs', 'eligible_tasks')
counts = {k: summary['inventory'][k] for k in keys}
assert all(type(n) is int and n >= 0 for n in counts.values())
assert type(summary['closure']['provided']) is bool
root = B/'session-0905-intake-20260907'
wrappers = sorted(root.glob('wrapper-*.json')); posts = sorted(root.glob('post-audit-*.json'))
assert len(wrappers) == len(posts) == 15
_, last = read(root/'poll-014/receipt.json')
_, post = read(posts[-1])
assert last['after']['latest'] == post['snapshot'] == latest
assert post['foreground_receipt_sha256'] == hashlib.sha256((root/'poll-014/receipt.json').read_bytes()).hexdigest()
assert post['wrapper_sha256'] == hashlib.sha256(wrappers[-1].read_bytes()).hexdigest()
assert post['outcome_values_read'] is False and post['audit_readonly_verified'] is True
env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
accounting = subprocess.check_output(['sacct','-X','-n','-P','-j','12664','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=30).decode().strip()
j, status, elapsed, tres, rc = accounting.split('|')[:5]
assert j == '12664' and status == 'COMPLETED' and rc == '0:0' and 'gres/gpu=2' in tres.split(',')
auth = json.loads(pending['ampere_authentication.json'])
_, worker = read(B/'critic-pivot-ampere/job-12664/trajectories/summary.json')
assert worker['code_commit']==auth['source_commit'] and worker['slurm_job_id']==j
assert worker['model_effect_measured'] is False and worker['checkpoints']==2
_, allocation = read(B/'critic-pivot-ampere/job-12664/allocation.json')
prior = allocation['prior_gpu_seconds']
assert prior == 16502
source = B/'external/senior_data/mle'
archives = list(source.glob('*/*.tar.gz'))
assert all(p.is_file() and not p.is_symlink() and not S.search(str(p).encode()) for p in archives)
metadata = [(p.stat().st_size, p.stat().st_mtime_ns) for p in archives]
sidecars = list(source.rglob('*.config_v2.jsonl'))
observation = {
    'classification': 'READONLY_SESSION_COMPLETION_NOT_MODEL_EFFECT',
    'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'original_session_deadline_utc': '2026-09-07T03:53:36+00:00',
    'session_deadline_not_extended': True, 'completed_foreground_polls': len(posts),
    'last_poll': 14, 'latest': latest, 'summary_sha256': hashlib.sha256(raw).hexdigest(),
    'closure_provided': summary['closure']['provided'], **counts,
    'last_intake_finished_utc': datetime.datetime.fromtimestamp(last['finished_epoch'], datetime.timezone.utc).isoformat(),
    'last_postaudit_sha256': hashlib.sha256(posts[-1].read_bytes()).hexdigest(),
    'protected_outcome_values_read': False, 'gpu_job': j, 'slurm_state': status,
    'gpu_job_elapsed_seconds': int(elapsed), 'job_gpu_seconds': int(elapsed)*2,
    'prior_engineering_gpu_seconds': prior, 'cumulative_engineering_gpu_seconds': prior+int(elapsed)*2,
    'engineering_budget_gpu_seconds': 36000, 'new_gpu_submissions_in_closure': 0,
    'unstarted_poll_15_not_run_after_deadline': True,
    'independent_payload_postflight_complete': False,
    'postflight_limit_seconds': 900,
    'postflight_termination': 'OWN_CHECKER_TIME_BOUND_ENFORCED',
    'postflight_authenticated_receipt_exists': True,
    'postflight_actual_payload_checks_completed_not_reported': True,
    'archive_count_at_last_intake': last['source_archives'],
    'archive_count_now_metadata_only': len(archives),
    'archive_total_bytes_metadata_only': sum(n for n, _ in metadata),
    'latest_archive_mtime_ns_metadata_only': max(t for _, t in metadata),
    'config_v2_sidecar_count_metadata_only': len(sidecars),
    'new_archive_or_sidecar_payloads_opened_in_closure': 0,
}
pending['session_observation.json'] = json.dumps(observation,sort_keys=True,indent=2).encode()
records['session_observation.json'] = {'bytes':len(pending['session_observation.json']), 'sha256':hashlib.sha256(pending['session_observation.json']).hexdigest(), 'original_relative_path':None}
cost_helper = Path('/tmp/cost_completed_program_pack_20260907.py')
assert hashlib.sha256(cost_helper.read_bytes()).hexdigest() == 'f1b2a0cc032d71f2c5b61d99feb8a9912d07f6ccc6fa6f16bcfff1027c41b62d'
cost_raw = subprocess.check_output([str(B/'venvs/exp/bin/python'), str(cost_helper)], timeout=60)
assert not S.search(cost_raw)
cost = json.loads(cost_raw)
assert cost['sum_full_caps_gpu_seconds'] == 22912800 and cost['programs_executed'] == 0
pending['reexecution_cost_caps.json'] = cost_raw
records['reexecution_cost_caps.json'] = {'bytes':len(cost_raw), 'sha256':hashlib.sha256(cost_raw).hexdigest(), 'original_relative_path':None}
row = {
    'job_id': j, 'source_commit': auth['source_commit'], 'seed': 6,
    'arm': 'ENGINEERING_SYNTHETIC_G_TO_L_NOT_DEVELOPMENT',
    'parameters_reported_by_worker': worker['parameters'], 'context_length': 16384, 'gpu_count': 2,
    'gpu_type': 'RTX3090', 'dtype': 'BF16', 'attention': 'FlashAttention2',
    'optimizer': 'ZeRO3_CPUAdam', 'learning_rate': 1e-5,
    'pairs_per_rank_microbatch': 1, 'gradient_accumulation': 64, 'global_pair_batch': 128,
    'steps': 2, 'valid_tokens': sum(s['new_valid_tokens'] for s in auth['segments']),
    'wall_seconds': int(elapsed), 'allocated_gpu_seconds': int(elapsed)*2,
    'allocated_gpu_hours': int(elapsed)*2/3600,
    'steady_state_updates': sum(s['steady_state_updates'] for s in auth['segments']),
    'checkpoints': 2, 'checkpoint_rank_payload_checks': None,
    'model_effect_measured': False, 'full_size_uninterrupted_final_parity_measured': False,
    'source_admitted': False, 'verdict': 'GPU_WORKER_COMPLETED_INDEPENDENT_PAYLOAD_POSTFLIGHT_TIMED_OUT',
}
buffer=io.StringIO(newline=''); writer=csv.DictWriter(buffer,fieldnames=list(row))
writer.writeheader();writer.writerow(row); pending['runs.csv']=buffer.getvalue().encode()
records['runs.csv']={'bytes':len(pending['runs.csv']),'sha256':hashlib.sha256(pending['runs.csv']).hexdigest(),'original_relative_path':None}
assert (state/'LATEST').read_text().strip() == latest
os.umask(0o077)
assert not O.exists()
O.mkdir()
for name, raw in pending.items(): put(name, raw)
put('export_manifest.json', json.dumps({'files':records, 'credential_shape_hits':0, 'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},sort_keys=True,indent=2).encode())
print(json.dumps({'output':str(O), 'files':len(pending), 'session':observation, 'manifest_sha256':hashlib.sha256((O/'export_manifest.json').read_bytes()).hexdigest()},sort_keys=True))
