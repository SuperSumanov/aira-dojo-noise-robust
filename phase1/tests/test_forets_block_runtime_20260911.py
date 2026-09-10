"""CPU OS-boundary fixtures; no live allocation, key, task data or model."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

PHASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PHASE))
import forets_block_runtime_20260911 as r
import forets_block_collect_20260911 as c
from phase1.tests.test_forets_block_controller_20260911 import prepared, pool_module, build_pool, Clock
from phase1.tests import test_forets_block_controller_20260911 as coretests


@contextmanager
def fixture_interrupt(budget,deadline):
    budget.left(deadline)
    yield
    budget.left(deadline)


def test_release_rejects_before_any_file_or_process(monkeypatch):
    def forbidden(*a,**kw): raise AssertionError('external access before release')
    monkeypatch.setattr(Path,'resolve',forbidden)
    monkeypatch.setattr(r.subprocess,'run',forbidden)
    for raw in (b'{}',b'{"readiness":true}'):
        with pytest.raises(RuntimeError,match='release absent'):
            r.execute_block('/not-opened',1,raw,node='gpu28',controller_commit='a'*40)


def test_budget_uses_actual_allocation_start(monkeypatch):
    monkeypatch.setattr(r.getpass,'getuser',lambda:'fixture-user')
    start=dt.datetime(2026,9,11,1,0,0)
    line='JobId=999 JobState=RUNNING UserId=fixture-user(1) NodeList=gpu28 NumNodes=1 NumCPUs=12 TRES=cpu=12,gres/gpu=2 '
    line+=f'StartTime={start.isoformat()} EndTime={(start+dt.timedelta(seconds=16800)).isoformat()}'
    budget=r.allocation_from_observation(line,job='999',node='gpu28',observed_wall=start.timestamp()+800,observed_mono=1000)
    assert budget.start==200 and budget.startup==1100 and budget.end==17000
    with pytest.raises(ValueError,match='startup'):
        r.allocation_from_observation(line,job='999',node='gpu28',observed_wall=start.timestamp()+901,observed_mono=1000)
    with pytest.raises(ValueError,match='owned'):
        r.allocation_from_observation(line.replace('gpu28','projgpu39'),job='999',node='projgpu39',observed_wall=start.timestamp(),observed_mono=1)


def test_service_env_is_minimal_and_has_no_credentials():
    value=r.service_environment(dict(PATH='/bin',SLURM_JOB_ID='999',PRIMARY_KEY='ARTIFICIAL',
        OPENROUTER_API_KEY='ARTIFICIAL',HTTP_PROXY='ARTIFICIAL',UNRELATED_TOKEN='ARTIFICIAL',PYTHONPATH='/unreviewed',
        SLURM_JWT='ARTIFICIAL',SLURM_EXPORT_ENV='ARTIFICIAL'))
    assert not set(value)&{'PRIMARY_KEY','OPENROUTER_API_KEY','HTTP_PROXY','UNRELATED_TOKEN','PYTHONPATH','SLURM_JWT','SLURM_EXPORT_ENV'}
    assert value['SLURM_JOB_ID']=='999' and value['PYTHON_DOTENV_DISABLED']=='1'


def test_scheduler_cancels_exact_owned_steps_only():
    clock=Clock(10);commands=[]
    def command(args,**kw):
        assert 0<kw['timeout']<=15
        commands.append(args)
        return NS(returncode=0,stdout='StepId=999.1 Name=forets-b1-critic\nStepId=12535.1 Name=forets-b1-critic\nStepId=999.2 Name=another-user-task')
    scheduler=r.Scheduler(r.Budget(0,16800,clock.monotonic),'999',run=command)
    steps=scheduler.active_owned({'forets-b1-critic'},30)
    assert steps==['999.1']
    scheduler.cancel(steps,30)
    assert commands[-1]==['scancel','--signal=TERM','999.1']
    with pytest.raises(ValueError,match='outside'): scheduler.cancel(['12535.1'],30)


def service_fixture(tmp_path,*,ready=True,wrong_job=False,live=True):
    clock=Clock(850);commands=[]
    budget=r.Budget(0,16800,clock.monotonic)
    def query(args,**kw):
        commands.append(args)
        return NS(returncode=0,stdout='StepId=999.1 Name=forets-b1-critic' if live else '')
    scheduler=r.Scheduler(budget,'999',run=query)
    class Process:
        ended=False
        def poll(self): return 0 if self.ended else None
        def terminate(self): self.ended=True
        def kill(self): self.ended=True
        def wait(self,timeout=None):
            if not self.ended: raise subprocess.TimeoutExpired('fixture',timeout)
            return 0
    process=Process()
    def popen(args,**kw):
        commands.append(args)
        assert '--verify-3090-context' not in args
        if ready:
            (tmp_path/'critic.ready.json').write_text(json.dumps(dict(allocation_id='998' if wrong_job else '999',
                step_id='1',host='127.0.0.1',port=8765,runtime_check=dict(all_parameters_cuda_bf16=True))))
        return process
    service=r.Service(scheduler,tmp_path,1,Path('/artificial/service.py'),popen=popen,sleep=clock.sleep)
    return service,clock,commands


def test_service_ready_binds_actual_scheduler_step(tmp_path):
    service,clock,commands=service_fixture(tmp_path)
    service.start()
    assert service.alive() and service.startup_seconds==850
    assert '--gres=gpu:1' in commands[0] and '--cpus-per-task=6' in commands[0]
    with pytest.raises(RuntimeError,match='replay'): service.start()


@pytest.mark.parametrize('problem',['timeout','wrong_job','no_live_step'])
def test_service_stops_before_any_worker_on_bad_startup(tmp_path,problem):
    service,clock,commands=service_fixture(tmp_path,ready=problem!='timeout',wrong_job=problem=='wrong_job',live=problem!='no_live_step')
    with pytest.raises((TimeoutError,RuntimeError,ValueError)): service.start()
    assert clock.elapsed<=900
    assert sum(args[0]=='srun' for args in commands)==1  # service only, artificial


def test_local_exit_does_not_prove_remote_cleanup(tmp_path):
    service,clock,commands=service_fixture(tmp_path)
    service.start()
    pool=NS(manifest={'tasks':{}},runtime_cancelled=[])
    result=r.cleanup_owned(pool,service,sleep=clock.sleep)
    assert result['local_srun_exited'] and not result['remote_step_cleanup_confirmed']
    assert clock.elapsed<=880  # ONE 30s budget, not separate worker/service budgets


def test_missing_ready_can_still_cancel_exact_named_service(tmp_path):
    service,clock,commands=service_fixture(tmp_path,ready=False)
    with pytest.raises(TimeoutError): service.start()
    result=r.cleanup_owned(NS(manifest={'tasks':{}}),service,sleep=clock.sleep)
    assert ['scancel','--signal=TERM','999.1'] in commands
    assert not result['remote_step_cleanup_confirmed']


@pytest.mark.parametrize('block',[1,2])
def test_actual_pool_mixin_four_runs_and_lifecycle(tmp_path,prepared,pool_module,monkeypatch,block):
    # Instantiate the exact real pinned pool with NEW runtime mixin. The old
    # fixture substitutes discovery/path/process/time, not scheduling functions.
    monkeypatch.setattr(coretests.ctl,'BlockPoolControl',r.RuntimePoolControl)
    pool,clock,commands,_=build_pool(tmp_path,prepared,pool_module,monkeypatch,block=block,start=800,durations=[100]*4)
    pool.runtime_budget=r.Budget(0,16800,clock.monotonic)
    events=[]
    class Service:
        budget=pool.runtime_budget
        startup_seconds=None
        def start(self): events.append('service-start');clock.sleep(10);self.startup_seconds=810
    service=Service()
    def cleanup(pool,service):
        events.append('shared-cleanup')
        return dict(remote_step_cleanup_confirmed=True)
    result=r.run_lifecycle(pool,service,interrupt=fixture_interrupt,cleanup=cleanup)
    assert result['status']=='completed' and len(commands)==4
    assert events==['service-start','shared-cleanup']
    assert result['service_startup_seconds']==810
    assert [cmd[cmd.index('--run-id')+1] for cmd in commands]==list(pool._block_spec.run_ids)


def test_runtime_path_check_uses_no_additional_srun(tmp_path,monkeypatch):
    clock=Clock(850)
    class FakePool(r.RuntimePoolControl):
        runtime_budget=r.Budget(0,16800,clock.monotonic)
        def _required_paths(self): return [tmp_path],[]
    monkeypatch.setattr(r.subprocess,'run',lambda *a,**kw:pytest.fail('path check must not dispatch'))
    FakePool()._validate_paths_on_node()
    clock.elapsed=901
    with pytest.raises(TimeoutError): FakePool()._validate_paths_on_node()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value).encode();path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def collected_case(tmp_path,prepared):
    prepared=json.loads(json.dumps(prepared))
    for block in (1,2):
        spec=coretests.ctl.block_spec(prepared,block)
        key=hashlib.sha256('\n'.join(sorted(spec.run_ids)).encode()).hexdigest()[:12]
        pooldir=tmp_path/'runs/srun_pool'/key
        tasks={}
        for original in [x for x in prepared['run_configs'] if x['block']==block]:
            run_id=original['run_id']
            cfg={'id':run_id,'artificial':True}
            original['config_sha256']=put(tmp_path/'configs'/f'{run_id}.json',cfg)
            stem=run_id[:64]+'-'+hashlib.sha256(run_id.encode()).hexdigest()[:10]
            config=pooldir/'configs'/f'{stem}.json';put(config,cfg)
            identity=pooldir/'identities'/f'{stem}.attempt-1.json'
            tasks[run_id]=dict(config_path=str(config),experiment_dir=str(tmp_path/'runs'/run_id),
                attempt=1,status='completed',attempts=[dict(attempt=1,identity_path=str(identity))])
        pool=dict(allocation_id=str(1000+block),node_list='gpu28',snapshot_path=str(tmp_path/'source'),
            allocations=[dict(allocation_id=str(1000+block))],tasks=tasks)
        put(pooldir/'manifest.json',pool)
        put(tmp_path/f'block-{block}.runtime/started.json',dict(block=block,allocation_id=str(1000+block),node='gpu28',
            controller_commit='a'*40,pool_manifest=f'runs/srun_pool/{key}/manifest.json'))
    def query(start):
        return c.terminal_record(f"{start['allocation_id']}|COMPLETED|gpu28|1800|cpu=12,gres/gpu=2|yzyang4\n",start)
    return tmp_path,prepared,query


def test_collects_all_slots_without_reading_scores(collected_case,monkeypatch):
    root,prepared,query=collected_case
    import forets_block_readout_20260911 as reader
    monkeypatch.setattr(reader,'_final_event',lambda *a:pytest.fail('metadata collector opened score'))
    monkeypatch.setattr(reader,'_process',lambda *a:pytest.fail('metadata collector opened bounded output'))
    value=c.collect_metadata(root,prepared,query=query)
    assert len(value['runs'])==8 and len(value['blocks'])==2
    assert {r['runtime_status'] for r in value['runs']}=={'completed'}
    assert all(b['service_startup_seconds'] is None for b in value['blocks'])


def test_missing_start_is_not_silently_unstarted(collected_case):
    root,prepared,query=collected_case
    (root/'block-2.runtime/started.json').unlink()
    with pytest.raises(FileNotFoundError): c.collect_metadata(root,prepared,query=query)


@pytest.mark.parametrize('bad',['RUNNING','wrong_gpu','duplicate','wrong_owner'])
def test_terminal_record_fail_closed(bad):
    start=dict(block=1,allocation_id='999',node='gpu28')
    text='999|COMPLETED|gpu28|1800|gres/gpu=2|yzyang4\n'
    if bad=='RUNNING': text=text.replace('COMPLETED','RUNNING')
    if bad=='wrong_gpu': text=text.replace('gpu28','projgpu39')
    if bad=='wrong_owner': text=text.replace('yzyang4','other')
    if bad=='duplicate': text+=text
    with pytest.raises(ValueError): c.terminal_record(text,start)


def test_terminal_interrupted_run_is_not_completed(collected_case):
    root,prepared,query=collected_case
    start=json.loads((root/'block-1.runtime/started.json').read_text())
    path=root/start['pool_manifest'];value=json.loads(path.read_text())
    value['tasks'][prepared['run_configs'][0]['run_id']]['status']='running'
    put(path,value)
    result=c.collect_metadata(root,prepared,query=query)
    assert result['runs'][0]['runtime_status']=='failed'


def test_terminal_query_precedes_final_pool_read(collected_case):
    root,prepared,query=collected_case
    start=json.loads((root/'block-1.runtime/started.json').read_text())
    path=root/start['pool_manifest'];value=json.loads(path.read_text())
    run_id=prepared['run_configs'][0]['run_id']
    value['tasks'][run_id]['status']='running';put(path,value)
    def becomes_terminal(start):
        if start['block']==1:
            value['tasks'][run_id]['status']='completed';put(path,value)
        return query(start)
    result=c.collect_metadata(root,prepared,query=becomes_terminal)
    assert result['runs'][0]['runtime_status']=='completed'


def test_worker_cancellation_wait_is_deferred_to_one_cleanup(tmp_path,prepared,pool_module,monkeypatch):
    monkeypatch.setattr(coretests.ctl,'BlockPoolControl',r.RuntimePoolControl)
    holder={}
    pool,clock,commands,processes=build_pool(tmp_path,prepared,pool_module,monkeypatch,start=800,
        durations=[10000]*4,service=lambda:holder['clock'].elapsed<850)
    holder['clock']=clock
    pool.runtime_budget=r.Budget(0,16800,clock.monotonic)
    result=pool.run()
    assert result['counts']=={'cancelled':1,'pending':3} and len(commands)==1
    assert len(pool.runtime_cancelled)==1 and not processes[0].terminated
    assert clock.elapsed==850  # pool has not consumed its own extra 30s wait
