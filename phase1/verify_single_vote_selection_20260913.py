"""Supplementary independent selector replay after both search blocks close.

Reads only this new, explicitly disclosed development package. No model or
program execution and no scores for the unexecuted alternatives are inferred.
"""
import json
from pathlib import Path
import sqlite3
from forets_environment_build_20260912 import read,sha,write,encode
from verify_forets_review_selection_20260912 import replay,code_contrast

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')
PREPARED='29349e0d78ce57701db2d5eae8bc35648f1fa50165df5eaff17a6502b3e402fe'

def verify_pool(value,cfg,row,rank_input=None,rank_finished=None):
    binding=value['binding'];candidates=value['candidates'];n=len(candidates)
    if (binding['task'],binding['selection_policy'],binding['selection_coupling'])!=(row['task'],row['arm'],'common_priority_v1'):
        raise ValueError('wrong task/policy/coupling')
    if (cfg['critic_top_k'],cfg['num_children_to_choose'],cfg['selector_seed'])!=(2,1,row['seed']):raise ValueError('selector config')
    selected=value['selected'];calls=value['task_calls']
    if selected is None:
        if calls or value['phase'] not in ('collecting','selected'):raise ValueError('unselected pool executed')
        return dict(selected=False,phase=value['phase'],candidate_executions=0)
    scores=[c['score'] for c in candidates]
    bypass=cfg['skip_redundant_critic'] and row['arm']=='critic_topk_random' and n<=2
    if bypass!=(binding.get('score_bypass')=='full_pool_no_pruning'):raise ValueError('bypass')
    effective='uniform_random' if bypass else row['arm']
    if effective=='uniform_random':
        if any(s is not None for s in scores) or rank_input is not None:raise ValueError('control unexpectedly ranked')
    else:
        if rank_input is None or rank_finished is None:raise ValueError('selection before full ranking')
        if rank_input['codes_sha256']!=[sha(c['node']['code'].encode()) for c in candidates]:raise ValueError('ranked other programs')
        if rank_finished['borda']!=scores or rank_input['aggregation']!='single_order_rank_v1':raise ValueError('scores/aggregation')
    expected=replay(n,scores,effective,'common_priority_v1',row['seed'],row['task'],binding['step'])
    if selected!=expected:raise ValueError('selected slot differs from independent replay')
    originals=[c for c in calls if c['intent']['role']=='candidate']
    if len(originals)>1 or any(c['slot']!=expected[0] for c in calls):raise ValueError('wrong candidate/debug lineage executed')
    if calls and (calls[0]['intent']['role']!='candidate' or not originals):raise ValueError('debug before candidate')
    if value['phase']=='complete' and len(originals)!=1:raise ValueError('complete selection did not execute')
    uniform=replay(n,None,'uniform_random','common_priority_v1',row['seed'],row['task'],binding['step'])
    codes=[c['node']['code'] for c in candidates]
    return dict(selected=True,phase=value['phase'],candidate_executions=len(originals),
        candidate_execution_returned=bool(originals and originals[0]['state']=='returned'),
        replay_matches=True,ranking_bypassed=bypass,
        differs_from_same_pool_uniform=(selected!=uniform) if effective!='uniform_random' else None,
        **code_contrast(codes,selected[0],uniform[0]))

def run():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('wait for all eight and independent readout')
    read(ROOT/'wallclock-summary.json',finish['summary_sha256'])
    prepared=read(ROOT/'prepared.json',PREPARED);rows=[]
    plan=read(ROOT/'selection-check-plan.json')
    helper=Path(__file__).with_name('verify_forets_review_selection_20260912.py')
    if plan['verifier_sha256']!=sha(Path(__file__).read_bytes()) or plan['helper_sha256']!=sha(helper.read_bytes()):raise ValueError('supplement source drift')
    for row in prepared['run_configs']:
        cfg=read(ROOT/'configs'/(row['run_id']+'.json'),row['config_sha256'])['solver']
        checkpoint=Path(cfg['checkpoint_path'])
        if not checkpoint.resolve().is_relative_to(ROOT):raise ValueError('foreign checkpoint')
        for path in sorted((checkpoint/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(path.read_bytes())
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                data=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
            if len(data)!=1 or sha(data[0][0].encode())!=data[0][1]:raise ValueError('snapshot hash')
            value=json.loads(data[0][0]);step=value['binding']['step']
            rank=checkpoint/'forets-contextual-judge-private'/f'batch-{step}'
            inp=read(rank/'input.json') if (rank/'input.json').exists() else None
            done=read(rank/'finished.json') if (rank/'finished.json').exists() else None
            checked=verify_pool(value,cfg,row,inp,done)
            if sha(path.read_bytes())!=before:raise ValueError('concurrent writer after closeout')
            rows.append(dict(run_id=row['run_id'],task=row['task'],seed=row['seed'],arm=row['arm'],step=step,
                ledger_sha256=before,**checked))
    result=dict(rows=rows,summary_sha256=finish['summary_sha256'],verifier_sha256=plan['verifier_sha256'],
        scope='intervention actually applied, not counterfactual outcome or utility',
        stopped_or_unselected_pools_preserved=True,agent_calls=0,program_executions=0)
    write(ROOT/'singlevote-selection-verification.json',encode(result));print(json.dumps(dict(pools=len(rows),selected=sum(r['selected'] for r in rows))))

if __name__=='__main__':run()
