"""Independent metadata/Git-object checks and read-only Slurm failure receipt."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE = Path('/research/d7/spc/yzyang4')
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
def safe_read(path, expected=None):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential_shape_withheld'
    if expected:
        assert digest(raw) == expected, 'input_hash_changed'
    return raw
def run(args):
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf', TZ='UTC')
    p = subprocess.run(args, env=env, capture_output=True, timeout=30)
    assert not SECRET.search(p.stdout + p.stderr), 'credential_shape_withheld'
    return p
receipt_raw = safe_read(BASE/'recorded-commit-recovery-20260907.json', '428db130b5eff7016469867c5d6c98288909449feceb087e9057c968e03b65cb')
receipt = json.loads(receipt_raw)
ledger = json.loads(safe_read(BASE/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json', '8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'))
scope = json.loads(safe_read(BASE/'historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json', 'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b'))
chosen = scope['selected_runs']
assert len(chosen) == len(set(chosen)) == 84 and set(chosen) <= set(ledger)
counts = collections.defaultdict(lambda: [0, 0])
for rid, row in ledger.items():
    commits = set(item['recorded_runner_git_commit'] for item in row['origins'])
    assert len(commits) == 1
    commit = next(iter(commits))
    assert re.fullmatch('[0-9a-f]{40}', commit)
    counts[commit][0] += 1
    counts[commit][1] += rid in chosen
records = {row['commit']: row for row in receipt['records']}
assert len(records) == len(receipt['records']) and set(records) == set(counts)
repo = BASE/'aira-dojo-reproduce'
verified = 0
for commit, (all_n, selected_n) in counts.items():
    row = records[commit]
    assert [row['historical_runs'], row['fixed_84_runs']] == [all_n, selected_n]
    commit_obj = run(['git', '-C', str(repo), 'cat-file', 'commit', commit])
    assert (commit_obj.returncode == 0) == row['git_commit_readable']
    if commit_obj.returncode == 0:
        tree = commit_obj.stdout.splitlines()[0].decode().removeprefix('tree ')
        assert tree == row['git_tree']
        tree_obj = run(['git', '-C', str(repo), 'cat-file', 'tree', tree])
        assert tree_obj.returncode == 0
        framed = b'tree ' + str(len(tree_obj.stdout)).encode() + b'\0' + tree_obj.stdout
        assert hashlib.sha1(framed).hexdigest() == tree
        inventory = run(['git', '-C', str(repo), 'ls-tree', '-r', commit])
        assert inventory.returncode == 0 and digest(inventory.stdout) == row['tree_inventory_sha256']
        verified += selected_n
assert verified == receipt['fixed_scope_runs_with_readable_commit'] == 84
jobroot = BASE/'critic-pivot-shape/job-12577'
artifacts = {}
for name in ('allocation.json', 'build_tools.json', 'space-probe.json', 'worker.log', 'driver.log', 'exit_status.txt'):
    raw = safe_read(jobroot/name)
    artifacts[name] = {'sha256': digest(raw), 'bytes': len(raw)}
driver = safe_read(jobroot/'driver.log').decode()
error_lines = [line for line in driver.splitlines() if 'ImportError:' in line and 'FlashAttention2' in line]
assert error_lines and all('doesn\'t seem to be installed' in line for line in error_lines)
accounting = run(['sacct', '-X', '-n', '-P', '-j', '12577', '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode,Start,End,NodeList'])
assert accounting.returncode == 0
rows = [line.split('|') for line in accounting.stdout.decode().splitlines() if line.strip()]
assert len(rows) == 1
jobid, state, elapsed, tres, code, start, end, node = rows[0][:8]
assert jobid == '12577' and state == 'FAILED' and code == '1:0'
gpus = int(next(v.split('=')[1] for v in tres.split(',') if v.startswith('gres/gpu=')))
queue = run(['squeue', '-h', '-j', '12535', '-o', '%i|%T|%r'])
assert queue.returncode == 0
result = {
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'script_sha256': digest(Path(__file__).read_bytes()),
    'verified_receipt_sha256': digest(receipt_raw),
    'historical_runs': len(ledger), 'recorded_commits': len(counts),
    'readable_commits': sum(r['git_commit_readable'] for r in records.values()),
    'fixed_scope_runs': len(chosen), 'fixed_scope_commits': sum(n[1] > 0 for n in counts.values()),
    'fixed_scope_runs_with_readable_commit': verified,
    'missing_commits_in_fixed_scope': sum(not records[c]['git_commit_readable'] for c, n in counts.items() if n[1]),
    'job': {'id': jobid, 'state': state, 'exit_code': code, 'elapsed_seconds': int(elapsed),
            'allocated_gpus': gpus, 'gpu_seconds': int(elapsed)*gpus, 'start': start, 'end': end,
            'requested_display_timezone': 'UTC', 'node': node, 'error': error_lines[0],
            'artifacts': artifacts, 'trajectory_summary_present': (jobroot/'trajectories/summary.json').exists()},
    'held_job_queue': queue.stdout.decode().strip(),
    'new_gpu_submission': False, 'training_admission': False,
    'runtime_or_uncommitted_changes_attested': False, 'journal_or_outcome_payload_reads': 0,
    'protected_cohort_reads': 0,
}
raw = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).encode()
assert not SECRET.search(raw)
with (BASE/'recorded-commit-recovery-independent-20260907.json').open('xb') as f:
    f.write(raw)
print(raw.decode())
print('receipt_sha256=' + digest(raw))
