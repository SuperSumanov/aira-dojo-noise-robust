"""Terminal failure evidence, owned synthetic receipts only, no pickle loading."""
import hashlib,json,os,re,subprocess
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
ROOT=BASE/'job-12574';CONTROL=BASE/'submission-20260906-3090-consumed'
SOURCE='09c322bf82cc62ce67babb7e2bfee51633e40710'
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=p.read_bytes();assert not SHAPE.search(raw);return json.loads(raw)


def main():
    ready=read(CONTROL/'READY.json');assert ready['commit']==SOURCE
    control=Path(ready['control'])
    assert all(sha(control/p)==h for p,h in ready['hashes'].items())
    assert read(CONTROL/'RELEASED.json')=={'commit':SOURCE,'job_id':'12574'}
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-n','-P','-j','12574','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=20)
    row=accounting.decode().strip().split('|')
    assert row[:3]==['12574','FAILED','199'] and row[4]=='1:0' and 'gres/gpu=2' in row[3].split(',')
    assert (ROOT/'exit_status.txt').read_text().strip()=='1'
    t=ROOT/'trajectories';assert {p.name for p in t.iterdir()}=={'full','prefix2','resume2'}
    data={c:read(t/c/'trajectory.json') for c in ('full','prefix2','resume2')}
    manifests={}
    for case,steps in {'full':(2,3,4),'prefix2':(2,),'resume2':(3,4)}.items():
        assert {p.name for p in (t/case).iterdir()}=={'trajectory.json'}|{f'checkpoint-{s}' for s in steps}
        for step in steps:
            cp=t/case/f'checkpoint-{step}';m=read(cp/'manifest.json')
            assert m['binding']==data['full']['binding'] and m['completed_steps']==step
            expected=set(m['files'])|{'manifest.json'}
            assert {p.relative_to(cp).as_posix() for p in cp.rglob('*') if p.is_file()}==expected
            for name,record in m['files'].items():
                p=cp/name;assert p.is_file() and not p.is_symlink() and p.stat().st_nlink==1 and p.stat().st_uid==os.getuid()
                assert record=={'bytes':p.stat().st_size,'sha256':sha(p)}
            manifests[cp.relative_to(ROOT).as_posix()]=sha(cp/'manifest.json')
    comparisons=[]
    for rank in (0,1):
        first=read(t/'full/checkpoint-2'/f'observed_{rank}.json')
        second=read(t/'prefix2/checkpoint-2'/f'observed_{rank}.json')
        f,p,r=[data[c]['ranks'][rank] for c in ('full','prefix2','resume2')]
        different=[k for k in f['state'] if f['state'][k]!=r['state'][k]]
        assert first==second and different==['master_shards']
        assert f['counters']==r['counters'] and p['records']+r['records']==f['records']
        comparisons.append({'rank':rank,'prefix_checkpoint_equal':True,'final_different_roles':different,
            'final_counters_equal':True,'consumption_equal':True})
    hashes={}
    for name in ('worker.log','driver.log','exit_status.txt','build_tools.json','resource_usage.txt','telemetry.txt','file_trace.log','master_difference_diagnosis.json'):
        p=ROOT/name;assert p.is_file() and not p.is_symlink() and p.stat().st_uid==os.getuid()
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for line in stream:
                assert not SHAPE.search(line)
                if name=='file_trace.log':
                    assert not any(x in line for x in (b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-'))
                h.update(line)
        hashes[name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
    assert b'zero3_final_state_not_equal' in (ROOT/'driver.log').read_bytes()
    assert not (ROOT/'independent_acceptance.json').exists() and not (t/'summary.json').exists()
    result={'status':'TERMINAL_NATIVE_RESTORE_DIFFERENCE_RECORDED_NOT_ACCEPTED','job_id':'12574','source_commit':SOURCE,
        'elapsed_seconds':199,'allocated_gpu_seconds':398,'aggregate_gpu_seconds':817,
        'completed_trajectories':3,'checkpoint_manifests':6,'comparisons':comparisons,'manifest_sha256':manifests,
        'original_file_hashes':hashes,'audit_source_sha256':sha(Path(__file__)),'model_benefit_measured':False,
        'automatic_retry':False,'credential_scan_hits':0,'protected_path_markers_found':0}
    with (ROOT/'failure_acceptance.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    with (ROOT/'failure_sacct.txt').open('xb') as f:f.write(accounting)
    print(json.dumps({'status':result['status'],'receipt_sha256':sha(ROOT/'failure_acceptance.json'),
        'trace':hashes['file_trace.log'],'aggregate_gpu_seconds':817},sort_keys=True))


if __name__=='__main__':main()
