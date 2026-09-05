import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recover_historical_pool_lineage as p

def fixture():
    ids=['a','b'];key=hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:12]
    obj={'version':1,'launcher_type':'srun_pool','allocation_id':'123','node_list':'gpu',
         'allocations':[{'allocation_id':'123','node_list':'gpu','started_at':'2026-08-11'}],
         'snapshot_path':'/old/snapshot','python_executable':'/old/python',
         'pool_dir':'/old/batch/srun_pool/'+key,'created_at':'2026-08-11T10:00:00+08:00','updated_at':'unused',
         'tasks':{cid:{'attempt':1,'attempts':[{'attempt':1,'step_id':'123.0'}],
                      'config_path':'/old/config','experiment_dir':'/old/batch/'+cid,
                      'task_name':'task','step_id':'123.0'} for cid in ids}}
    origins=[(cid+'__2026-08-11',{'config_member':'batch/'+cid+'/dojo_config.json',
                                'recorded_slurm_id':'123.0'}) for cid in ids]
    return obj,'batch/srun_pool/'+key+'/manifest.json',origins

def test_actual_record_binding_and_ignored_status():
    obj,member,origins=fixture()
    a=p.parse_manifest(json.dumps(obj).encode(),member,'sha',origins)
    obj['tasks']['a']['reason']='not a selection variable'
    b=p.parse_manifest(json.dumps(obj).encode(),member,'sha',origins)
    assert a['identity']==b['identity'] and a['tasks']==b['tasks']
    assert all(t['step_matches_recorded_config'] for t in a['tasks'])

@pytest.mark.parametrize('mutation', ['key','date','unknown','experiment','pool','attempt','alloc','secret','dupe'])
def test_fail_closed(mutation):
    obj,member,origins=fixture()
    if mutation=='key':member=member.replace(member.split('/')[2],'0'*12)
    if mutation=='date':obj['created_at']='2026-09-01T10:00:00+08:00'
    if mutation=='unknown':obj['unexpected']=True
    if mutation=='experiment':obj['tasks']['a']['experiment_dir']='/wrong'
    if mutation=='pool':obj['pool_dir']='/wrong'
    if mutation=='attempt':obj['tasks']['a']['attempts'][0]['unexpected']=0
    if mutation=='alloc':obj['allocations']=[]
    if mutation=='secret':obj['node_list']='sk-'+'X'*20
    raw=json.dumps(obj).encode()
    if mutation=='dupe':raw=raw[:-1]+b',"tasks":{}}'
    with pytest.raises(Exception):p.parse_manifest(raw,member,'sha',origins)

def test_unmatched_not_admitted_and_step_difference_not_silent():
    obj,member,origins=fixture();obj['tasks']['a']['step_id']='123.9'
    result=p.parse_manifest(json.dumps(obj).encode(),member,'sha',origins[:1])
    assert result['tasks'][0]['step_matches_recorded_config'] is False
    assert result['tasks'][1]['run_id'] is None

def test_closure_never_relaxes_hold():
    ledger={'a':{'conservative_component_sha256':'1','old_hold_closure_blocks_train':True},
            'b':{'conservative_component_sha256':'2','old_hold_closure_blocks_train':False},
            'c':{'conservative_component_sha256':'3','old_hold_closure_blocks_train':False}}
    m=[{'instance_sha256':'pool','tasks':[{'run_id':'a'},{'run_id':'b'},{'run_id':None}]}]
    out=p.closure(ledger,m)
    assert out['a']['old_hold_closure_blocks_train'] and out['b']['old_hold_closure_blocks_train']
    assert not out['c']['old_hold_closure_blocks_train']

def test_archive_reads_only_manifest_and_checks_hash(tmp_path,monkeypatch):
    obj,member,origins=fixture();path=tmp_path/'a.tar.gz'
    with tarfile.open(path,'w:gz') as tar:
        for name,raw in [(member,json.dumps(obj).encode()),('batch/a/checkpoint/journal.jsonl',b'NEVER_READ'),('batch/a/env_variables.json',b'NEVER_READ')]:
            m=tarfile.TarInfo(name);m.size=len(raw);tar.addfile(m,io.BytesIO(raw))
    original=tarfile.TarFile.extractfile;opened=[]
    def guard(self,m):
        opened.append(m.name);assert m.name==member
        return original(self,m)
    monkeypatch.setattr(tarfile.TarFile,'extractfile',guard)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    result=p.scan(path,sha,origins,time.monotonic()+10)
    assert opened==[member] and len(result['manifest_records'])==1
    with pytest.raises(Exception):p.scan(path,'wrong',origins,time.monotonic()+10)

def test_duplicate_manifest_rejected(tmp_path):
    obj,member,origins=fixture();path=tmp_path/'a.tar.gz';raw=json.dumps(obj).encode()
    with tarfile.open(path,'w:gz') as tar:
        for _ in range(2):
            m=tarfile.TarInfo(member);m.size=len(raw);tar.addfile(m,io.BytesIO(raw))
    with pytest.raises(Exception):p.scan(path,hashlib.sha256(path.read_bytes()).hexdigest(),origins,time.monotonic()+10)

def test_local_pool_is_not_a_slurm_attestation():
    obj,member,origins=fixture()
    for key in ('allocations','allocation_id','node_list'):obj.pop(key)
    obj['launcher_type']='local_gpu_pool';obj['pool_dir']=obj['pool_dir'].replace('srun_pool','local_gpu_pool')
    member=member.replace('srun_pool','local_gpu_pool')
    for task in obj['tasks'].values():
        task.pop('step_id');task['execution_id']='host:123:45:a1'
        task['attempts']=[{'attempt':1,'execution_id':'host:123:45:a1','gpu_uuids':['test-device']}]
    result=p.parse_manifest(json.dumps(obj).encode(),member,'sha',origins)
    assert result['identity']['launcher_type']=='local_gpu_pool'
    assert all(t['step_matches_recorded_config'] is None for t in result['tasks'])
    assert all(t['recorded_launcher_execution_id']=='host:123:45:a1' for t in result['tasks'])
    obj['tasks']['a']['attempts'][0]['unknown_runtime_value']=1
    with pytest.raises(Exception):p.parse_manifest(json.dumps(obj).encode(),member,'sha',origins)
