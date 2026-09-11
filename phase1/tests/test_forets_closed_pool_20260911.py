"""Only new closed-pool behavior; no existing GPU acceptance reruns."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_closed_pool_20260911 as c

def fixture_rows():
    return [dict(slot=s,repeat=r,status='valid',valid=True,score=float(s+1)) for s,r in c.ORDER]

def test_fixed_order_all_candidates_twice():
    assert c.ORDER==((0,0),(1,0),(2,0),(2,1),(1,1),(0,1))
    a=c.summarize(fixture_rows(),[1,3,2])
    assert a['top2']['slots']==[1,2]
    assert a['top2']['conditional_mean_logloss']==2.5
    assert a['uniform3']['conditional_mean_logloss']==2

def test_failures_not_imputed_as_zero_score():
    rows=fixture_rows()
    for r in rows:
        if r['slot']==1:r.update(valid=False,score=None,status='program_timeout')
    a=c.summarize(rows,[1,3,2])
    assert a['top2']['valid_probability']==.5
    assert a['top2']['conditional_mean_logloss']==3
    assert a['uniform3']['valid_probability']==4/6

@pytest.mark.parametrize('mode',['incomplete','duplicate','infrastructure'])
def test_invalid_diagnostics_rejected(mode):
    rows=fixture_rows()
    if mode=='incomplete':rows.pop()
    if mode=='duplicate':rows[-1]=dict(rows[0])
    if mode=='infrastructure':rows[0]['status']='infrastructure_error'
    with pytest.raises(ValueError):c.summarize(rows,[1,3,2])

def test_drift_rejected_before_code_read():
    with pytest.raises(ValueError,match='drift'):c.snapshot('{}',c.SNAPSHOT)

def test_credential_boundary_not_inside_ordinary_word():
    assert not c.SECRET.search('task-nameordinaryletters')
    assert c.SECRET.search('prefix '+ 'sk-'+'X'*16)

def test_wrong_root_never_opens_protected_cohort(tmp_path):
    with pytest.raises(ValueError):c.checked_root(tmp_path)

@pytest.mark.parametrize('timeout',[False,True])
def test_actual_runner_boundary_with_fake_kernel(tmp_path,monkeypatch,timeout):
    calls=[];code=b'print(1)';(tmp_path/'codes').mkdir();(tmp_path/'codes/0.py').write_bytes(code)
    monkeypatch.setattr(c,'CODES',(c.digest(code),)+c.CODES[1:])
    monkeypatch.setenv('FORETS_SOURCE_COMMIT','a'*40);monkeypatch.setenv('SLURM_JOB_ID','999')
    class Kernel:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def wait_for_ready(self,**kw):return True
        def execute(self,text,timeout_seconds):
            assert text==code.decode() and timeout_seconds==300
            (tmp_path/'work-0/submission.csv').write_text('artificial')
            return SimpleNamespace(is_ok=not timeout,timed_out=timeout,output=['artificial'])
    class Server:
        def __init__(self,**kw):
            calls.append(kw)
            assert kw['startup_timeout']==90 and kw['bind_inputs_dir'].as_posix().endswith('/prepared/public')
        def get_client(self):return SimpleNamespace(start_kernel=lambda _: 'k',get_kernel_client=lambda _:Kernel())
        def stop(self):calls.append('stopped')
    def grade(*args):calls.append('graded');return .25,{}
    registry=SimpleNamespace(set_data_dir=lambda _:SimpleNamespace(get_competition=lambda _:object()))
    modules={
        'dojo.core.interpreters.jupyter.singularity_jupyter_server':SimpleNamespace(SingularityJupyterServer=Server),
        'dojo.tasks.mlebench.evaluate':SimpleNamespace(evaluate_submission=grade),
        'mlebench.grade':SimpleNamespace(validate_submission=lambda *_:(True,'')),
        'mlebench.registry':SimpleNamespace(registry=registry),
        'forets_opencl_allowlist_20260911':SimpleNamespace(IMAGE=Path('/original.sif'))}
    for key,value in modules.items():monkeypatch.setitem(sys.modules,key,value)
    row=c.execute_one(tmp_path,0)
    assert row['status']==('program_timeout' if timeout else 'valid')
    assert ('graded' in calls)==(not timeout)
    assert calls[-1]=='stopped'
