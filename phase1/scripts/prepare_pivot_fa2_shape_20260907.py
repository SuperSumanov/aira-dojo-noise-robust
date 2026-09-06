"""FA2-bound successor of the fixed synthetic pivot-shape qualification.

Reuses the frozen shape driver and held-job controller. Scoped overrides are
restored even on failure; importing this module does not change old profiles.
No effect-data admission, backend fallback, automatic retry, or job polling.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re

BASE=Path('/research/d7/spc/yzyang4')
OUT=BASE/'critic-pivot-shape/submission-20260907-fa2-r4'
BUILD=BASE/'flash-attn-build-20260907-r4'
BUILD_JOB='12648'
BUILD_COMMIT='15402474dec5b5da1e376d3c812f53fe416c5c0b'
BUILD_SCRIPT_SHA='15353d409ceb52c25a9aa7f6080a90849839d5f571bab359b132d29489055893'
BUILD_PRIOR_SHA='43def888311cc5156a91980af6fb1ce46381fcf70a8d769d45e7e5441a0bac7d'
SCRIPT='phase1/scripts/pivot_fa2_shape_20260907.sbatch'
APPROVAL='phase1/manifests/pivot_fa2_shape_approval_20260907.json'
EXTRA_TESTS=['test_critic_fa2_preflight','test_critic_fa2_build_receipt','test_critic_fa2_resumed_receipt','test_pivot_fa2_shape_profile']
RECENT=[('12577','FAILED',98,2),('12635','FAILED',89,1),('12638','FAILED',1,1),('12639','COMPLETED',5,1),('12641','FAILED',2126,1)]
BUILD_CAP=5760
CAP=3840
EVIDENCE=('cpu-tests.log','runtime-plan.log','runtime-plan.json','space-probe.json',
          'space-probe-released.json','fa2-build-binding.json','fa2-cpu.json')


def build_binding():
    from phase1.critic_fa2_build_receipt import bind_resumed_build
    return bind_resumed_build(BUILD,expected_commit=BUILD_COMMIT,
        expected_job=BUILD_JOB,expected_script_sha=BUILD_SCRIPT_SHA,expected_prior_sha=BUILD_PRIOR_SHA)


def parse_accounting(raw,prior):
    expected={row[0]:row for row in prior};seen=set();total=0;build_seconds=None
    for line in raw.splitlines():
        if not line.strip():continue
        jid,state,elapsed,tres,exitcode=line.split('|')[:5]
        if jid in seen:raise RuntimeError('duplicate_accounting')
        seen.add(jid)
        if jid==BUILD_JOB:
            if not (state=='COMPLETED' and exitcode=='0:0' and elapsed.isdecimal()
                    and 0<int(elapsed)<=BUILD_CAP and 'gres/gpu=1' in tres.split(',')):
                raise RuntimeError('build_terminal_not_accepted')
            build_seconds=int(elapsed);total+=build_seconds
        elif jid in expected:
            _,s,t,g=expected[jid]
            if not (state==s and elapsed==str(t) and exitcode==('0:0' if s=='COMPLETED' else '1:0')
                    and f'gres/gpu={g}' in tres.split(',')):
                raise RuntimeError('prior_accounting_drift')
            total+=t*g
        else:raise RuntimeError('unknown_accounting')
    if seen!=set(expected)|{BUILD_JOB} or sum(t*g for _,_,t,g in prior)!=9423:
        raise RuntimeError('incomplete_accounting')
    if total+CAP>21600:raise RuntimeError('engineering_envelope_exceeded')
    return total


def kernel_receipt_valid(value,*,job,commit,build_sha):
    """Independent shape/threshold check of the GPU-kernel receipt fields."""
    import math
    if not (value.get('classification')=='FA2_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT'
            and value.get('job_id')==job and value.get('code_commit')==commit
            and value.get('binding',{}).get('build_sha256')==build_sha):return False
    rows=value.get('devices',[])
    if len(rows)!=2 or [r.get('device') for r in rows]!=[0,1]:return False
    for row in rows:
        if not ('PRO 6000' in row.get('name','').upper() and row.get('long_length')==16384
                and row.get('long_forward_backward_finite') is True and row.get('long_full_reference_compared') is False):return False
        cases=row.get('short_reference_cases',[])
        if [r.get('mode') for r in cases]!=['dense','varlen']:return False
        if [r.get('lengths') for r in cases]!=[[129],[31,97]]:return False
        for case in cases:
            errors=case.get('errors',{})
            if set(errors)!={'output','dq','dk','dv'}:return False
            for err in errors.values():
                for key,limit in [('relative_l2',.02),('maximum_absolute',.05)]:
                    v=err.get(key)
                    if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=limit:return False
    return True


@contextmanager
def configured_profile():
    # Lazy import: do not mutate the old shared controller on module import.
    from phase1.scripts import prepare_pivot_zero3_shape_20260906 as m
    c=m.c
    old_m={k:getattr(m,k) for k in ('SCRIPT','APPROVAL','TESTS','files','accounting','bind','ready','allocated')}
    old_out=c.OUT
    prior=m.PRIOR+RECENT
    def files(commit):
        # Matrix regression tests read the prior immutable manifest explicitly.
        return sorted(set(old_m['files'](commit))|{old_m['APPROVAL'],old_m['SCRIPT']})
    def accounting():
        raw=c.run(['sacct','-X','-n','-P','-j',','.join([r[0] for r in prior]+[BUILD_JOB]),
            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode()
        return parse_accounting(raw,prior)
    def bind(control,commit):
        hashes=old_m['bind'](control,commit)
        a=json.loads((control/APPROVAL).read_bytes())
        c.require(a['fa2_build_job']==BUILD_JOB and a['fa2_build_commit']==BUILD_COMMIT
            and a['fa2_build_script_sha256']==BUILD_SCRIPT_SHA and a['fa2_overlay_isolated'] is True
            and a['fa2_build_prior_sha256']==BUILD_PRIOR_SHA
            and a['fa2_gpu_check_seconds']==120 and a['enumerated_prior_actual_gpu_seconds_excluding_build']==9423
            and a['build_gpu_seconds_upper_bound']==BUILD_CAP and a['enumerated_combined_upper_bound_gpu_seconds']==19023
            and a['enumerated_engineering_envelope_gpu_seconds']==21600,
            'fa2_approval_drift')
        build_binding()
        return hashes
    def ready(control,commit):
        r=json.loads((OUT/'READY.json').read_bytes())
        c.require(r['commit']==commit and r['hashes']==bind(control,commit),'ready_drift')
        c.require(set(r['evidence_hashes'])==set(EVIDENCE)
            and all(c.sha(OUT/n)==h for n,h in r['evidence_hashes'].items()),'preparation_evidence_drift')
        b=json.loads((OUT/'fa2-build-binding.json').read_bytes())
        c.require(b==build_binding() and r['fa2_build_receipt_sha256']==b['build_receipt_sha256'],'fa2_ready_drift')
        cpu=json.loads((OUT/'fa2-cpu.json').read_bytes())
        c.require(cpu['binding']['build_sha256']==b['build_receipt_sha256']
            and cpu['classification']=='FA2_CPU_BINDING_NOT_GPU_ACCEPTANCE','fa2_cpu_binding_drift')
        space=json.loads((OUT/'space-probe.json').read_bytes());released=json.loads((OUT/'space-probe-released.json').read_bytes())
        c.require(space['passed'] is True and space['requested_bytes']==68719476736 and space['allocated_bytes']>=68719476736
            and released['own_inode_removed'] is True and not (OUT/'own-checkpoint-space-probe.bin').exists(),'space_proof_failed')
        return r
    def allocated(control,commit):
        r=ready(control,commit);jid=os.environ.get('SLURM_JOB_ID')
        path=BASE/'critic-pivot-shape'/('job-'+jid)/'fa2-kernel.json'
        c.require(kernel_receipt_valid(json.loads(path.read_bytes()),job=jid,commit=commit,
            build_sha=r['fa2_build_receipt_sha256']),'gpu_kernel_receipt_not_accepted')
        old_m['allocated'](control,commit)
    try:
        c.OUT=OUT;m.SCRIPT=SCRIPT;m.APPROVAL=APPROVAL
        m.TESTS=[n for n in old_m['TESTS'] if n!='test_pivot_shape_profile']+EXTRA_TESTS
        m.files=files;m.accounting=accounting;m.bind=bind;m.ready=ready;m.allocated=allocated
        yield m
    finally:
        c.OUT=old_out
        for key,value in old_m.items():setattr(m,key,value)


def prepare(m,control,commit):
    c=m.c;m.queue();m.accounting();b=build_binding()
    c.safe_root(BASE);OUT.parent.mkdir(mode=0o700,exist_ok=True);c.safe_root(OUT.parent)
    OUT.mkdir(mode=0o700)
    c.record('prepare_intent.json',{'commit':commit,'gpu_seconds_upper_bound':CAP,
        'controller_sha256':c.sha(__file__),'fa2_build_receipt_sha256':b['build_receipt_sha256']})
    c.record('fa2-build-binding.json',b)
    c.require(not control.exists(),'control_exists')
    c.run(['git','-C',c.REPO,'fetch','--no-tags','https://github.com/SuperSumanov/aira-dojo-noise-robust.git',commit],timeout=240)
    c.run(['git','-C',c.REPO,'worktree','add','--detach','--no-checkout',control,commit])
    c.run(['git','-C',control,'sparse-checkout','set','--no-cone','--stdin'],data=('\n'.join('/'+n for n in m.files(commit))+'\n').encode())
    c.run(['git','-C',control,'checkout','--detach',commit]);hashes=m.bind(control,commit)
    c.run(['bash','-n',control/SCRIPT])
    env=dict(c.ENV,PYTHONPATH=str(BUILD/'overlay')+os.pathsep+str(control),
        TRITON_CACHE_DIR='/tmp/critic-pivot-fa2-shape-triton')
    Path(env['TRITON_CACHE_DIR']).mkdir(mode=0o700,exist_ok=True)
    tests=['-q','-p','no:cacheprovider',*['phase1/tests/'+t+'.py' for t in m.TESTS]]
    command="import sys; sys.path.append('/research/d7/spc/yzyang4/venvs/exp/lib/python3.11/site-packages'); import pytest; raise SystemExit(pytest.main("+repr(tests)+"))"
    (OUT/'cpu-tests.log').write_bytes(c.run([c.RUNTIME/'bin/python','-B','-c',command],env=env,cwd=control,timeout=240))
    c.run([c.RUNTIME/'bin/python','-B','-m','phase1.critic_fa2_preflight','--overlay',BUILD/'overlay',
        '--manifest',BUILD/'BUILT.json','--expected-sha256',b['build_receipt_sha256'],'--output',OUT/'fa2-cpu.json'],env=env,cwd=control,timeout=60)
    check="import json,torch; from phase1.pivot_zero3_shape_fixture import summary; from phase1.global_local_zero3_session import runtime_binding; from phase1.scripts.validate_pivot_zero3_shape_20260906 import SNAPSHOT,MANIFEST,MANIFEST_SHA; from phase1.verify_critic_component_g0 import validate_model_snapshot,sha256_file; from pathlib import Path; assert sha256_file(Path(MANIFEST))==MANIFEST_SHA; validate_model_snapshot(SNAPSHOT,Path(MANIFEST)); b=runtime_binding(); assert not torch.cuda.is_initialized(); print(json.dumps({'plan':summary(),'runtime':b,'model_manifest_sha256':MANIFEST_SHA,'gpu_context_created':False},sort_keys=True))"
    raw=c.run([c.RUNTIME/'bin/python','-B','-c',check],env=env,cwd=control,timeout=240)
    (OUT/'runtime-plan.log').write_bytes(raw);runtime=json.loads(raw.decode().strip().splitlines()[-1])
    c.require(runtime['gpu_context_created'] is False and runtime['plan']['plan_sha256']=='d1fcdddc6ecb6e58d025f97ae9633b2bd5cb0390b20a05cb9cbd597e0a6e5ec6','runtime_plan_drift')
    c.record('runtime-plan.json',runtime)
    c.run([BASE/'venvs/exp/bin/python','-B','-c','from phase1.pivot_checkpoint_space import probe; import sys; probe(sys.argv[1])',OUT],env=env,cwd=control,timeout=180)
    c.require(m.bind(control,commit)==hashes and build_binding()==b,'end_prepare_drift')
    c.record('READY.json',{'commit':commit,'control':str(control),'hashes':hashes,'approval_sha256':hashes[APPROVAL],
        'gpu_seconds_upper_bound':CAP,'prior_actual_gpu_seconds':m.accounting(),'status':'READY_NOT_SUBMITTED',
        'real_corpus_reads':0,'fa2_build_receipt_sha256':b['build_receipt_sha256'],
        'evidence_hashes':{n:c.sha(OUT/n) for n in EVIDENCE}})
    print(json.dumps({'status':'READY_NOT_SUBMITTED','files':len(hashes),'gpu_seconds_upper_bound':CAP}))


def kernel(m,control,commit):
    c=m.c;r=m.ready(control,commit);jid=os.environ.get('SLURM_JOB_ID')
    c.require(json.loads((OUT/'RELEASED.json').read_bytes())=={'job_id':jid,'commit':commit},'allocated_job_identity')
    c.require(os.environ.get('ZERO3_GPU_APPROVAL_RECEIPT_SHA')==r['approval_sha256'],'allocated_approval_identity')
    m.allocation(control,jid,'RUNNING')
    from phase1.scripts.validate_zero3_session_gpu_20260905 import allocation_gate
    from phase1.critic_fa2_preflight import cpu_binding,check_device,verify_overlay
    allocation_gate(os.environ)
    b=cpu_binding(BUILD/'overlay',BUILD/'BUILT.json',r['fa2_build_receipt_sha256'])
    import torch
    c.require(torch.cuda.device_count()==2,'two_gpus_required')
    value={'classification':'FA2_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT','binding':b,
        'devices':[check_device(i) for i in (0,1)],'job_id':jid,'code_commit':commit}
    verify_overlay(BUILD/'overlay',BUILD/'BUILT.json',r['fa2_build_receipt_sha256'])
    c.require(kernel_receipt_valid(value,job=jid,commit=commit,build_sha=r['fa2_build_receipt_sha256']),'kernel_receipt_schema')
    path=BASE/'critic-pivot-shape'/('job-'+jid)/'fa2-kernel.json'
    with path.open('x') as f:json.dump(value,f,sort_keys=True,indent=2)
    print('FA2_TWO_GPU_KERNEL_CHECK_PASSED_NOT_MODEL_EFFECT')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','submit','release','kernel','allocated']);p.add_argument('--commit',required=True)
    a=p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.commit):raise SystemExit('exact_commit_required')
    os.umask(0o077);control=BASE/'worktrees'/('critic-pivot-fa2-shape-'+a.commit[:12])
    try:
        with configured_profile() as m:
            if a.action=='prepare':prepare(m,control,a.commit)
            elif a.action=='kernel':kernel(m,control,a.commit)
            else:getattr(m,a.action)(control,a.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__}))
        raise SystemExit(1)
