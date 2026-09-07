import hashlib,json
import pytest
from phase1.critic_ampere_preflight import bind_completed_ampere,BuildReceiptError

COMMIT='a'*40;SCRIPT='b'*64;JOB='123'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def put(root,name,value):
    (root/name).write_text(json.dumps(value))
def fixture(root):
    (root/'overlay').mkdir();(root/'wheels').mkdir();(root/'overlay/member.py').write_bytes(b'fixed')
    wheel='flash_attn-2.8.3-cp311-cp311-linux_x86_64.whl';(root/'wheels'/wheel).write_bytes(b'wheel')
    put(root,'BUILD_INTENT.json',{'job_id':JOB,'source_commit':COMMIT,'source_script_sha256':SCRIPT,
       'torch':'2.11.0+cu128','cuda':'12.8','arch':'80','cuda_context_created':False,'automatic_retries':0})
    put(root,'BUILT.json',{'job_id':JOB,'classification':'ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE',
       'original_fingerprints_unchanged':True,'gpu_used':False,'wheel':wheel,'wheel_sha256':sha(b'wheel'),
       'overlay_files':{'member.py':sha(b'fixed')}})
    for name in ('compiler-job-'+JOB,'build-dependency','compile','overlay-install','import'):
        (root/(name+'.log')).write_bytes(b'log')
        put(root,name+'-status.json',{'returncode':0,'elapsed_seconds':1.2,'log_sha256':sha(b'log')})
    for name in ('SOURCE_PRE_VERIFIED.json','SOURCE_POST_VERIFIED.json'):
        put(root,name,{'original_files_verified':3,'inventory_sha256':'c'*64})
def run(root):return bind_completed_ampere(root,expected_commit=COMMIT,expected_job=JOB,expected_script_sha=SCRIPT)

def test_bind_complete_without_claiming_gpu(tmp_path):
    fixture(tmp_path);r=run(tmp_path)
    assert len(r['stages'])==5 and r['gpu_kernel_verified'] is False

@pytest.mark.parametrize('mutation',['missing','stage_failure','timeout','log','wheel','source','identity','nan','negative'])
def test_bad_build_fails_closed(tmp_path,mutation):
    fixture(tmp_path)
    if mutation=='missing':(tmp_path/'import-status.json').unlink()
    elif mutation=='stage_failure':put(tmp_path,'compile-status.json',{'returncode':1})
    elif mutation=='timeout':put(tmp_path,'compile-timeout.json',{'timeout_seconds':4800})
    elif mutation=='log':(tmp_path/'compile.log').write_bytes(b'changed')
    elif mutation=='wheel':next((tmp_path/'wheels').iterdir()).write_bytes(b'changed')
    elif mutation=='source':put(tmp_path,'SOURCE_POST_VERIFIED.json',{'original_files_verified':0,'inventory_sha256':'c'*64})
    elif mutation=='identity':
        p=tmp_path/'BUILD_INTENT.json';v=json.loads(p.read_text());v['job_id']='124';put(tmp_path,p.name,v)
    else:
        p=tmp_path/'compile-status.json';v=json.loads(p.read_text());v['elapsed_seconds']=float('nan') if mutation=='nan' else -1;put(tmp_path,p.name,v)
    with pytest.raises(BuildReceiptError):run(tmp_path)

def test_duplicate_receipt_keys_rejected(tmp_path):
    fixture(tmp_path);(tmp_path/'BUILT.json').write_text('{"job_id":"123","job_id":"123"}')
    with pytest.raises(BuildReceiptError,match='duplicate'):run(tmp_path)

def test_sm120_build_is_not_ampere_authority(tmp_path):
    fixture(tmp_path);p=tmp_path/'BUILD_INTENT.json';v=json.loads(p.read_text());v['arch']='120';put(tmp_path,p.name,v)
    with pytest.raises(BuildReceiptError,match='runtime_drift'):run(tmp_path)
