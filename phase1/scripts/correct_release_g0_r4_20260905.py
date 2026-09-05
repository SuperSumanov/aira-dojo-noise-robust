"""Historical one-job correction; never submit, retry, or modify a running job."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path('/research/d7/spc/yzyang4')
OUT=ROOT/'critic-component-g0/submissions/20260905-g0-r4'
CONTROL=ROOT/'worktrees/g0_r4_46cd8f4_sparse'
SOURCE=ROOT/'worktrees/critic-g0-final-only-20260903-b'
OLD='46cd8f42b3f4ed0f986b35ee1c3bdca0d94ab117'
NEW='adbfa80180e44805a6c0231e55c000b4718ad23b'
ENV=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf',PYTHONDONTWRITEBYTECODE='1',
         GIT_LFS_SKIP_SMUDGE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
def call(*args):
    return subprocess.check_output(list(map(str,args)),env=ENV,stderr=subprocess.PIPE,timeout=180)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,data):
    with (OUT/name).open('x') as f:
        json.dump(data,f,sort_keys=True,indent=2)
def state():
    raw=call('scontrol','show','job','-o','12486').decode()
    return dict(re.findall(r'\b([A-Za-z][A-Za-z0-9/]*)=(\S+)',raw))
os.umask(0o077)
try:
    before=state()
    assert before['JobState']=='PENDING' and before['Reason']=='JobHeldUser'
    assert before['RunTime']=='00:00:00' and before['Restarts']=='0' and before['Requeue']=='0'
    assert before['NodeList']=='(null)' and before['TimeLimit'] in {'01:55:00','01:49:00'}
    assert sha(OUT/'READY.json')=='84c353122a703e2e1d68489601f5669e945254aa91ba8df559462750e967fdf2'
    assert sha(OUT/'SUBMITTED.json')=='769efcc1f4b4efd3b2f83f21bab7400a8e42f210a4918cb44ad0076be6fb550f'
    old_hashes=json.loads((OUT/'READY.json').read_bytes())['control_hashes']
    assert all(sha(CONTROL/path)==digest for path,digest in old_hashes.items())
    assert call('git','-C',CONTROL,'rev-parse','HEAD').decode().strip()==OLD
    assert not call('git','-C',CONTROL,'status','--porcelain','--untracked-files=all').strip()
    config=call('scontrol','show','config').decode()
    assert re.search(r'^KillWait\s*= 300 sec$',config,re.M)
    assert re.search(r'^OverTimeLimit\s*= 0 min$',config,re.M)
    if (OUT/'correction_before.json').exists():
        saved=json.loads((OUT/'correction_before.json').read_bytes())
        assert saved['old_control_commit']==OLD and saved['new_control_commit']==NEW
        assert not (OUT/'CORRECTED_READY.json').exists() and not (OUT/'RELEASED.json').exists()
    else:
        write('correction_before.json',{'state':before,'old_control_commit':OLD,'new_control_commit':NEW,
            'old_READY_sha256':sha(OUT/'READY.json'),'old_SUBMITTED_sha256':sha(OUT/'SUBMITTED.json'),
            'kill_wait_seconds':300,'scheduler_margin_seconds':60,'reason':'minute_rounding_and_exit_grace'})
    call('scontrol','update','JobId=12486','TimeLimit=01:49:00')
    call('git','-C',CONTROL,'cat-file','-e',NEW+'^{commit}')
    # Only our new, clean, held-job control changes; the trainer/source never changes.
    call('git','-C',CONTROL,'switch','--detach',NEW)
    assert not call('git','-C',CONTROL,'status','--porcelain','--untracked-files=all').strip()
    new_hashes={path:sha(CONTROL/path) for path in old_hashes}
    changed={path for path in old_hashes if old_hashes[path]!=new_hashes[path]}
    assert changed=={'phase1/verify_critic_component_g0.py','phase1/tests/test_g0_r4_budget.py',
                     'phase1/scripts/prepare_submit_g0_r4_20260905.py'}
    assert call('git','-C',SOURCE,'rev-parse','HEAD').decode().strip()=='5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
    assert not call('git','-C',SOURCE,'status','--porcelain','--untracked-files=all').strip()
    tests=['test_verify_critic_component_g0.py','test_g0_r4_budget.py','test_g0_output_isolation_smoke.py','test_g0_launcher_fake_accelerate_smoke.py']
    p=subprocess.run([ROOT/'venvs/exp/bin/python','-B','-m','pytest','-q','-p','no:cacheprovider',
                     *['phase1/tests/'+name for name in tests]],cwd=CONTROL,env=ENV,capture_output=True,timeout=120)
    (OUT/'corrected_tests.stdout').write_bytes(p.stdout)
    (OUT/'corrected_tests.stderr').write_bytes(p.stderr)
    assert p.returncode==0 and not p.stderr
    held=state()
    assert held['JobState']=='PENDING' and held['Reason']=='JobHeldUser' and held['RunTime']=='00:00:00'
    assert held['TimeLimit']=='01:49:00'
    assert held['Partition']=='gpu_24h' and held['QOS']=='gpu' and held['ReqNodeList']=='projgpu39'
    assert held['NumCPUs']=='12' and held['MinMemoryNode']=='0' and 'gres/gpu=2' in held['TRES'].split(',')
    used=582
    assert used+2*(6540+300+60)==14382 < 14400
    write('CORRECTED_READY.json',{'status':'CORRECTED_READY_HELD','job_id':12486,'control_commit':NEW,
          'control_hashes':new_hashes,'source_unchanged':True,'worker_and_training_config_unchanged':True,
          'walltime_seconds':6540,'exit_grace_seconds':300,'scheduler_margin_seconds':60,
          'budget_gpu_seconds_with_margin':14382,'new_jobs_in_correction':0,'preallocation_runtime_seconds':0})
    call('scontrol','release','12486')
    after=state()
    write('RELEASED.json',{'status':'ORIGINAL_JOB_RELEASED','job_id':12486,'scheduler':after,
                         'control_commit':NEW,'time_limit':'01:49:00'})
    print(json.dumps({'status':'ORIGINAL_JOB_RELEASED','job_id':12486,'state':after['JobState'],
          'reason':after['Reason'],'start_estimate':after.get('StartTime'),'time_limit':after['TimeLimit'],
          'tests':p.stdout.decode().strip(),'budget_gpu_seconds_with_margin':14382}))
except Exception as e:
    print(json.dumps({'status':'CORRECTION_FAILED_CLOSED','type':type(e).__name__}))
    raise SystemExit(1)
