"""Final choice by native internal metric, never by external grade."""
import itertools, math, statistics

def number(value):
    return type(value) in (int,float) and math.isfinite(value)

def choices(rows):
    ordered=sorted(rows,key=lambda r:r['slot'])
    ranked=sorted(rows,key=lambda r:(-r['reward'],r['slot']))
    return {'uniform_two_of_six':list(itertools.combinations(ordered,2)),
            'frozen_top_two':[tuple(ranked[:2])],
            'frozen_top_three_then_uniform_two':list(itertools.combinations(ranked[:3],2))}

def select(pair,*,budget=None,query_seconds=0.,load_seconds=0.):
    elapsed=query_seconds+load_seconds;incumbent=None
    for row in pair:
        if budget is not None and elapsed>=budget:break
        elapsed+=row['wall_seconds']+row['analysis_seconds']
        if budget is not None and elapsed>budget:break
        if row['native_accepted']:
            if not number(row['native_metric']):raise ValueError('accepted finite internal metric')
            if incumbent is None or (row['native_metric'],row['slot'])<(incumbent['native_metric'],incumbent['slot']):incumbent=row
    # An invalid actual final submission is failure, not permission to replace it
    # with a lower-ranked candidate using the external evaluator.
    return dict(slot=None if incumbent is None else incumbent['slot'],
        valid=incumbent is not None and incumbent['valid'],
        score=incumbent['score'] if incumbent is not None and incumbent['valid'] else None,
        conditional_replay_seconds=elapsed if budget is None else min(elapsed,budget))

def compare(a,b):
    if not a['valid']:return 0 if not b['valid'] else -1
    if not b['valid']:return 1
    return (b['score']>a['score'])-(b['score']<a['score'])

def pool(rows,load_seconds):
    if len(rows)!=6 or sorted(r['slot'] for r in rows)!=list(range(6)) or len({r['node'] for r in rows})!=6:raise ValueError('complete six')
    for row in rows:
        if row['analysis_status']!='returned' or type(row['native_accepted']) is not bool:raise ValueError('unknown cannot be omitted')
        if type(row['valid']) is not bool or not number(row['reward']):raise ValueError('complete outcome/reward')
        if row['valid'] and not number(row['score']):raise ValueError('finite valid grade')
        for key in ('wall_seconds','analysis_seconds','inference_seconds'):
            if not number(row[key]) or row[key]<0:raise ValueError('finite cost')
    policies=choices(rows);query=sum(r['inference_seconds'] for r in rows)
    scenarios={}
    for scenario,budget,cold in [('two_evaluations',None,False),('replay_2100_warm',2100.,False),('replay_2100_cold',2100.,True)]:
        selected={}
        for name,pairs in policies.items():
            critic=name!='uniform_two_of_six'
            selected[name]=[select(pair,budget=budget,query_seconds=query if critic else 0.,load_seconds=load_seconds if critic and cold else 0.) for pair in pairs]
        baseline=selected['uniform_two_of_six'];out={}
        for name,values in selected.items():
            signs=[compare(a,b) for a in values for b in baseline]
            valid=[v['score'] for v in values if v['valid']]
            out[name]=dict(choices=len(values),probability_valid_final=len(valid)/len(values),
                mean_final_loss_given_valid=statistics.mean(valid) if valid else None,
                median_conditional_replay_seconds=statistics.median(v['conditional_replay_seconds'] for v in values),
                final_slots=[v['slot'] for v in values],final_losses=[v['score'] for v in values],
                wins=signs.count(1),ties=signs.count(0),losses=signs.count(-1),
                net_preference=statistics.mean(signs),comparisons=len(signs))
        scenarios[scenario]=out
    return dict(native_accepted=sum(r['native_accepted'] for r in rows),
        valid_accepted=sum(r['native_accepted'] and r['valid'] for r in rows),
        valid_rejected=sum(not r['native_accepted'] and r['valid'] for r in rows),
        invalid_accepted=sum(r['native_accepted'] and not r['valid'] for r in rows),
        critic_order=[r['slot'] for r in sorted(rows,key=lambda r:(-r['reward'],r['slot']))],
        all_six_critic_query_seconds=query,scenarios=scenarios)

def summarize(rows,load_seconds):
    expected={('leaf-classification',1),('leaf-classification',2),('leaf-classification',3),('spooky-author-identification',1),('spooky-author-identification',2)}
    groups={}
    for row in rows:groups.setdefault((row['task'],row['seed']),[]).append(row)
    if len(rows)!=30 or set(groups)!=expected or len({r['node'] for r in rows})!=30:raise ValueError('fixed five pools')
    unknown=[r['node'] for r in rows if r['analysis_status']!='returned']
    if unknown:return dict(status='INCOMPLETE_NO_POINT_EFFECT_CLAIM',unknown_count=len(unknown),pools=[])
    pools=[dict(task=task,seed=seed,**pool(groups[task,seed],load_seconds)) for task,seed in sorted(groups)]
    aggregate={}
    for scenario in pools[0]['scenarios']:
        aggregate[scenario]={}
        for policy in pools[0]['scenarios'][scenario]:
            values=[p['scenarios'][scenario][policy] for p in pools]
            aggregate[scenario][policy]=dict(macro_probability_valid_final=statistics.mean(v['probability_valid_final'] for v in values),
                macro_net_preference=statistics.mean(v['net_preference'] for v in values),
                median_pool_net_preference=statistics.median(v['net_preference'] for v in values),
                std_pool_net_preference=statistics.stdev(v['net_preference'] for v in values),
                per_task={task:dict(mean_probability_valid_final=statistics.mean(p['scenarios'][scenario][policy]['probability_valid_final'] for p in pools if p['task']==task),
                    mean_net_preference=statistics.mean(p['scenarios'][scenario][policy]['net_preference'] for p in pools if p['task']==task)) for task in sorted({p['task'] for p in pools})})
    return dict(status='COMPLETE_NATIVE_FINAL_CHOICE',pools=pools,aggregate=aggregate,unknown_count=0,
        physical_runs=5,programs=30,full_e2e=False,heldout_confirmation=False,
        cost_boundary='Conditional serial replay, includes query and native-analysis time; cold load separate. Initial pool-generation cost excluded, not an E2E speedup. Combinations are not independent seeds.')
