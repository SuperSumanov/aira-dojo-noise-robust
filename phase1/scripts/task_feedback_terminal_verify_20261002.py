"""Separate implementation: check two immutable censuses and live scheduler state."""
import argparse,hashlib,json,os,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-evidence-edit-20261002-v1')
PLAN='5ef4fa98529f70662cadf14e3f9a4ec4427c823d4a9fd723c9b6c25dd6806814'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def verify(a,b):
    x,y=load(a),load(b);assert digest(a)!=digest(b)
    assert datetime.fromisoformat(y['utc'])>datetime.fromisoformat(x['utc'])
    assert x['artifact_bindings']==y['artifact_bindings'] and x['episodes']==y['episodes']
    assert digest(ROOT/'plan.json')==x['plan_sha256']==y['plan_sha256']==PLAN
    for rel,h in x['artifact_bindings'].items():assert digest(ROOT/rel)==h
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    lines=subprocess.check_output(['sacct','-j','15213','-n','-P','-o','JobIDRaw,State,ElapsedRaw,NodeList'],env=env,text=True,timeout=25).splitlines()
    records={p[0]:p[1:4] for line in lines if len(p:=line.split('|'))>=4}
    assert records['15213']==['FAILED','2229','gpu28']
    assert len(records)==16
    for row in y['episodes']:
        q=records[row['step']];assert q[0].split()[0] in ('COMPLETED','CANCELLED') and q[2]=='gpu28'
        assert int(q[1])==row['elapsed_seconds']
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25)
    assert '15213' not in queue.splitlines()
    assert load(ROOT/'closed.json')['service_closed'] is True
    missing=[i for i in range(12) if not (ROOT/f'episode-{i}/closed.json').exists()]
    assert missing==[10] and not (ROOT/'all-closed.json').exists()
    assert not list((ROOT/'episode-10').glob('action-*'))
    assert all((ROOT/f'episode-{i}/native.json').exists() for i in range(12))
    return dict(status='INDEPENDENT_TERMINAL_VERIFIED_ORIGINAL_PRIMARY_FAILED',utc=datetime.now(timezone.utc).isoformat(),
        job='15213',plan_sha256=PLAN,original_primary_gate_passed=False,stable_censuses=2,
        census_sha256=[digest(a),digest(b)],missing_original_closed=missing,
        artifact_bindings=y['artifact_bindings'],scope='failed batch, lifecycle closure only; no imputation or successful experiment certification')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('first',type=Path);p.add_argument('second',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=verify(a.first,a.second)
    with a.out.open('x') as f:json.dump(r,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in r.items() if k!='artifact_bindings'},sort_keys=True));print('certificate_sha256='+digest(a.out))
