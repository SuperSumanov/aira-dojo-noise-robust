"""Fixed complete-pool predictor diagnostic; no selection by observed outcome."""
import itertools,math,statistics

def pool_metrics(rows):
    if len(rows)!=6 or sorted(r['slot'] for r in rows)!=list(range(6)) or len({r['node'] for r in rows})!=6:raise ValueError('six unique slots')
    if any(type(r['valid']) is not bool or not math.isfinite(r['reward']) for r in rows):raise ValueError('complete known pool')
    if any(r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score'])) for r in rows):raise ValueError('valid finite grade')
    ranked=sorted(rows,key=lambda r:(-r['reward'],r['slot']))
    uniform=list(itertools.combinations(rows,2))
    policies={'uniform_two_of_six':uniform,'frozen_top_two':[tuple(ranked[:2])],
              'frozen_top_three_then_uniform_two':list(itertools.combinations(ranked[:3],2))}
    def best(pair):
        values=[r['score'] for r in pair if r['valid']]
        return min(values) if values else None
    def compare(a,b):
        if a is None:return 0 if b is None else -1
        if b is None:return 1
        return (b>a)-(b<a)
    output={}
    for name,choices in policies.items():
        values=[best(pair) for pair in choices];conditional=[v for v in values if v is not None]
        signs=[compare(a,best(pair)) for a in values for pair in uniform]
        output[name]=dict(choices=len(choices),probability_any_valid=len(conditional)/len(values),
            expected_valid_count=statistics.mean(sum(r['valid'] for r in pair) for pair in choices),
            mean_oracle_best_loss_given_any_valid=statistics.mean(conditional) if conditional else None,
            vs_uniform_wins=signs.count(1),vs_uniform_ties=signs.count(0),vs_uniform_losses=signs.count(-1),
            comparisons=len(signs),net_preference_vs_uniform=statistics.mean(signs))
    pos=[r for r in rows if r['valid']];neg=[r for r in rows if not r['valid']]
    auc=statistics.mean((a['reward']>b['reward'])+.5*(a['reward']==b['reward']) for a in pos for b in neg) if pos and neg else None
    return dict(critic_order=[r['slot'] for r in ranked],validity_ranking_auc=auc,valid_candidates=len(pos),policies=output,
        quality_is_post_execution_oracle_diagnostic=True)

def summarize(rows):
    expected={('leaf-classification',1),('leaf-classification',2),('leaf-classification',3),('spooky-author-identification',1),('spooky-author-identification',2)}
    groups={}
    for row in rows:groups.setdefault((row['task'],row['seed']),[]).append(row)
    if len(rows)!=30 or set(groups)!=expected:raise ValueError('fixed five pools')
    pools=[dict(task=task,seed=seed,**pool_metrics(groups[task,seed])) for task,seed in sorted(expected)]
    policies={}
    for name in pools[0]['policies']:
        values=[p['policies'][name]['probability_any_valid'] for p in pools]
        preferences=[p['policies'][name]['net_preference_vs_uniform'] for p in pools]
        policies[name]=dict(macro_probability_any_valid=statistics.mean(values),median_probability_any_valid=statistics.median(values),
            pool_std_probability_any_valid=statistics.stdev(values),macro_net_preference_vs_uniform=statistics.mean(preferences),
            per_task={task:dict(mean_probability_any_valid=statistics.mean(p['policies'][name]['probability_any_valid'] for p in pools if p['task']==task),
                mean_net_preference_vs_uniform=statistics.mean(p['policies'][name]['net_preference_vs_uniform'] for p in pools if p['task']==task)) for task in sorted({p['task'] for p in pools})})
    return dict(role='frozen_existing_reward_on_seen_complete_development_pools',pools=pools,policies=policies,
        independent_physical_runs=5,programs=30,model_training=False,independent_confirmation=False,full_e2e_claim=False,
        limitation='Seen development outcomes; fixed delivered critic, not reconstructed historical rank/template. Pool oracle quality is not the deployed final-submission rule. Five pools across two tasks do not establish generalization.')
