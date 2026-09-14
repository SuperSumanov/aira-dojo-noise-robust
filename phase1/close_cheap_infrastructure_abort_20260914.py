"""Prove the cancelled attempt ended before any sampled proposal or scoring."""
from contextlib import closing
import json,os,sqlite3,subprocess
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-q_imzdb_')
def main():
    os.umask(0o077);env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=[read(ROOT/f'launch-b{b}.json')['job'] for b in (1,2)]
    queue=subprocess.check_output(['squeue','-j',','.join(jobs),'-h','-o','%i'],env=env,text=True,timeout=25)
    if queue.strip():raise ValueError('allocations not closed')
    acct=subprocess.check_output(['sacct','-X','-j',','.join(jobs),'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList'],env=env,text=True,timeout=25).strip().splitlines()
    if len(acct)!=2 or any('CANCELLED' not in x for x in acct):raise ValueError('expected explicit abort')
    proof=[];generated=0;scored=0
    prepared=read(ROOT/'prepared.json')
    runids={r['run_id'] for r in prepared['run_configs']}
    for r in prepared['run_configs']:
        cfg=read(ROOT/'configs'/(r['run_id']+'.json'),r['config_sha256']);cp=Path(cfg['solver']['checkpoint_path'])
        for p in (cp/'forets-candidates-private').glob('batch-*.sqlite'):
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=h:raise ValueError('pool hash')
            v=json.loads(raw)
            if not v['binding'].get('common_start'):generated+=sum(c.get('node') is not None for c in v['candidates'])
            scored+=sum(c.get('score') is not None for c in v['candidates'])
            proof.append(dict(run_id=r['run_id'],file=p.name,sha256=sha(p.read_bytes()),common_start=bool(v['binding'].get('common_start'))))
        if list((cp/'forets-cheap-ranker-private').glob('*.json')) or list((cp/'forets-contextual-judge-private').glob('batch-*')):raise ValueError('selector called')
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        calls=db.execute('select * from calls order by id').fetchall()
    if any(r[1] in runids for r in calls) or generated or scored:raise ValueError('scientific proposal already happened; no automatic infrastructure restart')
    result=dict(status='ABORT_BEFORE_SAMPLED_PROPOSALS_OR_SELECTOR',root=str(ROOT),accounting=acct,
        allocation_seconds=sum(int(line.split('|')[2]) for line in acct),generated_candidates=generated,scored_candidates=scored,actual_search_api_calls=0,
        counts=[len(calls),sum(r[2] for r in calls),sum(r[3] or 0 for r in calls),sum(r[4]=='unresolved' for r in calls)],calls_sha256=sha(encode(calls)),
        reason='FreshContainerInterpreter expected integration fixed receipt; production adapter writes child-PID-suffixed receipt',
        all_original_planned_rows_retained=True,eligible_scientific_results=0,proof=proof,script_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(sha256=write(ROOT/'infrastructure-abort.json',encode(result)),**{k:v for k,v in result.items() if k!='proof'})))
if __name__=='__main__':main()
