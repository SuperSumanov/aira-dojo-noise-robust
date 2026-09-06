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
