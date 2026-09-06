"""Synthetic byte fixtures only; do not claim a real build or GPU result."""
import hashlib
import json
import pytest
from phase1.critic_fa2_build_receipt import bind_resumed_build, bind_completed_build, BuildReceiptError

C='a'*40; SCRIPT='b'*64; JOB='12648'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def put(root,name,value):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
def change(root,name,key,value):
    data=json.loads((root/name).read_bytes());data[key]=value;put(root,name,data)
def raw(root,name,data):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return digest(data)

def fixture(base):
    root=base/'r4';root.mkdir();old=base/'flash-attn-build-20260907-r3'
    compiler=old/'source/flash_attn-2.8.3/build/temp.linux-x86_64-cpython-311'
    preserved={f'evidence-{i}.json':raw(old,f'evidence-{i}.json',b'{}') for i in range(13)}
    copies={n:raw(root/'previous',n,b'{}') for n in preserved}
    copies['ninja.log']=raw(root/'previous','ninja.log',b'# ninja log v7\n')
    copies['build.ninja']=raw(root/'previous','build.ninja',b'graph')
    graph=raw(compiler,'build.ninja',b'graph')
    objects={f'obj-{i}.o':{'bytes':7,'sha256':raw(compiler,f'obj-{i}.o',b'\x7fELFobj')} for i in range(32)}
    prior={'prior_job':'12641','prior_state':'FAILED','prior_elapsed_seconds':2126,'prior_gpu_seconds_total':9423,
        'original_log_version':7,'new_compile_seconds':4800,'new_gpu_seconds_upper_bound':5760,
        'combined_gpu_seconds_upper_bound':19023,'objects':objects,'preserved_receipts':preserved,
        'copied_evidence':copies,'ninja_graph_sha256':graph}
    put(root,'PRIOR_VERIFIED.json',prior);h=digest((root/'PRIOR_VERIFIED.json').read_bytes())
    put(root,'BUILD_INTENT.json',{'job_id':JOB,'source_commit':C,'source_script_sha256':SCRIPT,
        'prior_receipt_sha256':h,'torch':'2.11.0+cu128','cuda':'12.8','arch':'120',
        'cuda_context_created':False,'automatic_retries':0,'explicit_prior_job':'12641','new_compile_seconds':4800})
    wheel='flash_attn-2.8.3-cp311-cp311-linux_x86_64.whl'
    wh=raw(root,'wheels/'+wheel,b'wheel');mh=raw(root,'overlay/member.py',b'module')
    put(root,'BUILT.json',{'classification':'ISOLATED_FA2_RESUMED_BUILD_NOT_GPU_ACCEPTANCE','job_id':JOB,
        'source_commit':C,'prior_receipt_sha256':h,'original_fingerprints_unchanged':True,
        'gpu_used':False,'prior_completed_objects_unchanged':True,'reused_objects':32,
        'wheel':wheel,'wheel_sha256':wh,'overlay_files':{'member.py':mh}})
    for stage in ('compile','overlay-install','import'):
        lh=raw(root,stage+'.log',b'log')
        put(root,stage+'-status.json',{'returncode':0,'elapsed_seconds':1.2,'log_sha256':lh})
    put(root,'SOURCE_POST_VERIFIED.json',{'original_files_verified':6608,'inventory_sha256':'c'*64})
    put(root,'submission-v7/RELEASED.json',{'job_id':JOB,'commit':C})
    put(root,'submission-v7/INDEPENDENT_PRE_RELEASE.json',{'job_id':JOB,'commit':C,'prior_receipt_sha256':h,
        'objects_checked':32,'source_files_independently_checked':6608})
    return root,old,compiler,h

def run(root,h):return bind_resumed_build(root,expected_commit=C,expected_job=JOB,
    expected_script_sha=SCRIPT,expected_prior_sha=h)

def test_explicit_resume_is_distinct_from_fresh_build_and_gpu(tmp_path):
    root,old,compiler,h=fixture(tmp_path);r=run(root,h)
    assert r['classification']=='FA2_RESUMED_ARTIFACT_BINDING_NOT_SLURM_OR_GPU_ACCEPTANCE'
    assert r['gpu_kernel_verified'] is False and len(r['stages'])==3
    with pytest.raises(BuildReceiptError,match='fresh_build_classification'):
        bind_completed_build(root,expected_commit=C,expected_job=JOB,expected_script_sha=SCRIPT)

@pytest.mark.parametrize('mutation',['job','commit','script','prior_hash','prior_scope','prior_complete',
    'fresh_classification','object_changed','graph_changed','failure_changed','copy_changed',
    'stage_failed','stage_timeout','stage_nan','stage_negative','log_changed','wheel_changed','overlay_added',
    'overlay_changed','source_count','release','independent','reused','gpu','retry','duplicate'])
def test_resume_rejects_unbound_or_failed_evidence(tmp_path,mutation):
    root,old,compiler,h=fixture(tmp_path)
    if mutation=='job':change(root,'BUILD_INTENT.json','job_id','12649')
    elif mutation=='commit':change(root,'BUILT.json','source_commit','d'*40)
    elif mutation=='script':change(root,'BUILD_INTENT.json','source_script_sha256','d'*64)
    elif mutation=='prior_hash':h='d'*64
    elif mutation=='prior_scope':change(root,'PRIOR_VERIFIED.json','prior_job','12635')
    elif mutation=='prior_complete':put(old,'BUILT.json',{})
    elif mutation=='fresh_classification':change(root,'BUILT.json','classification','ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE')
    elif mutation=='object_changed':raw(compiler,'obj-0.o',b'changed')
    elif mutation=='graph_changed':raw(compiler,'build.ninja',b'changed')
    elif mutation=='failure_changed':raw(old,'evidence-0.json',b'changed')
    elif mutation=='copy_changed':raw(root/'previous','ninja.log',b'changed')
    elif mutation=='stage_failed':change(root,'compile-status.json','returncode',1)
    elif mutation=='stage_timeout':put(root,'compile-timeout.json',{'seconds':4800})
    elif mutation=='stage_nan':change(root,'compile-status.json','elapsed_seconds',float('nan'))
    elif mutation=='stage_negative':change(root,'import-status.json','elapsed_seconds',-1)
    elif mutation=='log_changed':raw(root,'compile.log',b'changed')
    elif mutation=='wheel_changed':raw(root,'wheels/flash_attn-2.8.3-cp311-cp311-linux_x86_64.whl',b'changed')
    elif mutation=='overlay_added':raw(root,'overlay/extra.py',b'extra')
    elif mutation=='overlay_changed':raw(root,'overlay/member.py',b'changed')
    elif mutation=='source_count':change(root,'SOURCE_POST_VERIFIED.json','original_files_verified',6607)
    elif mutation=='release':change(root,'submission-v7/RELEASED.json','job_id','12649')
    elif mutation=='independent':change(root,'submission-v7/INDEPENDENT_PRE_RELEASE.json','objects_checked',31)
    elif mutation=='reused':change(root,'BUILT.json','reused_objects',31)
    elif mutation=='gpu':change(root,'BUILT.json','gpu_used',True)
    elif mutation=='retry':change(root,'BUILD_INTENT.json','automatic_retries',1)
    else:raw(root,'BUILT.json',b'{"job_id":"12648","job_id":"12648"}')
    with pytest.raises((BuildReceiptError,ValueError)):run(root,h)

def test_symlink_object_rejected_when_platform_supports_it(tmp_path):
    root,old,compiler,h=fixture(tmp_path);p=compiler/'obj-0.o';target=compiler/'same-bytes.bin'
    target.write_bytes(p.read_bytes());p.unlink()
    try:p.symlink_to(target)
    except OSError:pytest.skip('OS does not grant symlink creation')
    with pytest.raises(BuildReceiptError,match='unsafe_evidence_file'):run(root,h)
