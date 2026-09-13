"""Independent local check of exported JSON/CSV pairs and summary arithmetic."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

def close(a,b):
    if a is None or b is None:
        if a is not b:raise ValueError('missing summary statistic')
    elif not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('statistic differs')

def validate(path,kind):
    prefix={'action':'action-delivery','width':'width','memory':'memory'}[kind]
    finish=json.loads((path/'readout-finished.json').read_bytes())
    for name,digest in finish['files'].items():
        if hashlib.sha256((path/name).read_bytes()).hexdigest()!=digest:raise ValueError('export bytes differ from remote closure')
    value=json.loads((path/(prefix+'-summary.json')).read_bytes());rows=value['rows']
    with (path/(prefix+'-runs.csv')).open(newline='') as f:csvrows=list(csv.DictReader(f))
    if len(rows)!=8 or len(csvrows)!=8:raise ValueError('all runs required')
    if len({r['run_id'] for r in rows})!=8:raise ValueError('duplicate run')
    for r,c in zip(rows,csvrows):
        if set(r)!=set(c) or any(c[k] != ('' if v is None else str(v)) for k,v in r.items()):raise ValueError('CSV and JSON differ')
    tasks=('leaf-classification','spaceship-titanic')
    groups=[]
    if kind=='action':
        if {(r['task'],r['seed']) for r in rows}!={(t,s) for t in tasks for s in (34,35,36,37)}:raise ValueError('action matrix')
        for task in tasks:
            gains=[]
            for r in rows:
                if r['task']!=task:continue
                valid=r['technical_eligible'] and r['primary_valid'] and r['action_valid']
                gain=((r['primary_score']-r['action_score']) if task==tasks[0] else (r['action_score']-r['primary_score'])) if valid else None
                if r['quality_comparable']!=valid:raise ValueError('action eligibility')
                close(gain,r['action_oriented_gain'])
                if gain is not None:gains.append(gain)
            groups.append((next(g for g in value['groups'] if g['task']==task),gains))
    else:
        seeds,arms,gain_key=((38,39),('batch_four','direct_two'),'direct_oriented_gain') if kind=='width' else ((40,41),('no_memory','execution_memory'),'memory_oriented_gain')
        if {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in tasks for s in seeds for a in arms}:raise ValueError('exact contrast matrix')
        if value['primary_endpoint']!='action' or value['secondary_endpoint']!='iteration':raise ValueError('endpoint switching')
        for endpoint in ('action','iteration'):
            for task in tasks:
                gains=[]
                for seed in seeds:
                    a,b=[next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm)) for arm in arms]
                    valid=a['technical_eligible'] and b['technical_eligible'] and a[endpoint+'_valid'] and b[endpoint+'_valid']
                    gain=((a[endpoint+'_score']-b[endpoint+'_score']) if task==tasks[0] else (b[endpoint+'_score']-a[endpoint+'_score'])) if valid else None
                    pair=next(p for p in value['pairs'] if (p['endpoint'],p['task'],p['seed'])==(endpoint,task,seed))
                    if pair['quality_comparable']!=valid:raise ValueError('width eligibility')
                    close(gain,pair[gain_key])
                    if gain is not None:gains.append(gain)
                groups.append((next(g for g in value['groups'] if (g['endpoint'],g['task'])==(endpoint,task)),gains))
    for group,gains in groups:
        if (group['quality_comparable'],group['wins'],group['ties'],group['losses'])!=(len(gains),sum(v>0 for v in gains),sum(v==0 for v in gains),sum(v<0 for v in gains)):
            raise ValueError('gain counts')
        close(group['median_gain'],statistics.median(gains) if gains else None)
        close(group['sample_std_gain'],statistics.stdev(gains) if len(gains)>1 else None)
    return dict(status='EXPORT_BYTES_CSV_AND_INDEPENDENT_ARITHMETIC_VERIFIED',kind=kind,runs=len(rows),groups=len(groups),
        closure_sha256=hashlib.sha256((path/'readout-finished.json').read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('action','width','memory'));p.add_argument('directory',type=Path);a=p.parse_args()
    print(json.dumps(validate(a.directory,a.kind)))
