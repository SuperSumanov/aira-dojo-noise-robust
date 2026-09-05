"""Terminal read-only audit of our own tiny job, no checkpoint deserialization."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
ROOT=BASE/'job-12572'
CONTROL=BASE/'submission-20260906-3090-private'
SOURCE='11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c'
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def main():
    ready=json.loads((CONTROL/'READY.json').read_bytes())
    assert ready['commit']==SOURCE and json.loads((CONTROL/'RELEASED.json').read_bytes())=={'commit':SOURCE,'job_id':'12572'}
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-n','-P','-j','12572','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=20)
    row=accounting.decode().strip().split('|')
    assert row[:3]==['12572','FAILED','73'] and row[4]=='1:0' and 'gres/gpu=2' in row[3].split(',')
    assert (ROOT/'exit_status.txt').read_text().strip()=='1'
    assert not (ROOT/'trajectories/summary.json').exists()
    assert len(list((ROOT/'trajectories').rglob('manifest.json')))==0
    assert len(list((ROOT/'trajectories').rglob('trajectory.json')))==0
    hashes={}
    for name in ('worker.log','driver.log','exit_status.txt','build_tools.json','resource_usage.txt','telemetry.txt','file_trace.log'):
        p=ROOT/name;assert p.is_file() and not p.is_symlink() and p.stat().st_uid==os.getuid()
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for line in stream:
                assert not SHAPE.search(line)
                if name=='file_trace.log':
                    assert not any(x in line for x in (b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-'))
                h.update(line)
        hashes[name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
    assert hashes['file_trace.log']['sha256']=='39c71ce4e6b3584b782d20efa65d7d68dd5ce780b9f580b976b19e479ff90fce'
    build=json.loads((ROOT/'build_tools.json').read_bytes())
    assert build['status']=='ALLOCATED_PRIVATE_CUDA128_BUILD_TOOLS_PASS' and build['verified_files_and_links']==1735
    tails={};faults={};python_execs=[]
    with (ROOT/'file_trace.log').open() as stream:
        for line in stream:
            pid=line.split()[0];tails.setdefault(pid,deque(maxlen=20)).append(line.rstrip())
            if '--- SIGSEGV {' in line:faults[pid]=list(tails[pid])
            if 'execve(' in line and '/bin/python' in line:python_execs.append(line.rstrip())
    assert set(faults)=={'876825','876826'}
    assert all(any('infiniband/irdma1' in x for x in tail) for tail in faults.values())
    assert all('/venvs/critic-blackwell-g0-20260905-r5/bin/python' in x for x in python_execs)
    result={'status':'TERMINAL_GPU_INITIALIZATION_FAILURE_RECORDED','job_id':'12572','source_commit':SOURCE,
        'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'elapsed_seconds':73,
        'allocated_gpu_seconds':146,'aggregate_prior_gpu_seconds_including_this_job':153,
        'toolchain_precheck_passed':True,'completed_trajectories':0,'checkpoint_manifests':0,
        'faulted_process_tails':faults,'python_execs':python_execs,'original_file_hashes':hashes,
        'working_hypothesis':'RDMA enumeration initialization fault; filesystem tail alone is not a native stack or causal proof',
        'model_benefit_measured':False,'automatic_retry':False,'credential_scan_hits':0,'protected_path_markers_found':0}
    with (ROOT/'failure_acceptance.json').open('x') as out:json.dump(result,out,sort_keys=True,indent=2)
    with (ROOT/'failure_sacct.txt').open('xb') as out:out.write(accounting)
    print(json.dumps({'status':result['status'],'gpu_seconds':146,'aggregate_gpu_seconds':153,
        'faulted_processes':len(faults),'audit_receipt_sha256':hashlib.sha256((ROOT/'failure_acceptance.json').read_bytes()).hexdigest()},sort_keys=True))


if __name__=='__main__':main()
