"""Preserve the actual Socket job boundary failure; never deserialize artifacts."""
import hashlib,json,os,re,subprocess
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
ROOT=BASE/'job-12573'
CONTROL=BASE/'submission-20260906-3090-socket'
SOURCE='b84e8baea4de65a16038b4136cee094d29716964'
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def main():
    ready=json.loads((CONTROL/'READY.json').read_bytes())
    assert ready['commit']==SOURCE
    assert json.loads((CONTROL/'RELEASED.json').read_bytes())=={'commit':SOURCE,'job_id':'12573'}
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-n','-P','-j','12573','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=20)
    row=accounting.decode().strip().split('|')
    assert row[:3]==['12573','FAILED','133'] and row[4]=='1:0' and 'gres/gpu=2' in row[3].split(',')
    assert (ROOT/'exit_status.txt').read_text().strip()=='1'
    assert not (ROOT/'trajectories/summary.json').exists()
    assert not list((ROOT/'trajectories').rglob('manifest.json'))
    assert not list((ROOT/'trajectories').rglob('trajectory.json'))
    hashes={};segv=0
    for name in ('worker.log','driver.log','exit_status.txt','build_tools.json','resource_usage.txt','telemetry.txt','file_trace.log'):
        p=ROOT/name;assert p.is_file() and not p.is_symlink() and p.stat().st_uid==os.getuid()
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for line in stream:
                assert not SHAPE.search(line)
                if name=='file_trace.log':
                    assert not any(x in line for x in (b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-'))
                    segv+=int(b'--- SIGSEGV {' in line)
                h.update(line)
        hashes[name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
    driver=(ROOT/'driver.log').read_text()
    assert 'zero3_pending_gradient' in driver and 'session.save(' in driver
    assert 'Init COMPLETE' in driver and 'NET/Socket' in driver and segv==0
    build=json.loads((ROOT/'build_tools.json').read_bytes())
    assert build['status']=='ALLOCATED_PRIVATE_CUDA128_BUILD_TOOLS_PASS'
    result={'status':'TERMINAL_CPU_OFFLOAD_BOUNDARY_FAILURE_RECORDED','job_id':'12573','source_commit':SOURCE,
        'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'elapsed_seconds':133,'allocated_gpu_seconds':266,'aggregate_gpu_seconds':419,
        'completed_trajectories':0,'checkpoint_manifests':0,'socket_initialization_completed':True,
        'sigsegv_events':segv,'failure':'zero3_pending_gradient at first full-trajectory checkpoint boundary',
        'original_file_hashes':hashes,'model_benefit_measured':False,'automatic_retry':False,
        'credential_scan_hits':0,'protected_path_markers_found':0}
    with (ROOT/'failure_acceptance.json').open('x') as out:json.dump(result,out,sort_keys=True,indent=2)
    with (ROOT/'failure_sacct.txt').open('xb') as out:out.write(accounting)
    print(json.dumps({'status':result['status'],'gpu_seconds':266,'aggregate_gpu_seconds':419,
        'audit_receipt_sha256':hashlib.sha256((ROOT/'failure_acceptance.json').read_bytes()).hexdigest(),
        'trace':hashes['file_trace.log']},sort_keys=True))


if __name__=='__main__':main()
