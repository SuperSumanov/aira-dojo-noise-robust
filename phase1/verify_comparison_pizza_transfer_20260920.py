"""Independent closed-source/pair enumeration; never imports primary reader."""
import argparse,csv,hashlib,json,math
from pathlib import Path

def verify(summary,prepared):
    rows=summary['rows'];originals=prepared['rows']
    if len(rows)!=12 or len(originals)!=12 or len({r['node'] for r in rows})!=12 or {r['seed'] for r in rows}!={3,4}:raise ValueError('fixed twelve source nodes')
    for r,o in zip(rows,originals):
        if any(r[k]!=v for k,v in o.items()):raise ValueError('source identity')
        if r['valid'] is not (r['score'] is not None):raise ValueError('validity consistency')
        if r['valid'] and (r['exit_code']!=0 or r['timed_out'] or not 0<=r['score']<=1 or round(r['independent_score'],5)!=r['score']):raise ValueError('official independent score')
    for name,want in [('valid',True),('invalid',False),('unknown',None)]:
        if summary[name]!=sum(r['valid'] is want for r in rows):raise ValueError('aggregate coverage')
    for seed in (3,4):
        group=[r for r in rows if r['seed']==seed];pool,=[p for p in summary['pools'] if p['seed']==seed]
        if sorted(r['slot'] for r in group)!=list(range(6)):raise ValueError('complete slots')
        position={a['slot']:sum(b['reward']>a['reward'] or b['reward']==a['reward'] and b['slot']<a['slot'] for b in group) for a in group}
        if any(position[slot]!=i for i,slot in enumerate(pool['critic_order'])) or pool['valid_candidates']!=sum(r['valid'] for r in group):raise ValueError('ranking/coverage')
        pairs=[(a,b) for a in group for b in group if a['slot']<b['slot']]
        def value(pair):return max([r['score'] for r in pair if r['valid']] or [-math.inf])
        policies={'uniform_two_of_six':pairs,'frozen_top_two':[p for p in pairs if all(position[r['slot']]<2 for r in p)],'frozen_top_three_then_uniform_two':[p for p in pairs if all(position[r['slot']]<3 for r in p)]}
        for name,choices in policies.items():
            values=[value(p) for p in choices];valid=[v for v in values if v!=-math.inf]
            signs=[int(v>value(p))-int(v<value(p)) for v in values for p in pairs]
            calculated=dict(choices=len(choices),probability_any_valid=len(valid)/len(values),mean_oracle_auc_given_valid=sum(valid)/len(valid) if valid else None,
                wins=sum(x==1 for x in signs),ties=sum(x==0 for x in signs),losses=sum(x==-1 for x in signs),net_preference=sum(signs)/len(signs))
            if set(calculated)!=set(pool['policies'][name]):raise ValueError('policy schema')
            for key,v in calculated.items():
                got=pool['policies'][name][key]
                if (got is not v) if v is None else not math.isclose(v,got,abs_tol=1e-12,rel_tol=1e-12):raise ValueError('independent policy arithmetic')
    if not math.isclose(summary['gpu_hours'],summary['allocation_seconds']*6/3600) or any(summary[k] is not False for k in ('full_e2e','independent_confirmation','final_native_selection_tested','training')):raise ValueError('cost or claim scope')
    return dict(status='PASS',programs=12,pools=2,checks=['source identity','complete pool including failures','independent pair enumeration','higher AUC orientation','official independent score roundtrip','GPU accounting','no native-final/E2E claim'])

def main(root,out):
    expected={'summary.json':'ad70928f46866ed7555c8095066371a35fd52d82f54ae1735b7e9266bff7f988','prepared.json':'e8fb83fe8caa2d3d451dec6fb904574e7cd5b5490263b4ed2f480ee1d06c08f4','runs.csv':'3afc883e672d3100bea25f5542e20af52848c7365e1a67bc09f1f8fb810222ba'}
    for name,digest in expected.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('closed artifact drift')
    s=json.loads((root/'summary.json').read_bytes());p=json.loads((root/'prepared.json').read_bytes());result=verify(s,p)
    with (root/'runs.csv').open(newline='') as f:csvrows=list(csv.DictReader(f))
    if len(csvrows)!=12:raise ValueError('CSV population')
    for a,b in zip(s['rows'],csvrows):
        if set(a)!=set(b) or any(('' if v is None else str(v))!=b[k] for k,v in a.items()):raise ValueError('CSV fidelity')
    result['artifacts']=expected
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root',type=Path);a.add_argument('output',type=Path);args=a.parse_args();main(args.root,args.output)
