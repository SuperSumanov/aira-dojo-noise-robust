"""New production binding only; no GPU, model, credentials or network."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

PHASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PHASE))
import forets_native_context_20260911 as ctx


@pytest.fixture
def fresh(tmp_path,monkeypatch):
    root=tmp_path/'package';root.mkdir()
    prepared_raw=(PHASE/'results/forets_next_package_20260911/prepared.json').read_bytes()
    prepared=json.loads(prepared_raw)
    (root/'prepared.json').write_bytes(prepared_raw)
    spec=json.loads((PHASE/'forets_native_e2e_release_20260911.json').read_text())
    spec['package']=str(root);raw=json.dumps(spec).encode();policy=tmp_path/'release.json';policy.write_bytes(raw)
    monkeypatch.setattr(ctx,'RELEASE_SHA',hashlib.sha256(raw).hexdigest())
    row=prepared['run_configs'][0];name=row['run_id']
    ids=sorted(r['run_id'] for r in prepared['run_configs'] if r['block']==1)
    key=hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:12]
    stem=re.sub(r'[^A-Za-z0-9_.-]+','-',name).strip('-.')[:64]+'-'+hashlib.sha256(name.encode()).hexdigest()[:10]
    identity=root/'runs'/'srun_pool'/key/'identities'/(stem+'.attempt-1.json');identity.parent.mkdir(parents=True)
    value=dict(run_id=name,attempt=1,allocation_id='999',step_id='7',full_step_id='999.7')
    identity.write_text(json.dumps(value))
    env=dict(FORETS_NATIVE_RELEASE=str(policy),DOJO_WORKER_IDENTITY_PATH=str(identity),SLURM_JOB_ID='999',SLURM_STEP_ID='7')
    return root,identity,value,env


def test_valid_fresh_identity_does_not_require_step_gpu_equality(fresh):
    root,identity,value,env=fresh
    env['SLURM_STEP_GPUS']='1'
    assert ctx.context(env,root=root)==identity


@pytest.mark.parametrize('change',[{'attempt':2},{'allocation_id':'1000'},{'step_id':'8'},{'run_id':'not-planned'}])
def test_replay_wrong_step_or_unplanned_rejected(fresh,change):
    root,identity,value,env=fresh;value.update(change);identity.write_text(json.dumps(value))
    with pytest.raises(ValueError):ctx.context(env,root=root)


def test_mutated_release_rejected_before_identity(fresh):
    root,identity,value,env=fresh;Path(env['FORETS_NATIVE_RELEASE']).write_text('{}')
    with pytest.raises(RuntimeError,match='release'):ctx.context(env,root=root)


@pytest.mark.parametrize('fail',[False,True])
def test_worker_environment_reaches_actual_dispatch_and_is_restored(tmp_path,monkeypatch,fail):
    monkeypatch.delenv('FORETS_NATIVE_INTEGRATION_ROOT',raising=False)
    monkeypatch.setenv('PATH','original');monkeypatch.setenv('DOJO_WORKER_IDENTITY_PATH','previous')
    calls=[]
    class Base:
        def _launch(self,run_id):
            calls.append(dict(os.environ))
            if fail:raise RuntimeError('artificial launch failed')
            return 'launched'
    class Pool(ctx.NativeWorkerEnvironment,Base):
        native_code_dir=tmp_path;native_release_path=tmp_path/'release.json';native_controller_commit='a'*40
        def _identity_path(self,run_id,attempt):return tmp_path/(run_id+'.json')
    if fail:
        with pytest.raises(RuntimeError,match='artificial'):Pool()._launch('run')
    else:assert Pool()._launch('run')=='launched'
    assert calls[0]['DOJO_WORKER_IDENTITY_PATH']==str(tmp_path/'run.json')
    assert calls[0]['PATH'].startswith(str(tmp_path/'bin')+os.pathsep)
    assert os.environ['PATH']=='original' and os.environ['DOJO_WORKER_IDENTITY_PATH']=='previous'


def test_existing_pool_production_mro_receives_environment(pool_module,tmp_path,monkeypatch):
    # Existing exact pinned source fixture, only Popen replaced. No pool.run/recovery.
    from forets_block_runtime_20260911 import RuntimePoolControl
    class Pool(ctx.NativeWorkerEnvironment,RuntimePoolControl,pool_module.SrunPoolLauncher):pass
    assert Pool.__mro__.index(ctx.NativeWorkerEnvironment)<Pool.__mro__.index(RuntimePoolControl)
    assert Pool._recover is RuntimePoolControl._recover


def test_native_identity_env_on_exact_pool_popen(pool_module,prepared,tmp_path,monkeypatch):
    from phase1.tests.test_forets_block_controller_20260911 import build_pool
    pool,clock,commands,processes=build_pool(tmp_path,prepared,pool_module,monkeypatch)
    pool.__class__=type('NewNativePool',(ctx.NativeWorkerEnvironment,type(pool)),{})
    pool.native_code_dir=tmp_path;pool.native_release_path=tmp_path/'release.json'
    pool.native_controller_commit='b'*40
    received=[];original=pool_module.subprocess.Popen
    def capture(command,**kwargs):
        received.append(kwargs['env'].copy())
        return original(command,**kwargs)
    monkeypatch.setattr(pool_module.subprocess,'Popen',capture)
    run_id=pool._block_spec.run_ids[0]
    pool._launch(run_id)
    assert received[0]['DOJO_WORKER_IDENTITY_PATH']==str(pool._identity_path(run_id,1))
    assert received[0]['FORETS_NATIVE_RELEASE']==str(tmp_path/'release.json')
    assert received[0]['FORETS_SOURCE_COMMIT']=='b'*40
    assert 'dojo.main_bounded_srun_worker' in commands[0]


from phase1.tests.test_forets_block_controller_20260911 import pool_module,prepared
