"""Closed19136 metadata only. No rerun, gate change, code/label/log export."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v3')
PIN = '2736fb9326f62f3c83bc0cebc4854ba629991e5b5e4bb69e708aa91e24b74e7e'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw = p.read_bytes()
    assert not SECRET.search(raw), 'credential shape refused'
    return json.loads(raw)
def error(x):
    if x is None: return None
    if not isinstance(x, dict): return dict(container_type=type(x).__name__,message_withheld=True)
    out = {k:x[k] for k in ('type','error_type') if k in x}
    out['frames'] = [{k:r[k] for k in ('file','line','function') if k in r} for r in x.get('frames',[])]
    return out

def main():
    assert sha(ROOT/'plan.json') == PIN
    plan, closed = read(ROOT/'plan.json'), read(ROOT/'closed.json')
    assert read(ROOT/'launch.json')['job'] == '19136'
    assert plan['planned'] == 32 and closed['complete'] == 31
    assert all(sha(ROOT/n) == h for n,h in plan['files'].items())
    prior = ROOT/'readout-20261018-v1'
    summary = read(prior/'summary.json')
    assert summary['complete'] == 31 and summary['predeclared_success_gate_met'] is False
    before = {p.name:sha(p) for p in prior.iterdir() if p.is_file()}
    out = ROOT/'closure-evidence-20261018-v1'; out.mkdir(mode=0o700)
    def write(name,value):
        raw=json.dumps(value,sort_keys=True,indent=2,allow_nan=False).encode()
        assert not SECRET.search(raw)
        with (out/name).open('xb') as f:f.write(raw)
    rows=[]
    for s in plan['schedule']:
        ep=ROOT/f"episode-{s['index']}"
        f,c=read(ep/'finished.json'),read(ep/'closed.json')
        rows.append(dict(index=s['index'],block=s['block'],task=s['task'],quota_mode=s['quota_mode'],
            status=f.get('status'),returncode=c.get('returncode'),cleanup_verified=c.get('cleanup_verified'),
            error=error(f.get('error')),closed_error=error(c.get('error')),
            finished_sha256=sha(ep/'finished.json'),closed_sha256=sha(ep/'closed.json'),
            complete=c.get('returncode')==0 and c.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted'),
            finished_keys=sorted(f),closed_keys=sorted(c)))
    assert sum(r['complete'] for r in rows)==31
    write('worker-closure.json',rows)
    blocks=[]
    for b in range(4):
        es=[]
        for raw in (ROOT/f'generation-{b}/events.jsonl').read_bytes().splitlines():
            assert not SECRET.search(raw)
            e=json.loads(raw)
            if e['event'] not in ('queued','admitted','released','cancelled'):continue
            r={k:e[k] for k in ('event','time','key') if k in e}
            if e['event']=='queued':r['request']={k:e['request'][k] for k in ('key','task','role','requested','run')}
            es.append(r)
        write(f'generation-{b}.json',es)
        q=[]
        for raw in (ROOT/f'pool-{b}/events.jsonl').read_bytes().splitlines():
            assert not SECRET.search(raw)
            e=json.loads(raw)
            q.append({k:e[k] for k in ('event','time','key','device','home','active','queued') if k in e})
        write(f'queue-{b}.json',q)
        ec=read(ROOT/f'block-{b}/execution-closed.json')
        blocks.append(dict(block=b,execution_closed={k:ec[k] for k in ('gpu_clean','telemetry_errors','returncodes','cleanup_verified') if k in ec},
            steps=read(ROOT/f'block-{b}/steps.json'),budget_slot_exists=(ROOT/f'block-{b}/budget-slot.json').exists()))
    acct=subprocess.check_output(['sacct','-j','19136','-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES,Start,End'],text=True).strip().splitlines()
    assert len(acct)==1
    job,state,elapsed,tres,start,end,*_=acct[0].split('|')
    assert job=='19136' and state=='FAILED' and 'gres/gpu=6' in tres.split(',')
    result=dict(job=job,node='gpu3',state=state,start_hk=start,end_hk=end,elapsed_seconds=int(elapsed),gpus=6,
        gpu_seconds=int(elapsed)*6,gpu_hours=int(elapsed)*6/3600,assigned=32,complete=31,rows=rows,blocks=blocks,
        service_cleanup=read(ROOT/'block-0/service-cleanup.json'),controller_error=error(closed['error']),
        source_commit=plan['source_commit'],plan_sha256=PIN,original_readout_hashes=before,
        original_success_gate_met=False,quality_comparison_valid=False,automatic_retry=False,
        limitation='Intervention metadata can pass while the complete32 quality contrast remains invalid. Missing outcome is not imputed; no patch/rerun or filtered comparison.')
    assert result['gpu_seconds']==summary['gpu_seconds']
    write('closure.json',result)
    for name in ('summary.json','runs.json','effort.json'):write(name,read(prior/name))
    with (out/'runs.csv').open('xb') as f:f.write((prior/'runs.csv').read_bytes())
    assert before=={p.name:sha(p) for p in prior.iterdir() if p.is_file()}
    manifest=dict(directory=str(out),files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(out.iterdir())})
    write('remote-manifest.json',manifest)
    print(json.dumps(dict(directory=str(out),assigned=32,complete=31,gpu_seconds=result['gpu_seconds'],gpu_hours=result['gpu_hours'],
        failed=[r for r in rows if not r['complete']],blocks=blocks,service_cleanup=result['service_cleanup'],files=manifest['files']),sort_keys=True))

if __name__=='__main__':main()
