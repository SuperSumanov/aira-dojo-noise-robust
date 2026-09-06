import json
from pathlib import Path
import pytest
from phase1.scripts import prepare_pivot_zero3_shape_20260906 as m
from phase1 import pivot_checkpoint_space as space

ROOT=Path(__file__).resolve().parents[2]


def test_fixed_distinct_authority_and_budget():
    a=json.loads((ROOT/m.APPROVAL).read_bytes())
    assert a['gpu_seconds_upper_bound']==m.CAP==2*(1560+300+60)
    assert sum(s*g for _,_,s,g in m.PRIOR)==7006
    assert 7006+m.CAP==10846<=14400
    assert a['tiny_terminal_sha256']==m.TINY_SHA
    assert a['source_admission'] is False and a['real_corpus_reads']==0
    assert a['pretrained_critic_weights_allowed'] is True and a['agent_base_update_allowed'] is False
    assert a['actual_space_probe_bytes']==space.SIZE==64*1024**3


def test_real_accounting_fixture_and_mutation(monkeypatch):
    rows='\n'.join(f'{j}|{s}|{t}|cpu=12,gres/gpu={g},node=1|'+('0:0' if s=='COMPLETED' else '1:0') for j,s,t,g in m.PRIOR)
    monkeypatch.setattr(m.c,'run',lambda *a,**k:rows.encode())
    assert m.accounting()==7006
    rows=rows.replace('12575|COMPLETED|271','12575|COMPLETED|272')
    with pytest.raises(RuntimeError,match='drift'):m.accounting()


def test_profile_no_fallback_no_old_job_release():
    script=(ROOT/m.SCRIPT).read_text()
    assert '#SBATCH --time=00:26:00' in script and '#SBATCH --gres=gpu:pro6000:2' in script
    assert 'timeout --kill-after=60s 1200s' in script and '--no-requeue' in script
    assert 'NCCL_NET=Socket' in script
    assert script.index('pivot_checkpoint_space')<script.index(' allocated --commit')<script.index('validate_pivot_zero3_shape')
    assert '12535' not in script and 'scontrol release' not in script


def _previous_fixture(tmp_path,monkeypatch):
    old=tmp_path/'failed';old.mkdir();cleanup=tmp_path/'cleanup.json'
    monkeypatch.setattr(m,'PREVIOUS_OUT',old)
    monkeypatch.setattr(m.c,'OUT',tmp_path/'fresh')
    monkeypatch.setattr(m,'CLEANUP_RECEIPT',cleanup)
    objects={
        'prepare_intent.json':{'commit':m.PREVIOUS_COMMIT},
        'space-probe.json':{'passed':False,'requested_bytes':68719476736,'allocated_bytes':0,
            'device':1,'inode':2,'error':{'errno':122,'type':'OSError'}},
        'space-probe-released.json':{'own_inode_removed':True,'device':1,'inode':2}}
    for name,value in objects.items():(old/name).write_text(json.dumps(value))
    cleanup.write_text(json.dumps({'real_64GiB_allocation_passed':True,'real_probe_allocated_bytes':68719476736,
        'probe_own_inode_released':True,'protected_fingerprints_equal':True}))
    monkeypatch.setattr(m,'CLEANUP_SHA',m.c.sha(cleanup))
    return old,cleanup


def test_capacity_successor_fixed_scope():
    assert m.PREVIOUS_COMMIT=='ef19d100ac6cb1a747c332eb1b8596051f47a695'
    assert m.c.OUT.name=='submission-20260906-capacity-recovered'
    assert m.PREVIOUS_OUT.name=='submission-20260906'
    assert m.CLEANUP_SHA=='b5cd4dd02f8c5418106bbc0966371496b1d937e1bc5be04734f3df75bf3d9564'


def test_capacity_successor_preserves_failure_and_requires_fresh_probe(tmp_path,monkeypatch):
    old,_=_previous_fixture(tmp_path,monkeypatch)
    before={p.name:p.read_bytes() for p in old.iterdir()}
    result=m.previous_preparation()
    assert result['prior_gpu_job_submitted'] is False and result['fresh_space_probe_still_required'] is True
    assert before=={p.name:p.read_bytes() for p in old.iterdir()}


@pytest.mark.parametrize('marker',['READY.json','SUBMISSION_INTENT.json','SUBMITTED.json','RELEASED.json'])
def test_capacity_successor_rejects_possible_previous_submission(tmp_path,monkeypatch,marker):
    old,_=_previous_fixture(tmp_path,monkeypatch);(old/marker).write_text('{}')
    with pytest.raises(RuntimeError,match='may_have_submitted'):m.previous_preparation()


@pytest.mark.parametrize('mutation',['same_root','changed_error','released_identity','cleanup_hash','cleanup_failed'])
def test_capacity_successor_rejects_changed_evidence(tmp_path,monkeypatch,mutation):
    old,cleanup=_previous_fixture(tmp_path,monkeypatch)
    if mutation=='same_root':monkeypatch.setattr(m.c,'OUT',old)
    elif mutation=='changed_error':
        path=old/'space-probe.json';value=json.loads(path.read_text());value['error']['errno']=28;path.write_text(json.dumps(value))
    elif mutation=='released_identity':
        path=old/'space-probe-released.json';value=json.loads(path.read_text());value['inode']=3;path.write_text(json.dumps(value))
    elif mutation=='cleanup_hash':cleanup.write_text(cleanup.read_text()+'\n')
    else:
        value=json.loads(cleanup.read_text());value['real_64GiB_allocation_passed']=False;cleanup.write_text(json.dumps(value))
        monkeypatch.setattr(m,'CLEANUP_SHA',m.c.sha(cleanup))
    with pytest.raises(RuntimeError):m.previous_preparation()


def test_resume_receipt_survives_run_header(tmp_path,monkeypatch):
    # Exercise the production run-loop reporting with a fake already-qualified
    # one-rank CPU session. This is a unit check, not distributed qualification.
    torch=pytest.importorskip('torch')
    from dataclasses import dataclass
    from types import SimpleNamespace as N
    from phase1.critic_training_run import run_session
    @dataclass
    class Event:
        completed_steps:int=2
        source:str='L'
        cycle:int=0
        local_pair_visits:int=1
        local_valid_tokens:int=2
        global_update_pairs:int=1
        cumulative_global_valid_tokens:int=4
        learning_rate:float=1e-5
        step_owner:str='fake-unit-only'
    plan=N(shape=N(world_size=1),steps=2,seed=6,sha256='a'*64,arm='G_to_L')
    consumer=N(plan=plan,completed_steps=0,rank=0,accelerator=N(device=N(type='cpu'),wait_for_everyone=lambda:None))
    receipt={'completed_steps':1,'all_state_components_restored':True,'native_cpu_adam_cache':{'empty_native_calls':1}}
    def restore(*args,**kwargs):consumer.completed_steps=1;return receipt
    def run(step):consumer.completed_steps=step;return [Event()]
    session=N(consumer=consumer,binding={},restore=restore,run_until=run,save=lambda p:'b'*64,_tokens=lambda n:2*n)
    monkeypatch.setattr(torch.distributed,'all_gather_object',lambda out,value:out.__setitem__(0,value))
    result=run_session(session,N(plan=plan,sequence=2,reported_arm='unit'),tmp_path/'new',stop_after=2,
        checkpoint_steps=[2],resume=tmp_path/'checkpoint',resume_manifest_sha256='c'*64)
    assert result['status']=='COMPLETED'
    context=json.loads((tmp_path/'new/rank_0_context.json').read_text())
    assert context['restore_receipt']==receipt and context['start_step']==1
