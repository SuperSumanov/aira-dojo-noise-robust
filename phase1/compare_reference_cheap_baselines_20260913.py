"""Apply already recorded cheap orders to the fully closed finite pools."""
import json
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha
from readout_branching_completion_20260913 import compare

ROOT=Path('/research/d7/spc/yzyang4/forets-pool-completion-20260912-n3c3ijtb')


def main():
    result=read(ROOT/'completion-summary.json');orders=read(ROOT/'cheap-comparators.json')
    if result['attempted']!=9 or not result['execution_complete']:raise ValueError('complete matrix only')
    rows=[]
    for p in result['pools']:
        saved=[r for r in orders['rows'] if r['parent_run_id']==p['parent_run_id']]
        if len(saved)!=1:raise ValueError('all pool order binding')
        row=saved[0]
        if row['code_sha256']!=[r['code_sha256'] for r in p['rows']]:raise ValueError('different candidates')
        rows.append(dict(task=p['task'],seed=p['seed'],parent_run_id=p['parent_run_id'],
            critic=dict(top2=p['top2'],gain_bounds=p['any_valid_gain_bounds']),
            parent_distance=compare(p['rows'],row['parent_distance_order']),
            code_length=compare(p['rows'],row['code_length_order'])))
    out=dict(role='exploratory_finite_pool_comparators_not_e2e',rows=rows,
        completion_sha256=sha((ROOT/'completion-summary.json').read_bytes()),orders_sha256=sha((ROOT/'cheap-comparators.json').read_bytes()),
        script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Cheap order designed after parent e2e outcomes, before new completion readout. No selection/tuning after new outcomes. Four pools and one unresolved original; no significance/novelty/general superiority claim.')
    print(json.dumps(dict(sha256=write(ROOT/'cheap-comparison.json',encode(out)),rows=rows)))


if __name__=='__main__':main()
