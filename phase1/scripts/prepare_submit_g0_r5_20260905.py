"""One bounded G0 allocation. Prepare is separate; uncertain submits never retry."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE = Path('/research/d7/spc/yzyang4')
OUT = BASE/'critic-component-g0/submissions/20260905-g0-r5'
SOURCE = BASE/'worktrees/critic-g0-final-only-20260903-b'
SOURCE_COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
RUNTIME = BASE/'venvs/critic-blackwell-g0-20260905-r5'
OLD = BASE/'critic-component-g0/submissions/20260904-g0-r3'
SHAPE = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
ENV = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf', PYTHONDONTWRITEBYTECODE='1',
           CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
           MKL_NUM_THREADS='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def run(argv, timeout=300):
    proc = subprocess.run(list(map(str, argv)), env=ENV, capture_output=True, timeout=timeout)
    require(not SHAPE.search(proc.stdout+proc.stderr), 'credential_shape_no_disclosure')
    if proc.returncode and OUT.is_dir():
        with (OUT/'failed_subprocess.stdout').open('xb') as stream:
            stream.write(proc.stdout)
        with (OUT/'failed_subprocess.stderr').open('xb') as stream:
            stream.write(proc.stderr)
    require(proc.returncode == 0, 'subprocess_failed_'+Path(str(argv[0])).name)
    return proc.stdout


def record(name, value):
    with (OUT/name).open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.write('\n')


def accounting():
    expected = {'12181':156,'12288':4,'12377':131,'12486':191,'12497':1}
    raw = run(['sacct','-X','-n','-P','-j',','.join(expected),
               '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode()
    jobs = {}
    used = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        jid,state,elapsed,tres,code = line.split('|')[:5]
        require(jid in expected and jid not in jobs,'accounting_identity')
        metadata = jid == '12497'
        require(state == ('COMPLETED' if metadata else 'FAILED'),'accounting_state')
        require(code == ('0:0' if metadata else '1:0'),'accounting_exit')
        cards = 1 if metadata else 2
        require(f'gres/gpu={cards}' in tres.split(','),'accounting_gpus')
        require(int(elapsed) == expected[jid],'accounting_elapsed')
        jobs[jid] = int(elapsed)
        used += cards*int(elapsed)
    require(len(jobs)==5 and used==965,'accounting_total')
    require(used+2*(6300+300+60)==14285 < 14400,'budget')
    require(not run(['squeue','-h','-u','yzyang4','-o','%i']).strip(),'queue_nonempty')
    return {'elapsed_seconds':jobs,'allocated_gpu_seconds':used,'new_walltime_seconds':6300,
            'exit_grace_seconds':300,'scheduler_margin_seconds':60,
            'total_gpu_seconds_upper_bound':used+2*(6300+300+60)}


def bind(control, commit):
    require(re.fullmatch('[0-9a-f]{40}', commit), 'bad_commit')
    for root, expected in ((control,commit),(SOURCE,SOURCE_COMMIT)):
        require(root.resolve(strict=True) == root, 'root_resolution')
        require(run(['git','-C',root,'rev-parse','HEAD']).decode().strip() == expected, 'git_head')
        require(not run(['git','-C',root,'status','--porcelain','--untracked-files=all']).strip(), 'dirty_git')
    require(not os.access(SOURCE, os.W_OK), 'source_writable')
    helpers = {'/tmp/check_official_storage_20260903.py':'3e45c41f8a37ddd410e874bc60a484092f3a507a6f74717e48bbb369a576ca1c'}
    for path, expected in helpers.items():
        require(sha(path) == expected, 'helper_drift')
    require(sha(RUNTIME/'bin/ninja')=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','ninja_drift')
    setup = BASE/'critic-component-g0/runtime-repair-20260905-r5'
    cpu = json.loads((setup/'cpu_check_login.json').read_text())
    require(cpu['status']=='REAL_CPU_ADAM_COMPILE_INIT_UPDATE_PASS' and not cpu['gpu_context_created'],'cpu_adam_check')
    require(max(cpu['max_absolute_error_by_update'])<=1e-6,'cpu_adam_reference')
    inventory = json.loads((setup/'target-inventory-12497.log').read_text())
    require(inventory['hostname']=='projgpu39' and not inventory['model_load'],'target_inventory')
    require(any(row['path']=='/usr/local/cuda-12.8' and all(row[k] for k in ('nvcc','cuda_h','runtime_h','libcudart','libcurand')) for row in inventory['cuda_roots']),'target_cuda_toolchain')
    return {str(path.relative_to(control)):sha(path) for path in sorted(control.rglob('*'))
            if path.is_file() and '.git' not in path.parts}


def prepare(control, commit):
    bound = bind(control, commit)
    budget = accounting()
    OUT.mkdir(mode=0o700)
    record('prepare_intent.json', {'commit':commit,'utc':dt.datetime.now(dt.timezone.utc).isoformat(),**budget})
    for rel in ('critic_component_g0_worker_20260821.sh','critic_component_g0_shared_pro6000_20260821.sbatch'):
        run(['bash','-n',control/'phase1/scripts'/rel])
    run(['/usr/bin/strace','-f','-qq','-e','trace=%file','-o',OUT/'trace_smoke.log','/bin/true'])
    storage = json.loads(run([RUNTIME/'bin/python','-B','/tmp/check_official_storage_20260903.py']))
    record('storage.json', storage)
    require(storage['checkpoint_reservation'] == 'PASS' and storage['own_diagnostic_file_removed'], 'storage_reservation')
    require(storage['resulting_file_bytes'] == storage['resulting_allocated_bytes'] == 4294967296, 'storage_bytes')
    rebound = json.loads(run([RUNTIME/'bin/python','-B',control/'phase1/scripts/rebind_g0_r5_runtime_20260905.py']))
    record('runtime.json', rebound)
    require(rebound == json.loads((OLD/'recovery_binding.json').read_bytes()), 'runtime_changed')
    tests = ['test_verify_critic_component_g0.py','test_g0_r4_budget.py','test_g0_r5_budget.py',
             'test_g0_output_isolation_smoke.py','test_g0_launcher_fake_accelerate_smoke.py']
    proc = subprocess.run([BASE/'venvs/exp/bin/python','-B','-m','pytest','-q','-p','no:cacheprovider',
                           *['phase1/tests/'+f for f in tests]], cwd=control, env=ENV, capture_output=True, timeout=90)
    (OUT/'tests.stdout').write_bytes(proc.stdout)
    (OUT/'tests.stderr').write_bytes(proc.stderr)
    require(proc.returncode == 0 and not SHAPE.search(proc.stdout+proc.stderr), 'focused_tests_failed')
    run([RUNTIME/'bin/python','-B',control/'phase1/verify_critic_component_g0.py','assets',
         '--source-root',SOURCE,'--expected-source-commit',SOURCE_COMMIT,
         '--train-pairs',BASE/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
         '--dev-pairs',BASE/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl',
         '--cards',BASE/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
         '--model-snapshot',BASE/'cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1',
         '--model-manifest',control/'phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256',
         '--receipt',OUT/'assets.json'])
    assets = json.loads((OUT/'assets.json').read_bytes())
    old = json.loads((BASE/'critic-component-g0/source-repair-12288-20260904/static_assets_receipt.json').read_bytes())
    for key in ('source','inputs','runtime','fixed_config'):
        require(assets[key] == old[key], 'asset_drift_'+key)
    require(bind(control,commit) == bound, 'control_changed')
    record('READY.json', {'control_commit':commit,'control_hashes':bound,'budget':budget,
                         'status':'READY_NOT_SUBMITTED','checkpoint_reservation_bytes':4294967296})
    print(json.dumps({'status':'READY_NOT_SUBMITTED',**budget}))


def submit(control, commit):
    ready = json.loads((OUT/'READY.json').read_bytes())
    require(ready['control_commit'] == commit and bind(control,commit) == ready['control_hashes'], 'prepared_binding')
    budget = accounting()
    require(budget == ready['budget'], 'prepared_budget')
    record('SUBMISSION_INTENT.json', {'max_jobs':1,'retry':False,'commit':commit,**budget})
    exported = ','.join(['PATH=/usr/local/bin:/usr/bin:/bin',f'G0_CONTROL_ROOT={control}',f'G0_SOURCE_ROOT={SOURCE}',
        f'G0_EXPECTED_SOURCE_COMMIT={SOURCE_COMMIT}',f'G0_VENV={RUNTIME}','G0_RECOVERY_FINAL_ONLY=1',
        'G0_BUDGET_REVISION=20260905-r5','CUDA_HOME=/usr/local/cuda-12.8','G0_TRACE_FILES=1','PYTHONDONTWRITEBYTECODE=1','MAX_JOBS=2'])
    command = ['sbatch','--parsable','--hold','--no-requeue','--time=01:45:00','--job-name=critic_g0_r5_20260905',
               f'--output={OUT}/slurm-%j.out',f'--error={OUT}/slurm-%j.out',f'--export={exported}',
               str(control/'phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch')]
    record('command.json', command)
    proc = subprocess.run(command, env=ENV, capture_output=True, timeout=60)
    (OUT/'sbatch.stdout').write_bytes(proc.stdout)
    (OUT/'sbatch.stderr').write_bytes(proc.stderr)
    record('sbatch_status.json', {'returncode':proc.returncode})
    require(proc.returncode == 0, 'submission_failed_do_not_retry')
    jid = proc.stdout.decode().strip().split(';')[0]
    require(re.fullmatch(r'\d+',jid), 'submission_uncertain_do_not_retry')
    record('SUBMITTED.json', {'job_id':int(jid),'commit':commit,**budget})
    (OUT/'scheduler_receipt.txt').write_bytes(run(['scontrol','show','job','-o',jid]))
    print(json.dumps({'status':'SUBMITTED_HELD_NOT_RUNNING','job_id':int(jid),**budget}))


def release(control, commit):
    ready = json.loads((OUT/'READY.json').read_bytes())
    require(ready['control_commit']==commit and bind(control,commit)==ready['control_hashes'],'release_binding')
    submitted = json.loads((OUT/'SUBMITTED.json').read_text())
    jid = str(submitted['job_id'])
    queue = run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()
    require(queue == [jid],'unexpected_queue_before_release')
    line = run(['scontrol','show','job','-o',jid]).decode()
    fields = dict(part.split('=',1) for part in line.split() if '=' in part)
    exact = {'JobId':jid,'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00',
             'TimeLimit':'01:45:00','Requeue':'0','Restarts':'0','NumCPUs':'12',
             'CPUs/Task':'12','MinMemoryNode':'0','ReqNodeList':'projgpu39',
             'Partition':'gpu_24h','QOS':'gpu'}
    require(all(fields.get(k)==v for k,v in exact.items()),'held_scheduler_drift')
    require('gres/gpu=2' in fields.get('TRES','').split(','),'held_gpu_drift')
    record('VERIFIED_HELD.json',{'job_id':int(jid),'scheduler_fields':fields,'control_commit':commit})
    run(['scontrol','release',jid])
    record('RELEASED.json',{'job_id':int(jid),'control_commit':commit,'status':'RELEASED',
                           'budget':ready['budget'],'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    print(json.dumps({'status':'RELEASED','job_id':int(jid),'gpu_seconds_upper_bound':14285}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare','submit','release'])
    parser.add_argument('--control',required=True,type=Path)
    parser.add_argument('--commit',required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        {'prepare':prepare,'submit':submit,'release':release}[args.action](args.control,args.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','type':type(exc).__name__,
                         'reason':str(exc) if isinstance(exc,RuntimeError) else 'detail_withheld'}))
        raise SystemExit(1)
