import copy
import json
from pathlib import Path
import pytest
from phase1.scripts import prepare_pivot_fa2_shape_20260907 as m

ROOT=Path(__file__).resolve().parents[2]


def test_import_leaves_old_profile_unchanged():
    from phase1.scripts import prepare_pivot_zero3_shape_20260906 as old
    assert old.c.OUT.name=='submission-20260906-capacity-recovered'
    assert old.SCRIPT.endswith('pivot_zero3_shape_20260906.sbatch')
    assert 'test_pivot_shape_profile' in old.TESTS


def test_scoped_profile_restored_on_failure():
    from phase1.scripts import prepare_pivot_zero3_shape_20260906 as old
    before={k:getattr(old,k) for k in ('SCRIPT','APPROVAL','TESTS','files','accounting','bind','ready','allocated')}
    before_out=old.c.OUT
    with pytest.raises(RuntimeError,match='test_failure'):
        with m.configured_profile() as p:
            assert p.c.OUT==m.OUT and p.APPROVAL==m.APPROVAL and p.SCRIPT==m.SCRIPT
            assert set(m.EXTRA_TESTS).issubset(p.TESTS)
            assert 'test_pivot_shape_profile' not in p.TESTS
            raise RuntimeError('test_failure')
    assert old.c.OUT==before_out
    assert before=={k:getattr(old,k) for k in before}


def test_same_scientific_matrix_distinct_dependency_authority():
    old=json.loads((ROOT/'phase1/manifests/pivot_zero3_shape_approval_20260906.json').read_bytes())
    new=json.loads((ROOT/m.APPROVAL).read_bytes())
    for key in ('jobs','gpu_count','gpu_type','node','walltime_seconds','driver_seconds','parameters',
                'context_length','microbatch_per_rank','accumulation','seed','checkpoints','actual_space_probe_bytes',
                'real_corpus_reads','pretrained_critic_weights_allowed','agent_base_update_allowed','source_admission',
                'model_effect_measured','tiny_terminal_sha256','model_manifest_sha256'):
        assert new[key]==old[key]
    assert new['enumerated_prior_actual_gpu_seconds_excluding_build']+m.BUILD_CAP+m.CAP==19023<=21600
    assert new['fa2_build_job']==m.BUILD_JOB and new['fa2_build_commit']==m.BUILD_COMMIT
    assert new['automatic_retries']==0 and not new['requeue']


def accounting_fixture(build_elapsed=100):
    from phase1.scripts import prepare_pivot_zero3_shape_20260906 as old
    prior=old.PRIOR+m.RECENT
    rows=[f'{j}|{s}|{t}|cpu=12,gres/gpu={g},node=1|'+('0:0' if s=='COMPLETED' else '1:0') for j,s,t,g in prior]
    rows.append(f'{m.BUILD_JOB}|COMPLETED|{build_elapsed}|cpu=4,gres/gpu=1,node=1|0:0')
    return '\n'.join(rows),prior


def test_build_fee_is_actual_and_bounded():
    rows,prior=accounting_fixture()
    assert m.parse_accounting(rows,prior)==9523
    rows,prior=accounting_fixture(m.BUILD_CAP)
    assert m.parse_accounting(rows,prior)+m.CAP==19023


@pytest.mark.parametrize('mutation',['duplicate','missing','running','failed','oversized','zero','prior_drift','extra'])
def test_accounting_fails_closed(mutation):
    rows,prior=accounting_fixture()
    if mutation=='duplicate':rows+='\n'+rows.splitlines()[-1]
    elif mutation=='missing':rows='\n'.join(rows.splitlines()[:-1])
    elif mutation=='running':rows=rows.replace(m.BUILD_JOB+'|COMPLETED',m.BUILD_JOB+'|RUNNING')
    elif mutation=='failed':rows=rows.replace(m.BUILD_JOB+'|COMPLETED',m.BUILD_JOB+'|FAILED')
    elif mutation=='oversized':rows=rows.replace('|100|cpu=4',f'|{m.BUILD_CAP+1}|cpu=4')
    elif mutation=='zero':rows=rows.replace('|100|cpu=4','|0|cpu=4')
    elif mutation=='prior_drift':rows=rows.replace('12577|FAILED|98','12577|FAILED|99')
    else:rows+='\n99999|COMPLETED|1|gres/gpu=1|0:0'
    with pytest.raises(RuntimeError):m.parse_accounting(rows,prior)


def receipt():
    cases=[{'mode':mode,'lengths':lengths,'errors':{n:{'relative_l2':.01,'maximum_absolute':.01}
        for n in ('output','dq','dk','dv')}} for mode,lengths in [('dense',[129]),('varlen',[31,97])]]
    return {'classification':'FA2_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT',
        'job_id':'123','code_commit':'a'*40,'binding':{'build_sha256':'b'*64},
        'devices':[{'device':i,'name':'NVIDIA RTX PRO 6000','long_length':16384,'long_forward_backward_finite':True,
            'long_full_reference_compared':False,'short_reference_cases':copy.deepcopy(cases)} for i in (0,1)]}


def test_kernel_receipt_accepts_only_frozen_math_cases():
    assert m.kernel_receipt_valid(receipt(),job='123',commit='a'*40,build_sha='b'*64)


@pytest.mark.parametrize('mutation',['nan','negative','large','missing_grad','one_gpu','wrong_digest','wrong_length'])
def test_kernel_receipt_rejects_bad_cases(mutation):
    r=receipt();error=r['devices'][0]['short_reference_cases'][0]['errors']
    if mutation=='nan':error['dq']['relative_l2']=float('nan')
    elif mutation=='negative':error['dq']['relative_l2']=-.1
    elif mutation=='large':error['dq']['maximum_absolute']=.051
    elif mutation=='missing_grad':del error['dk']
    elif mutation=='one_gpu':r['devices'].pop()
    elif mutation=='wrong_digest':r['binding']['build_sha256']='c'*64
    else:r['devices'][0]['long_length']=1024
    assert not m.kernel_receipt_valid(r,job='123',commit='a'*40,build_sha='b'*64)


def test_worker_dependency_then_allocation_then_unchanged_driver():
    script=(ROOT/m.SCRIPT).read_text()
    assert '#SBATCH --time=00:26:00' in script and '#SBATCH --gres=gpu:pro6000:2' in script
    assert 'PYTHONPATH="$overlay:$ZERO3_CONTROL_ROOT"' in script
    assert script.index('pivot_checkpoint_space')<script.index(' kernel --commit')<script.index(' allocated --commit')<script.index('validate_pivot_zero3_shape_20260906')
    assert '1200s' in script and '120s' in script and '12535' not in script
    assert 'scontrol release' not in script and '--no-requeue' in script
