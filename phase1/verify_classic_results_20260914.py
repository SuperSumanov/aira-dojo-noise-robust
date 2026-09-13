"""Independent numeric and whole-matrix check after the classic search closes."""
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import statistics
import sys
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-classic-control-20260914-6jkjkwd5')


def run():
    closed=read(ROOT/'readout-finished.json')
    summary=read(ROOT/'summary.json',closed['summary_sha256'])
    data=(ROOT/'runs.csv').read_bytes()
    if sha(data)!=closed['csv_sha256']:raise ValueError('CSV drift')
    rows=summary['rows'];csvrows=list(csv.DictReader(io.StringIO(data.decode())))
    expected={(t,s) for t in ('leaf-classification','spaceship-titanic') for s in range(42,46)}
    if len(rows)!=8 or len(csvrows)!=8 or {(r['task'],r['seed']) for r in rows}!=expected:raise ValueError('matrix')
    sys.path[:0]=[str(ROOT),str(ROOT.parent/'forets-wallclock-20260912-88v5m9dr/source/src')]
    from mlebench.registry import registry
    from readout_forets_generation_capacity_20260912 import numerical
    import pandas as pd
    registry=registry.set_data_dir(ROOT.parent/'mle-bench-data');answers={};trial_counts=Counter();checked=[]
    for r,c in zip(rows,csvrows):
        for k,v in r.items():
            if c[k]!=('' if v is None else str(v)):raise ValueError('CSV value mismatch')
        if r['api_cost_usd']!=0 or r['budget_seconds']!=1200:raise ValueError('budget/zero-API record')
        work=ROOT/f"work-{r['index']}";result=read(ROOT/f"result-{r['index']}.json")
        if result['status']=='completed':
            finish=read(work/'classic-finished.json',result['finished_sha256'])
            trial_counts.update(a['status'] for a in finish['rows'])
        if r['valid'] is True:
            p=work/'classic-incumbents'/f"trial-{r['selected_index']:03d}.csv"
            if sha(p.read_bytes())!=r['submission_sha256']:raise ValueError('selected file')
            if r['task'] not in answers:answers[r['task']]=pd.read_csv(registry.get_competition(r['task']).answers)
            score=numerical(r['task'],pd.read_csv(p),answers[r['task']])
            if not math.isfinite(score) or round(score,5)!=round(r['score'],5):raise ValueError('independent numeric grade')
            checked.append(dict(index=r['index'],task=r['task'],seed=r['seed'],score=r['score'],independent_score=score,
                submission_sha256=r['submission_sha256']))
    for group in summary['groups']:
        values=[r['score'] for r in rows if r['task']==group['task'] and r['valid'] is True]
        if (len(values),statistics.median(values) if values else None,statistics.stdev(values) if len(values)>1 else None)!=(group['valid'],group['median'],group['sd']):
            raise ValueError('aggregate mismatch')
    out=dict(status='INDEPENDENT_NUMERIC_CSV_AND_MATRIX_PASS',rows=len(rows),numeric_regrades=len(checked),
        trial_status_counts=dict(trial_counts),total_trial_attempts=sum(trial_counts.values()),
        scores=checked,groups=summary['groups'],allocation_gpu_hours=summary['allocation_gpu_hours'],
        summary_sha256=closed['summary_sha256'],csv_sha256=closed['csv_sha256'],script_sha256=sha(Path(__file__).read_bytes()),
        limitation='No agent comparison until its full matrix closes. Traditional reference is not a novel method or AutoGluon replication.')
    print(json.dumps(dict(sha256=write(ROOT/'independent-results.json',encode(out)),**out)))


if __name__=='__main__':run()
