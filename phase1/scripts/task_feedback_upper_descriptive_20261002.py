"""Descriptive complete denominator, including closed runs with worker exceptions.

Frozen primary readout remains unchanged. This supplementary saved-incumbent
view was added after an outcome-blind deadline/transport failure was observed.
It is not a replacement primary analysis and does not relabel unknown finishes.
"""
import argparse,json,statistics
from pathlib import Path
def stats(values):
    x=[v for v in values if v is not None]
    return {'n':len(x),'median':statistics.median(x) if x else None,
            'sample_variance':statistics.variance(x) if len(x)>1 else None,
            'values':values}
def summarize(data):
    assert data['planned']==18 and data['closed']==18, 'Complete experiment only'
    rows=data['rows'];groups=[];pairs=[]
    assert len(rows)==18
    for task in sorted({r['task'] for r in rows}):
        for arm in 'ABC':
            subset=sorted((r for r in rows if r['task']==task and r['arm']==arm),key=lambda r:r['seed'])
            assert len(subset)==3
            groups.append({'task':task,'arm':arm,'planned':3,'states':[r['status'] for r in subset],
                           'valid_saved_incumbents':sum(r['selected_metric'] is not None for r in subset),
                           'final':stats([r['selected_metric'] for r in subset]),
                           'own_initial_gain':stats([r['oriented_development_gain'] for r in subset]),
                           'generation_seconds':stats([r['completed_generator_seconds'] for r in subset])})
        for high,low in [('B','A'),('C','B'),('C','A')]:
            values=[];gains=[];states=[]
            for seed in sorted({r['seed'] for r in rows if r['task']==task}):
                z={r['arm']:r for r in rows if r['task']==task and r['seed']==seed};h,l=z[high],z[low]
                values.append(h['selected_metric']-l['selected_metric'] if h['selected_metric'] is not None and l['selected_metric'] is not None else None)
                gains.append(h['oriented_development_gain']-l['oriented_development_gain'] if h['oriented_development_gain'] is not None and l['oriented_development_gain'] is not None else None)
                states.append([h['status'],l['status']])
            pairs.append({'task':task,'contrast':high+'-'+low,'finish_states':states,
                          'saved_incumbent_difference':stats(values),'gain_difference':stats(gains)})
    return {'scope':'supplementary all-closed saved-incumbent description, not strict completed-run primary; no missing value imputation',
            'plan_sha256':data['plan_sha256'],'groups':groups,'pairs':pairs,
            'planned':18,'strict_original_comparisons':data['comparisons'],
            'independent_units_warning':'two task/code instances, three continuation seeds per task; no across-task significance claim'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=summarize(json.loads(a.input.read_bytes()))
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    print(json.dumps(result,sort_keys=True))
