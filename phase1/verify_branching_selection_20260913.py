"""Independent two-slot replay including execution order and debug lineage."""
import hashlib
import json
import math
import random


def replay(n, scores, policy, seed, task, step):
    if policy=='uniform_random':eligible=set(range(n))
    elif policy=='critic_topk_random':
        if len(scores)!=n or any(type(s) not in (int,float) or not math.isfinite(s) for s in scores):raise ValueError('scores')
        eligible=set(sorted(range(n),key=lambda i:(-scores[i],i))[:2])
    else:raise ValueError('policy')
    identity=dict(version='forets-common-priority-v1',seed=seed,task=task,step=step,purpose='selection_order')
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    order=list(range(n));random.Random(key).shuffle(order)
    return [i for i in order if i in eligible][:min(n,2)]


def verify_pool(value,cfg,row,rank_input=None,rank_finished=None):
    binding=value['binding'];candidates=value['candidates'];n=len(candidates)
    if (binding['task'],binding['selection_policy'],binding['selection_coupling'])!=(row['task'],row['arm'],'common_priority_v1'):raise ValueError('binding')
    if (cfg['critic_top_k'],cfg['num_children_to_choose'],cfg['selector_seed'])!=(2,2,row['seed']):raise ValueError('config')
    selected=value['selected'];calls=value['task_calls']
    if selected is None:
        if calls or value['phase'] not in ('collecting','selected'):raise ValueError('unselected executed')
        return dict(selected=False,phase=value['phase'],candidate_executions=0)
    scores=[c['score'] for c in candidates]
    bypass=cfg['skip_redundant_critic'] and row['arm']=='critic_topk_random' and n<=2
    if bypass!=(binding.get('score_bypass')=='full_pool_no_pruning'):raise ValueError('bypass')
    effective='uniform_random' if bypass else row['arm']
    if effective=='uniform_random':
        if any(s is not None for s in scores) or rank_input is not None:raise ValueError('control ranked')
    else:
        if rank_input is None or rank_finished is None:raise ValueError('rank incomplete')
        hashes=[hashlib.sha256(c['node']['code'].encode()).hexdigest() for c in candidates]
        if rank_input['codes_sha256']!=hashes or rank_finished['borda']!=scores or rank_input['aggregation']!='single_order_rank_v1':raise ValueError('rank binding')
    expected=replay(n,scores,effective,row['seed'],row['task'],binding['step'])
    if selected!=expected:raise ValueError('independent order mismatch')
    originals=[];last=None;previous=None
    for c in calls:
        if previous is not None and previous['state']!='returned':raise ValueError('call after unfinished call')
        if c['intent']['role']=='candidate':
            if len(originals)>=len(expected) or c['slot']!=expected[len(originals)]:raise ValueError('candidate order/duplicate')
            originals.append(c);last=c['slot']
            code=candidates[last]['node']['code']
            if c['intent']['code_sha256']!=hashlib.sha256(code.encode()).hexdigest():raise ValueError('executed different code')
        elif c['intent']['role']=='debug':
            if last is None or c['slot']!=last:raise ValueError('debug lineage')
        else:raise ValueError('role')
        previous=c
    if value['phase']=='complete' and (len(originals)!=len(expected) or any(c['state']!='returned' for c in calls)):raise ValueError('incomplete marked complete')
    uniform=replay(n,None,'uniform_random',row['seed'],row['task'],binding['step'])
    return dict(selected=True,phase=value['phase'],candidate_executions=len(originals),
        candidate_execution_returned=sum(c['state']=='returned' for c in originals),replay_matches=True,
        selected_width=len(selected),ranking_bypassed=bypass,
        differs_from_same_pool_uniform=selected!=uniform if effective!='uniform_random' else None)
