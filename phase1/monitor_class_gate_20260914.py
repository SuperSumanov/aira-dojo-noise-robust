"""Operational-only monitor; no scores, candidate identities or predictions."""
from contextlib import closing
import datetime as dt,json,os,re,sqlite3,subprocess,time
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-9uosb6me')
def read(p):return json.loads(p.read_bytes())
def snapshot():
    blocks=[]
    for block in (1,):
        start=ROOT/f'block-{block}.runtime/started.json'
        if not start.exists():blocks.append(dict(block=block,status='not_started'));continue
        pool=read(ROOT/read(start)['pool_manifest']);rows=[]
        for rid,task in pool['tasks'].items():
            row=dict(run_id=rid,status=task['status'],attempt=task['attempt'])
            if task['attempts']:
                identity=Path(task['attempts'][0]['identity_path']);summary=identity.with_suffix('.bounded')/'execution/summary.json'
                row['native_bindings']=len(list(identity.parent.glob(identity.name+'.native-binding-*.json')))
                if summary.exists():
                    closed=read(summary);row.update(termination=closed['status'],elapsed_seconds=closed['elapsed_seconds'])
                    if closed['status']=='failed':
                        log=summary.parent/'stderr.private.log'
                        with log.open('rb') as f:f.seek(max(0,log.stat().st_size-4096));tail=f.read().rstrip()
                        for suffix,name in [(b'SearchBudgetExpired: insufficient search time for a bounded API request','api_admission_budget_expired'),(b'RunBudgetError: run adapter-attempt budget exhausted','adapter_attempt_budget_expired')]:
                            if tail.endswith(suffix):row['termination']=name
                        if row['termination']=='failed':
                            last=tail.splitlines()[-1].decode(errors='replace') if tail else ''
                            match=re.match(r'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Stopped)):',last)
                            row['exception_type']=match[1] if match else 'unclassified'
            rows.append(row)
        blocks.append(dict(block=block,job=pool['allocation_id'],runs=rows))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        total=db.execute('SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)),SUM(state="unresolved") FROM calls').fetchone();stopped=db.execute('SELECT stopped FROM auth').fetchone()[0]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-j','13311','-h','-o','%i|%T|%M|%N'],env=env,text=True,timeout=25).strip().splitlines()
    acct=subprocess.check_output(['sacct','-X','-j','13311','-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList'],env=env,text=True,timeout=25).strip().splitlines()
    return dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),blocks=blocks,billing=dict(calls=total[0],held_nusd=total[1],settled_nusd=total[2],unresolved=total[3],stopped=bool(stopped)),queue=queue,accounting=acct)
if __name__=='__main__':print(json.dumps(snapshot()))
