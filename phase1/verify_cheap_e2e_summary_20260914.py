"""After frozen readout only: independent CSV, effects, gate and model binding."""
import csv,json,math,statistics
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
ROOT=BASE/'forets-wallclock-20260912-km65uuej'
def sign(x):return (x>0)-(x<0)
def verify_effects(rows):
    if len(rows)!=12 or {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in ('leaf-classification','spaceship-titanic') for s in (46,47) for a in ('uniform','short_code','learned_validity')}:raise ValueError('matrix')
    for r in rows:
        for endpoint in ('action','iteration'):
            if type(r['technical_eligible']) is not bool or type(r[endpoint+'_valid']) is not bool:raise ValueError('qualification type')
            if r[endpoint+'_valid']:
                if type(r[endpoint+'_score']) not in (float,int) or not math.isfinite(r[endpoint+'_score']):raise ValueError('finite score')
            elif r[endpoint+'_score'] is not None:raise ValueError('unknown imputed')
    pairs=[]
    for endpoint in ('action','iteration'):
        for baseline in ('uniform','short_code'):
            for task in ('leaf-classification','spaceship-titanic'):
                for seed in (46,47):
                    learned=next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,'learned_validity'))
                    other=next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,baseline))
                    technical=learned['technical_eligible'] and other['technical_eligible'];gain=None;result=None
                    lv=learned[endpoint+'_valid'];ov=other[endpoint+'_valid']
                    if technical:
                        if lv and ov:
                            gain=(learned[endpoint+'_score']-other[endpoint+'_score'])*(-1 if task=='leaf-classification' else 1)
                            result=sign(gain)
                        else:result=int(lv)-int(ov)
                    pairs.append(dict(endpoint=endpoint,baseline=baseline,task=task,seed=seed,technical_comparable=technical,
                        baseline_valid=ov,learned_valid=lv,gain=gain,sign=result))
    primary=[p for p in pairs if p['endpoint']=='action'];by= {(b,t):[p for p in primary if (p['baseline'],p['task'])==(b,t)] for b in ('uniform','short_code') for t in ('leaf-classification','spaceship-titanic')}
    gate=all(r['technical_eligible'] for r in rows) and all(sum(p['sign'] or 0 for p in v)>=0 for v in by.values()) and all(sum(p['sign'] or 0 for p in primary if p['baseline']==b)>0 for b in ('uniform','short_code'))
    return pairs,gate
def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('frozen full readout first')
    for n,h in finish['files'].items():checked(ROOT/n,h)
    s=read(ROOT/'cheap-selector-summary.json',finish['summary_sha256']);base=read(ROOT/'wallclock-summary.json')
    pairs,gate=verify_effects(s['rows'])
    if pairs!=s['pairs'] or gate!=s['investment_gate']:raise ValueError('paired arithmetic or gate')
    for g in s['groups']:
        rr=[p for p in pairs if (p['endpoint'],p['baseline'],p['task'])==(g['endpoint'],g['baseline'],g['task'])]
        for name,k in (('wins',1),('ties',0),('losses',-1),('unknown',None)):
            if sum(p['sign']==k for p in rr)!=g[name]:raise ValueError('group signs')
        values=[p['gain'] for p in rr if p['gain'] is not None]
        for name,value in (('median_gain',statistics.median(values) if values else None),('sample_sd_gain',statistics.stdev(values) if len(values)>1 else None)):
            target=g[name]
            if (value is None)!=(target is None) or (value is not None and abs(value-target)>1e-12):raise ValueError('group dispersion')
    with (ROOT/'cheap-selector-runs.csv').open(newline='') as f:csvrows=list(csv.DictReader(f))
    if len(csvrows)!=12:raise ValueError('CSV complete')
    for r,c in zip(s['rows'],csvrows):
        if set(r)!=set(c) or any(c[k]!=('' if value is None else str(value)) for k,value in r.items()):raise ValueError('CSV JSON agreement')
        if (r['node'],r['allocated_gpus'],r['allocated_cpus'],r['program_timeout_seconds'],r['search_budget_seconds'],r['selection_top_k'])!=('gpu28',1,6,300,600,1):raise ValueError('hardware budget declaration')
    if not base['same_physical_gpu_within_each_block'] or s['allocation_gpu_hours']!=base['allocation_seconds']/3600:raise ValueError('native hardware accounting')
    model=BASE/'forets-task-validity-20260914-n8q3h72y/code_only.private.joblib'
    if sha(model.read_bytes())!='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1':raise ValueError('model change')
    out=dict(status='independent_full_matrix_csv_effects_dispersion_gate_hardware_and_fixed_model_verified',summary_sha256=finish['summary_sha256'],
        rows=12,technical_eligible=sum(r['technical_eligible'] for r in s['rows']),paired_comparisons=len(pairs),investment_gate=gate,
        script_sha256=sha(Path(__file__).read_bytes()),limitation='Independent arithmetic/CSV and prior native/numeric evidence binding; not a second execution, statistical confirmation or interference-free guarantee.')
    raw=(json.dumps(out,sort_keys=True)+'\n').encode()
    with (ROOT/'cheap-selector-independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**out)))
if __name__=='__main__':main()
