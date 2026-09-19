"""Independent arithmetic and local closed-label check; no primary analyzer import."""
import argparse,hashlib,json,math
from pathlib import Path

def near(a,b):
    return a is b if a is None or b is None else math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)

def verify(summary,labels):
    rows=summary['rows'];known={r['node']:r for r in labels}
    if len(rows)!=30 or len(known)!=30 or len({r['node'] for r in rows})!=30:raise ValueError('complete population')
    for r in rows:
        original=known[r['node']]
        for key in ('task','seed','run','slot','node','code_sha256','valid','score','independent_score','original_selected','exit_code','timed_out'):
            if r[key]!=original[key]:raise ValueError('closed label/source mismatch')
    groups={}
    for r in rows:groups.setdefault((r['task'],r['seed']),[]).append(r)
    expected={('leaf-classification',1),('leaf-classification',2),('leaf-classification',3),('spooky-author-identification',1),('spooky-author-identification',2)}
    if set(groups)!=expected or len(summary['pools'])!=5:raise ValueError('pool population')
    checked={}
    for taskseed,data in groups.items():
        positions={}
        for a in data:
            positions[a['slot']]=sum(b['reward']>a['reward'] or (b['reward']==a['reward'] and b['slot']<a['slot']) for b in data)
        pool,=[p for p in summary['pools'] if (p['task'],p['seed'])==taskseed]
        if any(positions[slot]!=i for i,slot in enumerate(pool['critic_order'])):raise ValueError('critic ordering')
        pairs=[(a,b) for a in data for b in data if a['slot']<b['slot']]
        def quality(pair):
            valid=[-r['score'] for r in pair if r['valid']]
            return max(valid) if valid else -math.inf
        policies={'uniform_two_of_six':pairs,
            'frozen_top_two':[p for p in pairs if all(positions[r['slot']]<2 for r in p)],
            'frozen_top_three_then_uniform_two':[p for p in pairs if all(positions[r['slot']]<3 for r in p)]}
        for name,choices in policies.items():
            grades=[quality(pair) for pair in choices]
            valid=[g for g in grades if g!=-math.inf]
            signs=[int(g>quality(p))-int(g<quality(p)) for g in grades for p in pairs]
            calculated=dict(choices=len(choices),probability_any_valid=len(valid)/len(choices),
                expected_valid_count=sum(sum(r['valid'] for r in pair) for pair in choices)/len(choices),
                mean_oracle_best_loss_given_any_valid=-sum(valid)/len(valid) if valid else None,
                vs_uniform_wins=sum(s==1 for s in signs),vs_uniform_ties=sum(s==0 for s in signs),vs_uniform_losses=sum(s==-1 for s in signs),
                comparisons=len(signs),net_preference_vs_uniform=sum(signs)/len(signs))
            if set(pool['policies'][name])!=set(calculated) or any(not near(pool['policies'][name][key],value) for key,value in calculated.items()):raise ValueError('policy arithmetic')
            checked[taskseed,name]=calculated
        positives=[r for r in data if r['valid']];negatives=[r for r in data if not r['valid']]
        auc=sum(1 if a['reward']>b['reward'] else .5 if a['reward']==b['reward'] else 0 for a in positives for b in negatives)/(len(positives)*len(negatives)) if positives and negatives else None
        if not near(auc,pool['validity_ranking_auc']) or pool['valid_candidates']!=len(positives):raise ValueError('validity AUC')
    for name,p in summary['policies'].items():
        values=[checked[k,name]['probability_any_valid'] for k in expected]
        pref=[checked[k,name]['net_preference_vs_uniform'] for k in expected]
        mean=sum(values)/5
        if not near(mean,p['macro_probability_any_valid']) or not near(sorted(values)[2],p['median_probability_any_valid']) or not near(math.sqrt(sum((v-mean)**2 for v in values)/4),p['pool_std_probability_any_valid']) or not near(sum(pref)/5,p['macro_net_preference_vs_uniform']):raise ValueError('macro arithmetic')
        for task,t in p['per_task'].items():
            keys=[key for key in expected if key[0]==task]
            if not near(sum(checked[k,name]['probability_any_valid'] for k in keys)/len(keys),t['mean_probability_any_valid']) or not near(sum(checked[k,name]['net_preference_vs_uniform'] for k in keys)/len(keys),t['mean_net_preference_vs_uniform']):raise ValueError('task arithmetic')
    if summary['full_e2e_claim'] is not False or summary['independent_confirmation'] is not False or summary['model_training'] is not False:raise ValueError('scope')
    if not near(summary['gpu_hours'],sum(r['seconds'] for r in summary['allocations'])/3600) or summary['gpu_hours']>.5:raise ValueError('all attempts cost')
    return dict(status='PASS',programs=30,pools=5,checks=['closed_local_labels_exact','all_failed_pool_retained','rank_ties_by_slot','independent_pair_enumeration','oracle_quality_scope','macro_and_per_task','all_attempts_gpu_cost'])

def main(path,out):
    base=Path(__file__).parent/'results'
    files=[(base/'comparison_pool_20260919/combined/summary.json','41e42fbff91ca970e8f5ee19a1ffdf57c31ffe0ddd6a24182e5e304c1225ef4f'),
        (base/'comparison_spooky_pool_20260919/summary.json','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1')]
    labels=[]
    for file,digest in files:
        raw=file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('local closed source drift')
        labels.extend(r for r in json.loads(raw)['rows'] if r['task']=='leaf-classification' or r['seed'] in (1,2))
    raw=path.read_bytes();result=verify(json.loads(raw),labels)
    result['summary_sha256']=hashlib.sha256(raw).hexdigest()
    with out.open('x') as file:json.dump(result,file,indent=2)
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);p.add_argument('output',type=Path);a=p.parse_args();main(a.summary,a.output)
