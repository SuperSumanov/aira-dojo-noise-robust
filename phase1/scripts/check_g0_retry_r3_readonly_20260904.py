"""Read only the approved submission's structural receipts and scheduler metadata."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/critic-component-g0/submissions/20260904-g0-r3')
SOURCE = Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b')
ENV = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
PATTERN = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def read(name):
    p = ROOT/name
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 64*1024:
        raise RuntimeError('unsafe_submission_receipt')
    raw = p.read_bytes()
    if PATTERN.search(raw):
        raise RuntimeError('credential_shape_hit')
    return raw


def main():
    if ROOT.resolve(strict=True) != ROOT:
        raise RuntimeError('submission_root_resolution')
    jid = read('job_id.txt').decode().strip()
    if not re.fullmatch(r'\d+', jid):
        raise RuntimeError('bad_job_id')
    if read('sbatch_exit.txt') != b'sbatch_exit=0\n' or read('orchestrator_exit.txt') != b'orchestrator_exit=0\n':
        raise RuntimeError('submit_did_not_complete')
    names = ('submit.sh', 'intent.txt', 'source_and_budget_preflight.json', 'storage_test.json',
             'recovery_binding.json', 'inputs.sha256', 'scheduler_receipt.txt', 'SUBMITTED',
             'submission_attempted_at_utc.txt', 'sbatch.stdout', 'sbatch.stderr')
    raw = {name: read(name) for name in names}
    storage = json.loads(raw['storage_test.json'])
    binding = json.loads(raw['recovery_binding.json'])
    before = json.loads(raw['source_and_budget_preflight.json'])
    assert storage['checkpoint_reservation'] == 'PASS'
    assert storage['resulting_allocated_bytes'] == storage['resulting_file_bytes'] == 4294967296
    assert storage['own_diagnostic_file_removed']
    assert before['allocated_gpu_seconds_used'] == 320
    assert before['proposed_cumulative_gpu_seconds'] == 14360
    assert binding['status'] == 'UNCHANGED_RUNTIME_SOURCE_AND_CPU_SAVE_REGRESSION_BOUND'
    original = re.findall(rb'^sbatch --parsable', raw['submit.sh'], re.M)
    assert len(original) == 1 and b'--no-requeue --time=01:57:00' in raw['submit.sh']
    text = subprocess.check_output(['scontrol', 'show', 'job', '-o', jid], env=ENV).decode()
    fields = dict(re.findall(r'\b([A-Za-z][A-Za-z0-9/]*)=(\S+)', text))
    expected = {'JobId':jid, 'JobName':'critic_g0_r3_20260904', 'Partition':'gpu_24h', 'QOS':'gpu',
                'TimeLimit':'01:57:00', 'Requeue':'0', 'Restarts':'0', 'NumTasks':'1',
                'NumCPUs':'12', 'CPUs/Task':'12', 'MinMemoryNode':'0', 'ReqNodeList':'projgpu39'}
    for key, value in expected.items():
        if fields.get(key) != value:
            raise RuntimeError('scheduler_contract_mismatch_'+key)
    # Slurm 19.05 prints pending requests as min-max; 1-1 is exactly one node.
    if fields.get('NumNodes') not in ('1', '1-1'):
        raise RuntimeError('scheduler_contract_mismatch_NumNodes')
    if 'gres/gpu=2' not in fields.get('TRES','').split(','):
        raise RuntimeError('scheduler_gpu_mismatch')
    queue = subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'], env=ENV).decode().split()
    if fields['JobState'] in ('RUNNING','PENDING') and queue != [jid]:
        raise RuntimeError('unexpected_own_queue')
    keep = ('JobId','JobName','JobState','Reason','Partition','QOS','Requeue','Restarts','TimeLimit',
            'RunTime','SubmitTime','EligibleTime','StartTime','EndTime','NodeList','ReqNodeList',
            'NumNodes','NumCPUs','CPUs/Task','MinMemoryNode','TRES','ExcNodeList')
    git = lambda *args: subprocess.check_output(['git','-C',str(SOURCE),*args]).decode().strip()
    assert git('rev-parse','HEAD') == '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
    assert not git('status','--porcelain','--untracked-files=all')
    return {'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'status':'G0_R3_SUBMISSION_INDEPENDENTLY_VERIFIED',
            'job_id':int(jid), 'scheduler':{k:fields.get(k) for k in keep},
            'scheduler_receipt_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'artifact_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
            'source_clean':True,'source_commit':git('rev-parse','HEAD'),'checkpoint_storage_check_bytes':4294967296,
            'checkpoint_storage_check_utc':storage['utc'],'temporary_storage_check_removed':True,
            'new_gpu_jobs_submitted':1,'prior_allocated_gpu_seconds':320,'max_new_wall_seconds':7020,
            'max_cumulative_gpu_seconds':14360,'max_cumulative_gpu_hours':14360/3600,
            'runtime_packages_rebound':binding['package_versions_rechecked'],
            'runtime_critical_hashes_rebound':binding['runtime_critical_hashes_rechecked'],
            'five_arm_training_submitted':False,'protected_cohort_values_read':False}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch(r'[A-Za-z0-9/_-]+', str(exc)) else 'detail_withheld'
        print(json.dumps({'status':'READ_ONLY_CHECK_FAILED_CLOSED','exception_type':type(exc).__name__,'safe_reason':reason}))
        raise SystemExit(1)
