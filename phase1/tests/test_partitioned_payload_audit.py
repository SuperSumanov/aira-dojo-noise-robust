import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from phase1.partitioned_payload_audit import (PARTS, ROLES, complete_coverage, completed_part,
    fingerprint, part_name, payload_names, read_json, save_exclusive, verified_file)


def sealed(path, raw=b'abc'):
    path.write_bytes(raw); path.chmod(0o400); return path


@pytest.mark.parametrize('case,rank', PARTS)
def test_fixed_addresses(case, rank):
    assert part_name(case, rank) == f'{case}-rank{rank}'
    assert len(payload_names(rank)) == 3


@pytest.mark.parametrize('case,rank', [('prefix1', True), ('resume2', -1), ('other', 0), ('prefix1', 2)])
def test_bad_addresses(case, rank):
    with pytest.raises(ValueError): part_name(case, rank)


def test_sealed_byte_identity(tmp_path):
    p=sealed(tmp_path/'input')
    expected={'bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest()}
    assert verified_file(p,expected)==fingerprint(p)
    with pytest.raises(ValueError): verified_file(p,dict(expected,sha256='0'*64))


def test_writable_file_refused(tmp_path):
    p=tmp_path/'input';p.write_bytes(b'x');p.chmod(0o600)
    with pytest.raises(ValueError): fingerprint(p)


def test_duplicate_json_refused(tmp_path):
    p=sealed(tmp_path/'input',b'{"x":1,"x":2}')
    with pytest.raises(ValueError): read_json(p)


def test_exclusive_output(tmp_path):
    p=tmp_path/'receipt'; save_exclusive(p,{'x':1})
    with pytest.raises((FileExistsError,PermissionError)): save_exclusive(p,{'x':2})
    assert read_json(p)=={'x':1}


def part_fixture(tmp_path, mutation=None):
    root=tmp_path/'part';root.mkdir();binding={'audit':'fixed'}
    value={'binding':binding,'case':'prefix1','rank':0,
        'classification':'ONE_AUTHENTICATED_PAYLOAD_PART_NOT_FINAL_ACCEPTANCE',
        'input_fingerprints':{n:{'dev':1,'inode':1,'bytes':3,'mtime_ns':1,'ctime_ns':1} for n in payload_names(0)},
        'elapsed_seconds':1.0,
        'payload_check':{'classification':'ACTUAL_ZERO3_PAYLOAD_SIX_ROLE_OBSERVATION_CHECK_NOT_RESTART_PARITY',
            'direct_roles_verified':list(ROLES),'parameters':3,'master_groups':1,'local_master_elements':2,
            'completed_steps':1,'cumulative_valid_tokens':8,'live_model_shards_independently_reconstructed':False,
            'direct_state_sha256':{k:'1'*64 for k in ROLES},'gpu_initialized':False}}
    if mutation: mutation(value)
    save_exclusive(root/'INTENT.json',{'binding':binding,'case':'prefix1','rank':0})
    sealed(root/'progress.jsonl',b'{}\n')
    digest=save_exclusive(root/'SUCCESS.json',value)
    save_exclusive(root/'COMPLETE.json',{'sha256':digest})
    return root,binding


def test_completed_part_not_final(tmp_path):
    root,binding=part_fixture(tmp_path)
    assert completed_part(root,binding,'prefix1',0)['payload_check']['parameters']==3
    with pytest.raises(ValueError): completed_part(root,{'audit':'changed'},'prefix1',0)


@pytest.mark.parametrize('mutation', [
    lambda v:v.update(rank=True), lambda v:v.update(model_effect=True),
    lambda v:v['payload_check'].update(gpu_initialized=True),
    lambda v:v['payload_check'].update(live_model_shards_independently_reconstructed=True),
    lambda v:v['payload_check'].update(completed_steps=True),
    lambda v:v['payload_check']['direct_roles_verified'].pop(),
    lambda v:v['input_fingerprints'].pop(next(iter(v['input_fingerprints']))),
])
def test_bad_receipt_refused(tmp_path, mutation):
    root,binding=part_fixture(tmp_path,mutation)
    with pytest.raises(ValueError): completed_part(root,binding,'prefix1',0)


def test_nonfinite_receipt_cannot_be_published(tmp_path):
    with pytest.raises(ValueError): part_fixture(tmp_path, lambda v:v.update(elapsed_seconds=float('inf')))


def test_success_hash_drift_rejected(tmp_path):
    root,binding=part_fixture(tmp_path)
    (root/'COMPLETE.json').chmod(0o600)
    (root/'COMPLETE.json').write_text(json.dumps({'sha256':'0'*64}))
    (root/'COMPLETE.json').chmod(0o400)
    with pytest.raises(ValueError): completed_part(root,binding,'prefix1',0)


def test_hardlinked_inputs_rejected(tmp_path):
    import os
    p=sealed(tmp_path/'source')
    try: os.link(p,tmp_path/'alias')
    except OSError: pytest.skip('hardlinks unavailable')
    with pytest.raises(ValueError): fingerprint(p)


def test_interrupted_part_never_skipped(tmp_path):
    root=tmp_path/'part';root.mkdir();save_exclusive(root/'INTENT.json',{})
    with pytest.raises(ValueError): completed_part(root,{},'prefix1',0)


def test_failed_part_never_skipped(tmp_path):
    root,binding=part_fixture(tmp_path);save_exclusive(root/'FAILED.json',{'failure':True})
    with pytest.raises(ValueError): completed_part(root,binding,'prefix1',0)


def test_final_needs_unique_complete_coverage():
    rows=[{'case':c,'rank':r} for c,r in PARTS];complete_coverage(rows)
    for bad in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]]):
        with pytest.raises(ValueError): complete_coverage(bad)


def test_no_loader_on_import_and_old_checker_untouched():
    command="import sys; import phase1.scripts.partitioned_pivot_postflight_20260907; assert 'torch' not in sys.modules"
    p=subprocess.run([sys.executable,'-B','-c',command],capture_output=True)
    assert p.returncode==0
    root=Path(__file__).parents[2]
    new=(root/'phase1/scripts/partitioned_pivot_postflight_20260907.py').read_text()
    assert new.index("event(folder, 'hash_pre_done'") < new.index('        import torch') < new.index('torch.load(')
    assert 'original.manifest(cp' in new and 'verify_payload_observation(*payload' in new


def test_part_hash_failure_prevents_loader_and_is_preserved(tmp_path, monkeypatch):
    import builtins
    from phase1.scripts import partitioned_pivot_postflight_20260907 as m
    cp=tmp_path/'cp';cp.mkdir();out=tmp_path/'out';out.mkdir()
    monkeypatch.setattr(m,'OUT',out)
    monkeypatch.setattr(m,'deployment',lambda:{'audit':'fixed'})
    monkeypatch.setattr(m,'authenticate_shared',lambda:({}, {'prefix1':(cp, {'files':{n:{} for n in payload_names(0)}})}))
    def reject(*_): raise ValueError('part_input_hash_drift')
    monkeypatch.setattr(m,'verified_file',reject)
    previous=builtins.__import__
    def no_loader(name,*args,**kwargs):
        if name=='torch': raise AssertionError('loader reached before hashes')
        return previous(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',no_loader)
    with pytest.raises(ValueError,match='part_input_hash_drift'): m.part('prefix1',0)
    assert (out/'prefix1-rank0/FAILED.json').exists()
    assert not (out/'prefix1-rank0/SUCCESS.json').exists()
    with pytest.raises(ValueError,match='incomplete_or_unexpected_part'): m.part('prefix1',0)


def test_shared_authentication_drift_refused_before_loader(monkeypatch):
    from phase1.scripts import partitioned_pivot_postflight_20260907 as m
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','')
    monkeypatch.setattr(m.original,'sha',lambda p:'0'*64)
    with pytest.raises(ValueError,match='previous_authentication_drift'): m.authenticate_shared()


def test_finalizer_checks_both_whole_bundles(tmp_path, monkeypatch):
    from phase1.scripts import partitioned_pivot_postflight_20260907 as m
    binding={'audit':'fixed'}; checks={};matrices={};calls=[]
    for case,rank in PARTS:
        step=1 if case=='prefix1' else 2
        cp=tmp_path/case;cp.mkdir(exist_ok=True);(cp/'pytorch_model').mkdir(exist_ok=True)
        for n in payload_names(rank): sealed(cp/n)
        value={'case':case,'rank':rank,'input_fingerprints':{n:fingerprint(cp/n) for n in payload_names(rank)},
            'payload_check':{'parameters':3,'completed_steps':step,'cumulative_valid_tokens':step*4194304,
                'direct_roles_verified':list(ROLES),'direct_state_sha256':{k:'1'*64 for k in ROLES}}}
        checks[(case,rank)]=value;matrices[case]=(cp,{'binding':{}})
    monkeypatch.setattr(m,'OUT',tmp_path)
    monkeypatch.setattr(m,'deployment',lambda:binding)
    monkeypatch.setattr(m,'authenticate_shared',lambda:({'segments':[]},matrices))
    monkeypatch.setattr(m,'completed_part',lambda folder,b,c,r:checks[(c,r)])
    monkeypatch.setattr(m.original,'PARAMETERS',3)
    monkeypatch.setattr(m.original,'sha',lambda p:m.AUTH_SHA)
    monkeypatch.setattr(m.original,'read',lambda p:{'state':{k:'1'*64 for k in ROLES}})
    def full_manifest(cp,b,step): calls.append(step);return {'binding':{}}
    monkeypatch.setattr(m.original,'manifest',full_manifest)
    m.finalize()
    assert calls==[1,2] and read_json(tmp_path/'FINAL.json')['model_effect_measured'] is False
