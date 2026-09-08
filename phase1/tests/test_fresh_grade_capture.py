import hashlib
import json
from pathlib import Path
import pytest
from phase1 import fresh_grade_capture as m


def setup(tmp_path):
    workspace=tmp_path/'workspace';workspace.mkdir()
    submission=workspace/'submission.csv';submission.write_bytes(b'id,pred\na,0.7\n')
    source=tmp_path/'grader.py';source.write_bytes(b'def grade(): return 0.7\n')
    return dict(output=tmp_path/'vault',submission_path=submission,code=b'print(1)\n',
        binding=dict(run_id='synthetic-run',step=1,task='synthetic-task',execution_receipt_sha256='a'*64),
        sources=dict(grader=source))


def test_persists_before_grade_and_returns_same_object(tmp_path):
    kw=setup(tmp_path); expected={'score':0.7,'extra':{'x':[1,2]}};calls=[]
    def grade():
        assert (kw['output']/'submission.csv').read_bytes()==kw['submission_path'].read_bytes()
        assert (kw['output']/'intent.json').exists() and not (kw['output']/'COMPLETE').exists()
        calls.append(1);return expected
    assert m.capture_grade(**kw,evaluate=grade) is expected and calls==[1]
    root=kw['output']; receipt=json.loads((root/'receipt.json').read_bytes())
    assert (root/'COMPLETE').read_text()==hashlib.sha256((root/'receipt.json').read_bytes()).hexdigest()
    assert receipt['source_admission'] is receipt['agent_isolation_attested'] is False
    for name,r in receipt['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==r['sha256']
    assert kw['submission_path'].read_bytes()==b'id,pred\na,0.7\n'
    assert json.loads((root/'result.json').read_bytes())==expected
    assert m.verify_capture(root)['integrity_verified'] is True


def test_collision_never_regrades(tmp_path):
    kw=setup(tmp_path);calls=[]
    m.capture_grade(**kw,evaluate=lambda:calls.append(1))
    with pytest.raises(m.CaptureError,match='new_transaction_required'):
        m.capture_grade(**kw,evaluate=lambda:calls.append(2))
    assert calls==[1]


@pytest.mark.parametrize('case',['source_mutates','submission_mutates','grade_error','nonfinite','result_secret'])
def test_post_call_failure_preserved_and_never_retried(tmp_path,case):
    kw=setup(tmp_path);calls=[]
    def grade():
        calls.append(1)
        if case=='source_mutates':kw['sources']['grader'].write_text('changed')
        if case=='submission_mutates':kw['submission_path'].write_text('changed')
        if case=='grade_error':raise RuntimeError('private row must not appear in evidence')
        if case=='nonfinite':return {'score':float('nan')}
        if case=='result_secret':return {'x':'sk-'+'x'*32}
        return 1
    with pytest.raises(m.CaptureError,match='capture_incomplete_do_not_retry'):m.capture_grade(**kw,evaluate=grade)
    assert calls==[1] and not (kw['output']/'COMPLETE').exists()
    failed=(kw['output']/'FAILED.json').read_text()
    assert 'private row must' not in failed and 'sk-'+'x'*32 not in failed
    assert json.loads(failed)['grading_call_entered'] is True
    with pytest.raises(m.CaptureError,match='new_transaction_required'):m.capture_grade(**kw,evaluate=grade)
    assert calls==[1]


@pytest.mark.parametrize('case',['extra_binding','bad_reference','code_secret','source_secret','submission_secret','workspace_vault','source_alias'])
def test_pre_call_faults_do_not_grade(tmp_path,case):
    kw=setup(tmp_path);calls=[]
    if case=='extra_binding':kw['binding']['label']=1
    if case=='bad_reference':kw['binding']['execution_receipt_sha256']='unknown'
    if case=='code_secret':kw['code']=('sk-'+'x'*32).encode()
    if case=='source_secret':kw['sources']['grader'].write_text('sk-'+'x'*32)
    if case=='submission_secret':kw['submission_path'].write_text('sk-'+'x'*32)
    if case=='workspace_vault':kw['output']=kw['submission_path'].parent/'vault'
    if case=='source_alias':kw['sources']['duplicate']=kw['sources']['grader']
    with pytest.raises(m.CaptureError):m.capture_grade(**kw,evaluate=lambda:calls.append(1))
    assert not calls and not kw['output'].exists()


def test_absent_submission_preserved_without_inventing_score(tmp_path):
    kw=setup(tmp_path);kw['submission_path'].unlink()
    expected={'score':None,'submission_exists':False}
    assert m.capture_grade(**kw,evaluate=lambda:expected) is expected
    assert not (kw['output']/'submission.csv').exists()
    assert json.loads((kw['output']/'intent.json').read_bytes())['submission_present'] is False


def test_submission_size_cap_is_pre_call(tmp_path,monkeypatch):
    kw=setup(tmp_path);monkeypatch.setattr(m,'MAX_SUBMISSION',2);calls=[]
    with pytest.raises(m.CaptureError):m.capture_grade(**kw,evaluate=lambda:calls.append(1))
    assert not calls and not kw['output'].exists()


def test_source_symlink_rejected(tmp_path):
    kw=setup(tmp_path);link=tmp_path/'link.py'
    try:link.symlink_to(kw['sources']['grader'])
    except OSError:pytest.skip('symlinks unavailable')
    kw['sources']['grader']=link
    with pytest.raises(m.CaptureError,match='unsafe_path'):m.capture_grade(**kw,evaluate=lambda:1)


@pytest.mark.parametrize('case',['code.py','intent.json','submission.csv','sources/grader.txt','unexpected','unexpected_source'])
def test_callback_archive_mutation_rejected(tmp_path,case):
    kw=setup(tmp_path)
    def grade():
        path=kw['output']/('sources/new.txt' if case=='unexpected_source' else case)
        if path.exists():path.chmod(0o600)
        path.write_bytes(b'changed')
        return 1
    with pytest.raises(m.CaptureError,match='capture_incomplete'):m.capture_grade(**kw,evaluate=grade)
    with pytest.raises(m.CaptureError,match='failed_transaction'):m.verify_capture(kw['output'])


@pytest.mark.parametrize('case',['code.py','COMPLETE','extra','FAILED.json','missing_source'])
def test_consumer_rejects_post_commit_change(tmp_path,case):
    kw=setup(tmp_path);m.capture_grade(**kw,evaluate=lambda:1)
    path=kw['output']/case
    if case=='missing_source':
        target=kw['output']/'sources/grader.txt';target.chmod(0o600);target.unlink()
    else:
        if path.exists():path.chmod(0o600)
        path.write_bytes(b'changed')
    with pytest.raises(m.CaptureError):m.verify_capture(kw['output'])


def test_failure_after_complete_is_never_accepted(tmp_path,monkeypatch):
    kw=setup(tmp_path);original=m.sync_directory
    def late_failure(path):
        if (kw['output']/'COMPLETE').exists() and not (kw['output']/'FAILED.json').exists():
            raise OSError('fixture fsync failure')
        original(path)
    monkeypatch.setattr(m,'sync_directory',late_failure)
    with pytest.raises(m.CaptureError,match='capture_incomplete'):m.capture_grade(**kw,evaluate=lambda:1)
    assert (kw['output']/'COMPLETE').exists()
    with pytest.raises(m.CaptureError,match='failed_transaction'):m.verify_capture(kw['output'])
