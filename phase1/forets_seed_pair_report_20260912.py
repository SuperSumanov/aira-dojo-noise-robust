"""Combine fully closed, independently checked seed11/12 DEVELOPMENT blocks.

All four task/seed pairs stay visible. Missing finals are neither zero nor ties.
This module reads only completed public receipts, never an active run directory.
"""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics

TASKS=('leaf-classification','spaceship-titanic')
BINDINGS={11:('13115','6ca01fba9892a350cbb24152054b5296dc7095f1'),
          12:('13118','35711518b3b7262bccd3bebfdd2b4a4b7c726715')}


def aggregate(blocks):
    by_seed={}
    for block in blocks:
        if block['verification']!='selected-node/external-grade consistency passed':raise ValueError('not independently checked')
        rows=block['rows'];seeds={r['seed'] for r in rows}
        if len(rows)!=4 or len(seeds)!=1:raise ValueError('whole seed block required')
        seed=seeds.pop()
        if seed not in BINDINGS or (block['job'],block['source_tree'])!=BINDINGS[seed] or seed in by_seed:
            raise ValueError('wrong or duplicate block')
        keys=[(r['task'],r['arm']) for r in rows]
        if set(keys)!={(t,a) for t in TASKS for a in ('uniform_random','critic_topk_random')} or len(set(keys))!=4:
            raise ValueError('task/arm scope changed')
        for row in rows:
            valid=row['comparable_final'];score=row['external_final_score']
            if type(valid) is not bool or (not valid and score is not None):raise ValueError('missing score imputed')
            if valid and (type(score) not in (int,float) or not math.isfinite(score) or score<0
                          or (row['task']==TASKS[1] and score>1)):raise ValueError('bad score')
        by_seed[seed]={k:r for k,r in zip(keys,rows)}
    if set(by_seed)!={11,12}:raise ValueError('both complete seeds required')
    pairs=[]
    for task in TASKS:
        for seed in (11,12):
            r=by_seed[seed][task,'uniform_random'];c=by_seed[seed][task,'critic_topk_random']
            state=('both_valid' if r['comparable_final'] and c['comparable_final'] else
                   'random_only_valid' if r['comparable_final'] else
                   'critic_only_valid' if c['comparable_final'] else 'neither_valid')
            delta=None
            if state=='both_valid':
                delta=Decimal(str(c['external_final_score']))-Decimal(str(r['external_final_score']))
                if task==TASKS[0]:delta=-delta
            pairs.append(dict(task=task,seed=seed,status=state,random_score=r['external_final_score'],
                critic_score=c['external_final_score'],signed_critic_improvement=str(delta) if delta is not None else None,
                accuracy_improvement_percentage_points=str(delta*100) if delta is not None and task==TASKS[1] else None,
                metric='logloss' if task==TASKS[0] else 'accuracy',higher_signed_delta_is_better=True))
    summaries=[]
    for task in TASKS:
        group=[p for p in pairs if p['task']==task]
        values=[Decimal(p['signed_critic_improvement']) for p in group if p['signed_critic_improvement'] is not None]
        summaries.append(dict(task=task,planned_seed_pairs=2,comparable_seed_pairs=len(values),
            critic_only_valid=sum(p['status']=='critic_only_valid' for p in group),
            random_only_valid=sum(p['status']=='random_only_valid' for p in group),
            neither_valid=sum(p['status']=='neither_valid' for p in group),
            conditional_median_improvement=str(statistics.median(values)) if values else None,
            conditional_sample_variance=str(statistics.variance(values)) if len(values)>1 else None,
            positive_seed_pairs=sum(v>0 for v in values),negative_seed_pairs=sum(v<0 for v in values)))
    return dict(role='two_seed_development_comparison_not_confirmation',pairs=pairs,tasks=summaries,
        limitations=['Final-score contrast is not sufficient evidence of critic attribution; read selector/code contrast too.',
                    'No pooled mean across different task metrics. Missing finals are not zeros or ties.',
                    'Two seeds and two tasks cannot establish stable generalization or clean scaling.',
                    'Same configured budgets, not identical realized generation draws or resource usage.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('receipts',type=Path,nargs=2);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=aggregate([json.loads(p.read_text()) for p in args.receipts])
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps(report))
