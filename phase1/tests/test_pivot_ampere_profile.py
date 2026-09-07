import copy,inspect,json,subprocess,sys
from dataclasses import replace
from pathlib import Path
import pytest
from phase1 import pivot_ampere_shape_fixture as f
from phase1 import critic_ampere_preflight as k
from phase1.scripts import prepare_pivot_ampere_shape_20260907 as m

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mutation',['none','missing','extra','hash','head'])
def test_space_failure_successor_preserves_previous_attempt(tmp_path,monkeypatch,mutation):
    previous=tmp_path/'previous';previous.mkdir();monkeypatch.setattr(m,'PREVIOUS',previous)
    monkeypatch.setattr(m.os,'getuid',lambda:previous.stat().st_uid,raising=False)
    names={'cpu-tests.log','fa2-build-binding.json','fa2-cpu.json','failed-011017455867.stderr',
        'failed-011017455867.stdout','prepare_intent.json','runtime-plan.json','runtime-plan.log',
        'space-probe-released.json','space-probe.json'}
    for n in names:(previous/n).write_text('{}')
    (previous/'prepare_intent.json').write_text(json.dumps({'commit':'b5b995cf2823d0cd25c404d2a7cbe2a2f8e29ab3'}))
    hashes={'space-probe.json':'a4bee335c062f3947ece6f52b513e6b88f82b5f612412b729e3ab4f165b2607e',
        'space-probe-released.json':'396c306b45a2fc8b58eb44b63aec65433f5b67bcd123aca734a4e21513cef840',
        'failed-011017455867.stderr':'c3a2e2828ea4778eaaf470593cb3b1cc8164c5b82ac9fc9122238a4d468a63be'}
    original=m.sha;monkeypatch.setattr(m,'sha',lambda p:hashes.get(p.name,original(p)))
    if mutation=='missing':(previous/'cpu-tests.log').unlink()
    elif mutation=='extra':(previous/'SUBMITTED.json').write_text('{}')
    elif mutation=='hash':hashes['space-probe.json']='0'*64
    elif mutation=='head':(previous/'prepare_intent.json').write_text(json.dumps({'commit':'0'*40}))
    if mutation!='none':
        with pytest.raises(RuntimeError):m.previous_failed_preparation()
    else:
        result=m.previous_failed_preparation()
        assert result['classification']=='PRESERVED_EDQUOT_BEFORE_ANY_GPU_SUBMISSION' and set(result['files'])==names


def test_space_failure_successor_has_new_namespace_and_prior_evidence():
    from phase1.scripts import verify_pivot_ampere_artifacts_20260907 as post
    assert m.OUT==post.SUB and m.OUT.name=='submission-20260907-r3' and m.PREVIOUS!=m.OUT
    assert 'previous-failed-preparation.json' in m.EVIDENCE
    assert inspect.getsource(m.prepare).index('previous_failed_preparation()')<inspect.getsource(m.prepare).index('OUT.mkdir')

def test_security_pattern_equals_existing_canonical_source_gate():
    from phase1.validate_g_reuse_source_package_v1 import SECRET
    assert m.SECRET.pattern==SECRET.pattern and m.SECRET.flags==SECRET.flags

@pytest.mark.parametrize('value',[b'sk-'+b'x'*16,b'Bearer '+b'x'*24,b'ghp_'+b'x'*24,b'hf_'+b'x'*24,b'AKIA'+b'X'*16],
    ids=['api','bearer','github','hub','aws'])
def test_credential_shapes_still_block(value):assert m.SECRET.search(value)

def test_hyphenated_task_or_disk_identifier_is_not_a_key():
    assert not m.SECRET.search(b'--requested-disk-space-bytes')
    assert not m.SECRET.search(b'task-resource-fingerprint')

def test_explicit_distinct_shape_same_global_work():
    from phase1.pivot_zero3_shape_fixture import fixture
    p,pools,encoder,truth=f.fixture();old,oldpools,oldencoder,oldtruth=fixture()
    assert pools==oldpools and encoder is oldencoder and truth==oldtruth
    assert p.shape.world_size==2 and p.shape.pairs_per_rank==1 and p.shape.accumulation==64
    assert p.steps==2 and p.planned_valid_tokens==old.planned_valid_tokens==8388608
    assert p.sha256==m.PLAN_SHA and p.sha256!=old.sha256
    assert [(s.source,s.pair_visits) for s in p.segments]==[('G',128),('L',128)]
    assert all(len(b.rows)==1 and b.update_real_pairs==128 for b in p.batches)
    assert f.summary()['fit_or_source_admission'] is False
    f.guard(p)
    with pytest.raises(ValueError):f.guard(old)
    with pytest.raises(ValueError):f.guard(replace(p,seed=7))

def test_other_plan_rejected_before_runtime_import():
    code="from phase1.critic_synthetic_ampere_setup import create_synthetic_ampere_setup;from phase1.pivot_zero3_shape_fixture import fixture;import sys;p,pools,e,t=fixture();setup=create_synthetic_ampere_setup(source_root='unused',model_snapshot='unused',pad_id=0)\ntry:setup(p,pools,e,t.__getitem__,training_contract_sha256='a'*64)\nexcept ValueError:pass\nelse:raise AssertionError('non synthetic plan accepted')\nassert 'torch' not in sys.modules"
    p=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,timeout=30)
    assert p.returncode==0,p.stderr.decode()

def test_model_optimizer_and_session_unchanged_after_hardware_gate():
    from phase1.critic_offline_setup import create_zero3_setup
    from phase1.critic_synthetic_ampere_setup import create_synthetic_ampere_setup
    old=inspect.getsource(create_zero3_setup);new=inspect.getsource(create_synthetic_ampere_setup)
    assert old[old.index('        random.seed(plan.seed)'):]==new[new.index('        random.seed(plan.seed)'):]
    assert new.index('guard(plan)')<new.index('import torch')
    assert "get_device_capability(rank) != (8,6)" in new

def test_math_checks_unchanged_except_explicit_device_identity():
    from phase1 import critic_fa2_preflight as original
    old=inspect.getsource(original.check_device)
    expected=old.replace("'PRO 6000'","'RTX 3090'").replace('(12,0)','(8,6)').replace('expected_pro6000_sm120','expected_rtx3090_sm86')
    assert inspect.getsource(k.check_device).strip()==expected.strip()
    assert k.numerical_check is original.numerical_check and k.math_reference is original.math_reference

def test_approval_and_budget_are_distinct_not_model_effect():
    a=json.loads((ROOT/m.APPROVAL).read_bytes());assert m.approval_valid(a)
    assert m.CAP==2*(3600+300+60)==7920 and m.DRIVER==3000
    assert sum(t*g for _,_,t,g in m.PRIOR)==9429
    assert 9429+5760+3840+5760+m.CAP==32709<=36000

@pytest.mark.parametrize('key,value',[('source_admission',True),('real_corpus_reads',1),('automatic_retries',1),
 ('microbatch_per_rank',8),('accumulation',8),('node','projgpu39'),('gpu_type','pro6000'),
 ('driver_seconds',1200),('gpu_seconds_upper_bound',3840),('context_length',2048),('build_job','12648')])
def test_wrong_approval_rejected(key,value):
    a=json.loads((ROOT/m.APPROVAL).read_bytes());a[key]=value;assert not m.approval_valid(a)

def accounting_fixture():
    return '\n'.join(f'{j}|{s}|{t}|cpu=12,gres/gpu={g},node=1|'+('0:0' if s=='COMPLETED' else '1:0')
        for j,s,t,g in m.PRIOR+[('12648','COMPLETED',3199,1),('12649','COMPLETED',1000,1)])

def test_accounting_counts_both_builds_and_keeps_pro_headroom():
    # Last build elapsed is a synthetic parser fixture, not a measured result.
    assert m.parse_accounting(accounting_fixture())==9429+3199+1000

@pytest.mark.parametrize('mutation',['missing','duplicate','unknown','state','exit','duration','gpus','old_failure'])
def test_accounting_failure_closed(mutation):
    raw=accounting_fixture()
    if mutation=='missing':raw='\n'.join(raw.splitlines()[:-1])
    elif mutation=='duplicate':raw+='\n'+raw.splitlines()[-1]
    elif mutation=='unknown':raw+='\n888|COMPLETED|1|gres/gpu=1|0:0'
    elif mutation=='state':raw=raw.replace('12649|COMPLETED','12649|RUNNING')
    elif mutation=='exit':raw=raw.rsplit('|0:0',1)[0]+'|1:0'
    elif mutation=='duration':raw=raw.replace('12649|COMPLETED|1000','12649|COMPLETED|5761')
    elif mutation=='gpus':raw=raw.replace('12649|COMPLETED|1000|cpu=12,gres/gpu=1','12649|COMPLETED|1000|cpu=12,gres/gpu=2')
    else:raw=raw.replace('12641|FAILED|2126','12641|COMPLETED|2126')
    with pytest.raises(RuntimeError):m.parse_accounting(raw)

def kernel_fixture():
    return {'classification':'FA2_AMPERE_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT','job_id':'123',
      'code_commit':'a'*40,'binding':{'build_sha256':'b'*64},'devices':[{'device':r,'name':'NVIDIA RTX 3090',
      'long_length':16384,'long_forward_backward_finite':True,'long_full_reference_compared':False,
      'short_reference_cases':[{'mode':mode,'lengths':lengths,'errors':{key:{'relative_l2':.001,'maximum_absolute':.001}
        for key in ('output','dq','dk','dv')}} for mode,lengths in [('dense',[129]),('varlen',[31,97])]]} for r in (0,1)]}

def valid(v):return k.kernel_receipt_valid(v,job='123',commit='a'*40,build_sha='b'*64)

def test_ampere_kernel_exact_schema_not_pro_acceptance():
    from phase1.scripts.prepare_pivot_fa2_shape_20260907 import kernel_receipt_valid
    v=kernel_fixture();assert valid(v)
    assert not kernel_receipt_valid(v,job='123',commit='a'*40,build_sha='b'*64)

@pytest.mark.parametrize('mutation',['missing_rank','hardware','class','nonfinite','relative','absolute','missing_gradient','length','long'])
def test_kernel_rejects_drift(mutation):
    v=kernel_fixture();row=v['devices'][0]
    if mutation=='missing_rank':v['devices'].pop()
    elif mutation=='hardware':row['name']='NVIDIA RTX PRO 6000'
    elif mutation=='class':v['classification']='FA2_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT'
    elif mutation in ('nonfinite','relative','absolute'):
        err=row['short_reference_cases'][0]['errors']['dq']
        err['relative_l2' if mutation!='absolute' else 'maximum_absolute']=float('nan') if mutation=='nonfinite' else .06
    elif mutation=='missing_gradient':del row['short_reference_cases'][0]['errors']['dq']
    elif mutation=='length':row['short_reference_cases'][0]['lengths']=[128]
    else:row['long_forward_backward_finite']=False
    assert not valid(v)

def test_batch_script_binds_ampere_profile_and_full_time():
    s=(ROOT/m.SCRIPT).read_text()
    for x in ('--gres=gpu:rtx3090:2','--nodelist=gpu28','--time=01:00:00','--cpus-per-task=12',
      'phase1.scripts.check_zero3_private_tools_20260906','timeout --kill-after=60s 3000s','timeout --kill-after=20s 180s','--no-requeue','--constraint=highcpucount'):
        assert x in s
    assert "'Features':'highcpucount'" in inspect.getsource(m.allocation)
    assert s.index('pivot_checkpoint_space')<s.index(' kernel --commit')<s.index(' allocated --commit')<s.index('validate_pivot_ampere_shape')
    assert 'pro6000' not in s.lower() and '12535' not in s
    assert 'CUDA_HOME=/research/d7/spc/yzyang4/private-cuda128-toolchain-20260906/prefix' in s
    assert 'CXX=/usr/bin/g++ NVCC_CCBIN=/usr/bin/g++' in s
    assert '/usr/local/cuda-12.8' not in s

def test_prepare_cache_is_commit_specific_and_checked_before_output_creation():
    a=m.prepare_cache_path('a'*40);b=m.prepare_cache_path('b'*40)
    assert a!=b and str(a).replace('\\','/')=='/tmp/critic-pivot-ampere-'+('a'*40)+'-triton'
    body=inspect.getsource(m.prepare)
    assert body.index('prepare_cache_already_exists')<body.index('OUT.mkdir')
    assert "TRITON_CACHE_DIR=str(cache)" in body and 'mkdir(mode=0o700)' in body

@pytest.mark.parametrize('bad',['a'*39,'../outside','A'*40,123])
def test_prepare_cache_rejects_noncommit(bad):
    with pytest.raises(RuntimeError,match='cache_exact_commit'):m.prepare_cache_path(bad)

@pytest.mark.parametrize('mutation',['none','recovery','independent','manifest'])
def test_private_toolchain_receipts_and_actual_prefix_are_bound(monkeypatch,mutation):
    from phase1.scripts import check_zero3_private_tools_20260906 as tools
    expected={'RECOVERY_COMPLETE.json':tools.RECOVERY,'INDEPENDENT_VERIFIED.json':tools.INDEPENDENT,'installed_manifest.json':tools.MANIFEST}
    key={'recovery':'RECOVERY_COMPLETE.json','independent':'INDEPENDENT_VERIFIED.json','manifest':'installed_manifest.json'}.get(mutation)
    monkeypatch.setattr(m,'sha',lambda p:'0'*64 if p.name==key else expected[p.name])
    inventory={'bin/nvcc':{'kind':'file'}};monkeypatch.setattr(m,'read',lambda p:inventory)
    calls=[]
    def verified(prefix,value):calls.append((prefix,value));return value
    monkeypatch.setattr(tools,'verify_prefix',verified)
    if mutation!='none':
        with pytest.raises(RuntimeError,match='toolchain_receipt'):m.toolchain_binding(full=True)
        assert not calls
    else:
        v=m.toolchain_binding(full=True);assert len(calls)==1 and v['files_and_links']==1
        assert m.toolchain_binding()==v and len(calls)==1

def test_toolchain_failure_is_explicit_in_budget_and_fresh_preparation():
    assert ('12662','FAILED',3,2) in m.PRIOR
    assert {'failed-toolchain-job.json','private-toolchain.json'}<=set(m.EVIDENCE)
    code=inspect.getsource(m.prepare)
    assert code.index('failed_toolchain_job()')<code.index('OUT.mkdir')
    assert code.index('toolchain_binding(full=True)')<code.index('OUT.mkdir')
    a=json.loads((ROOT/m.APPROVAL).read_bytes());assert a['replaces_pre_model_job']=='12662' and a['automatic_retries']==0
