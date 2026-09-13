"""Frozen whole-matrix readout, initial-program proof, and paired improvement."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import sqlite3
import statistics
import sys
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=TREE=PREPARED=None  # Exact identities come only from the frozen launch plan.
FILES=('readout_forets_branching_20260913.py','readout_forets_branching_core_20260913.py',
    'readout_forets_single_vote_20260913.py','readout_forets_generation_capacity_20260912.py',
    'attribute_forets_wallclock_20260912.py','verify_branching_selection_20260913.py',
    'verify_forets_review_selection_20260912.py')


def oriented(task,before,after):
    if task not in ('leaf-classification','spaceship-titanic'):raise ValueError('unregistered task')
    return before-after if task=='leaf-classification' else after-before


def run(root):
    global ROOT,TREE,PREPARED
    plan=read(root/'readout-plan.json')
    ROOT=Path(plan['root']);TREE=plan['source_tree'];PREPARED=plan['prepared_sha256']
    if ROOT.parent!=Path('/research/d7/spc/yzyang4') or not ROOT.name.startswith('forets-wallclock-20260912-'):raise ValueError('root boundary')
    if root.resolve(strict=True)!=ROOT:raise ValueError('exact frozen experiment')
    prepared=read(root/'prepared.json',PREPARED)
    if read(root/'build.json')['source_tree']!=TREE:raise ValueError('source')
    actual={f:sha(Path(__file__).with_name(f).read_bytes()) for f in FILES}
    plan=read(root/'readout-plan.json')
    if plan['readers']!=actual:raise ValueError('reader drift')
    write(root/'readout-intent.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),readers=actual)))
    from readout_forets_branching_core_20260913 import verify
    verify(root,seeds=(30,31),blocks=(1,2))
    import readout_forets_single_vote_20260913 as cost
    cost.TREE=TREE;cost.attribute(root)
    from verify_branching_selection_20260913 import verify_pool
    from dojo.solvers.fore_ts.common_start import canonical as code_for,digest
    from readout_forets_generation_capacity_20260912 import numerical
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(root.parent/'mle-bench-data')
    summary=read(root/'wallclock-summary.json');rows=[];selection=[];answers={}
    configs={r['run_id']:r for r in prepared['run_configs']}
    for r in summary['rows']:
        rid=r['run_id'];cfg=read(root/'configs'/(rid+'.json'),configs[rid]['config_sha256'])
        checkpoint=Path(cfg['solver']['checkpoint_path'])
        if not checkpoint.resolve().is_relative_to(root) or cfg['solver']['common_start_protocol']!='rf_common_v1':raise ValueError('config')
        first=None
        for path in sorted((checkpoint/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(path.read_bytes())
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                values=db.execute('select payload,sha256 from snapshot where id=1').fetchall()
            if len(values)!=1 or sha(values[0][0].encode())!=values[0][1]:raise ValueError('snapshot')
            value=json.loads(values[0][0]);step=value['binding']['step']
            rank=checkpoint/'forets-contextual-judge-private'/f'batch-{step}'
            inp=read(rank/'input.json') if (rank/'input.json').exists() else None
            done=read(rank/'finished.json') if (rank/'finished.json').exists() else None
            checked=verify_pool(value,cfg['solver'],r,inp,done)
            if step==1:
                first=value
                if (len(value['candidates'])!=1 or value['llm_requests'] or inp is not None or
                    value['binding']['common_start']!={'protocol':'rf_common_v1','code_sha256':digest(r['task'])}):
                    raise ValueError('not the fixed zero-generation/ranking first candidate')
                node=value['candidates'][0]['node']
                if node is not None and node['code']!=code_for(r['task']):raise ValueError('wrong starting code')
                if node is None and value['task_calls']:raise ValueError('execution without baseline node')
                if any(c['intent']['code_sha256']!=digest(r['task']) for c in value['task_calls'] if c['intent']['role']=='candidate'):
                    raise ValueError('wrong actually executed baseline')
            elif 'common_start' in value['binding']:
                raise ValueError('baseline reapplied after first step')
            if sha(path.read_bytes())!=before:raise ValueError('concurrent mutation')
            selection.append(dict(run_id=rid,step=step,ledger_sha256=before,**checked))
        baseline=None;baseline_seconds=None
        receipt_path=root/'incumbents'/rid/'step-000002.commit.json'
        if receipt_path.exists():
            commit=read(receipt_path);data=read(receipt_path.parent/commit['data_file'],commit['data_sha256'])
            receipt=data['submission']
            if commit['eligible'] and receipt is not None:
                if data['code']!=code_for(r['task']) or receipt['code_sha256']!=digest(r['task']):raise ValueError('wrong initial incumbent')
                archive=Path(receipt['archive_dir'])
                if archive.parent.resolve()!=(Path(cfg['task']['results_output_dir'])/'submission-escrow').resolve():raise ValueError('archive')
                complete=read(archive/'complete.json')
                if any(receipt.get(k)!=v for k,v in complete.items()):raise ValueError('archive receipt')
                report=read(archive/'report.json',receipt['report_sha256'])
                if sha((archive/'submission.csv').read_bytes())!=receipt['submission_sha256'] or report['valid_submission'] is not True:raise ValueError('baseline submission')
                task=r['task']
                if task not in answers:answers[task]=pd.read_csv(registry.get_competition(task).answers)
                exact=numerical(task,pd.read_csv(archive/'submission.csv'),answers[task])
                if round(exact,5)!=report['score']:raise ValueError('baseline numeric')
                baseline=report['score'];baseline_seconds=(commit['durable_ns']-data['start_ns'])/1e9
        if baseline is not None and (first is None or first['phase']!='complete' or len(first['task_calls'])!=1):
            raise ValueError('baseline was not one completed execution')
        gain=oriented(r['task'],baseline,r['score']) if baseline is not None and r['valid'] else None
        rows.append(dict(r,baseline_valid=baseline is not None,baseline_score=baseline,
            baseline_elapsed_seconds=baseline_seconds,baseline_code_sha256=digest(r['task']),improvement=gain))
    pairs=[]
    for task in ('leaf-classification','spaceship-titanic'):
        for seed in (30,31):
            a,b=[next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm)) for arm in ('uniform_random','critic_topk_random')]
            same=a['baseline_valid'] and b['baseline_valid'] and a['baseline_score']==b['baseline_score']
            qualified=same and a['technical_eligible'] and b['technical_eligible'] and a['valid'] and b['valid']
            pairs.append(dict(task=task,seed=seed,matched_valid_common_start=same,qualified=qualified,
                critic_minus_random_improvement=b['improvement']-a['improvement'] if qualified else None))
    gains=[]
    for task in ('leaf-classification','spaceship-titanic'):
        values=[r['critic_minus_random_improvement'] for r in pairs if r['task']==task and r['qualified']]
        gains.append(dict(task=task,qualified_seeds=len(values),median=statistics.median(values) if values else None,
            sample_std=statistics.stdev(values) if len(values)>1 else None))
    result=dict(role='common_start_development_not_cold_start_gain',source_tree=TREE,rows=rows,pairs=pairs,gain_summary=gains,
        selection=selection,summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),
        limitation='Common start costs charged to each arm. Small development sample. No significance, clean-scaling or novelty claim.')
    write(root/'common-start-summary.json',encode(result))
    with (root/'common-start-runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    finish=dict(status='verified',utc=dt.datetime.now(dt.timezone.utc).isoformat(),readers=actual,
        files={n:sha((root/n).read_bytes()) for n in ('wallclock-summary.json','wallclock-runs.csv','singlevote-attribution.json','common-start-summary.json','common-start-runs.csv')})
    write(root/'readout-finished.json',encode(finish));print(json.dumps(dict(pairs=pairs,gain_summary=gains,finish=finish)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
