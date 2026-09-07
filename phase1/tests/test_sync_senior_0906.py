"""No network or corpus access: fixed manifest and destination negative controls."""
import copy
import hashlib
import json
import pytest
from phase1.scripts import sync_senior_0906_bounded_20260908 as m


def fixture_manifest():
    rows=[[f'file_identifier_{i:02d}',f'archive_{i:02d}.tar.gz','application/gzip'] for i in range(11)]
    return dict(folder='0906',folder_id='folder_identifier_00',items=rows,archives=copy.deepcopy(rows))


def bind(tmp_path,monkeypatch,value):
    p=tmp_path/'inventory.json';raw=json.dumps(value).encode();p.write_bytes(raw)
    monkeypatch.setattr(m,'MANIFEST',p)
    monkeypatch.setattr(m,'MANIFEST_SHA',hashlib.sha256(raw).hexdigest())


def test_fixed_scope(tmp_path,monkeypatch):
    value=fixture_manifest();bind(tmp_path,monkeypatch,value)
    assert m.bound_manifest()==(value['archives'],value['folder_id'])


@pytest.mark.parametrize('kind',['date','count','sidecar','duplicate_id','duplicate_name','traversal','backslash','newline','subfolder','credential','hash'])
def test_manifest_rejection(tmp_path,monkeypatch,kind):
    v=fixture_manifest()
    if kind=='date':v['folder']='0905'
    elif kind=='count':v['items'].pop();v['archives'].pop()
    elif kind=='sidecar':v['items'].append(['sidecar_identifier','data.config_v2.jsonl','application/json'])
    elif kind=='duplicate_id':v['archives'][1][0]=v['archives'][0][0]
    elif kind=='duplicate_name':v['archives'][1][1]=v['archives'][0][1]
    elif kind=='traversal':v['archives'][0][1]='../archive.tar.gz'
    elif kind=='backslash':v['archives'][0][1]='folder\\archive.tar.gz'
    elif kind=='newline':v['archives'][0][1]='archive\n.tar.gz'
    elif kind=='subfolder':v['archives'][0][2]='application/vnd.google-apps.folder'
    elif kind=='credential':v['archives'][0][1]='sk-'+('x'*24)+'.tar.gz'
    if kind!='sidecar':v['items']=copy.deepcopy(v['archives'])
    bind(tmp_path,monkeypatch,v)
    if kind=='hash':monkeypatch.setattr(m,'MANIFEST_SHA','0'*64)
    with pytest.raises(RuntimeError):m.bound_manifest()


@pytest.mark.parametrize('method,url,expected',[
    ('GET','https://drive.google.com/uc',True),
    ('GET','https://drive.usercontent.google.com/download',True),
    ('GET','https://content.googleusercontent.com/object',True),
    ('POST','https://drive.google.com/uc',False),
    ('GET','http://drive.google.com/uc',False),
    ('GET','https://drive.google.com.example.org/uc',False),
    ('GET','https://example.org/uc',False),
])
def test_request_scope(method,url,expected):
    assert m.allowed_request(method,url) is expected


def test_hard_deadline():
    with pytest.raises(RuntimeError,match='whole_operation_deadline'):
        m.deadline_expired(None,None)
