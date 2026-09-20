"""Separate finite enumeration and exact closed-source/native-parser verifier."""
import argparse,ast,hashlib,json,math,statistics,subprocess,sys,types
from pathlib import Path
from unittest.mock import patch
import verify_comparison_native_acceptance_20260919 as native

SOURCE_COMMIT='b7f8ab0f65dba9877ac3af35e3e770fc32546565'
SOURCE_SHA='f81203004ca873cc46a958a1fb9eba3b8dfabe5531f290453bcfc6f523f594d0'

def submission_hook():
    raw=subprocess.check_output(['git','show',SOURCE_COMMIT+':src/dojo/solvers/fore_ts/wallclock.py'],timeout=25)
    if hashlib.sha256(raw).hexdigest()!='a2f9597ab6670dd4e97b4c3ab88a656cd1f6de8bfc9060f61926c8f9c87a2b0c':raise ValueError('wallclock source')
    tree=ast.parse(raw);function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='remember_submission')
    # This closed component has no full-search budget or submission archive;
    # execute the unmodified production hook under that exact condition.
    namespace={'budget':lambda:None}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'<pinned-native-submission-hook>','exec'),namespace)
    module=types.ModuleType('dojo.solvers.fore_ts.wallclock');module.remember_submission=namespace['remember_submission']
    return module

def close(a,b):
    return a is b if a is None or b is None else math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)

def reference(pair,query,load,limit):
    used=query+load;eligible=[]
    for row in pair:
        if limit is not None and used>=limit:break
        used+=row['wall_seconds']+row['analysis_seconds']
        if limit is not None and used>limit:break
        if row['native_accepted']:eligible.append(row)
    ordered=sorted(eligible,key=lambda r:(r['native_metric'],r['slot']))
    winner=ordered[0] if ordered else None
    grade=-math.inf if winner is None or not winner['valid'] else -winner['score']
    return (None if winner is None else winner['slot']),grade,min(used,limit) if limit is not None else used

def verify(summary,reward,labels):
    rows=summary['rows'];rr={r['node']:r for r in reward['rows']};ll={r['node']:r for r in labels}
    if len(rows)!=30 or len(rr)!=30 or len(ll)!=30 or len({r['node'] for r in rows})!=30:raise ValueError('population')
    with patch.object(native,'COMMIT',SOURCE_COMMIT):parser,source_sha=native.native_parser()
    hook=submission_hook()
    if source_sha!=SOURCE_SHA:raise ValueError('pinned actual source')
    for row in rows:
        old=ll[row['node']];pred=rr[row['node']]
        for key in ('task','seed','run','slot','node','code_sha256','valid','score','independent_score','exit_code','timed_out'):
            if row[key]!=old[key]:raise ValueError('exact prior closed labels')
        for key in ('reward','inference_seconds'):
            if row[key]!=pred[key]:raise ValueError('exact frozen score')
        if row['wall_seconds']!=old['wall_seconds']:raise ValueError('execution cost')
        if row['analysis_status']=='returned':
            with patch.dict(sys.modules,{'dojo.solvers.fore_ts.wallclock':hook}):
                actual=native.decide(parser,is_bug=row['native_is_bug'],metric=row['native_metric'],exit_code=row['exit_code'],valid_guard=None)
            if actual is not row['native_accepted']:raise ValueError('production parser')
    unknown=sum(r['analysis_status']!='returned' for r in rows)
    if unknown:
        if summary['status']!='INCOMPLETE_NO_POINT_EFFECT_CLAIM' or summary['unknown_count']!=unknown or summary.get('pools'):raise ValueError('unknown not retained')
        return dict(status='PASS_UNKNOWN_RETAINED_NO_EFFECT',unknown=unknown,source_sha256=source_sha)
    if summary['full_e2e'] or summary['heldout_confirmation'] or summary['training'] or summary['paid_api_calls']:raise ValueError('claim scope')
    calculated={};groups={}
    for row in rows:groups.setdefault((row['task'],row['seed']),[]).append(row)
    for key,data in groups.items():
        pool,=[p for p in summary['pools'] if (p['task'],p['seed'])==key]
        rank={r['slot']:sum(o['reward']>r['reward'] or (o['reward']==r['reward'] and o['slot']<r['slot']) for o in data) for r in data}
        allpairs=[(a,b) for a in data for b in data if a['slot']<b['slot']]
        policies={'uniform_two_of_six':allpairs,
            'frozen_top_two':[tuple(sorted(p,key=lambda r:rank[r['slot']])) for p in allpairs if all(rank[r['slot']]<2 for r in p)],
            'frozen_top_three_then_uniform_two':[tuple(sorted(p,key=lambda r:rank[r['slot']])) for p in allpairs if all(rank[r['slot']]<3 for r in p)]}
        # Match the fixed ranked-combination presentation order; computations do
        # not depend on this order, but final-slot lists must be reproducible.
        for name in ('frozen_top_two','frozen_top_three_then_uniform_two'):policies[name].sort(key=lambda p:tuple(rank[r['slot']] for r in p))
        for scenario,limit,cold in [('two_evaluations',None,False),('replay_2100_warm',2100.,False),('replay_2100_cold',2100.,True)]:
            outputs={name:[reference(pair,sum(r['inference_seconds'] for r in data) if name!='uniform_two_of_six' else 0.,
                       reward['encoder']['load_seconds'] if cold and name!='uniform_two_of_six' else 0.,limit) for pair in pairs] for name,pairs in policies.items()}
            for name,values in outputs.items():
                record=pool['scenarios'][scenario][name];grades=[v[1] for v in values];valid=[g for g in grades if g!=-math.inf]
                signs=[int(a>b[1])-int(a<b[1]) for a in grades for b in outputs['uniform_two_of_six']]
                expected=dict(choices=len(values),probability_valid_final=len(valid)/len(values),mean_final_loss_given_valid=-sum(valid)/len(valid) if valid else None,
                    median_conditional_replay_seconds=statistics.median(v[2] for v in values),wins=signs.count(1),ties=signs.count(0),losses=signs.count(-1),net_preference=sum(signs)/len(signs),comparisons=len(signs))
                if any(not close(record[k],v) for k,v in expected.items()):raise ValueError('independent pair enumeration')
                if record['final_slots']!=[v[0] for v in values] or record['final_losses']!=[None if v[1]==-math.inf else -v[1] for v in values]:raise ValueError('actual final not oracle')
                calculated[key,scenario,name]=expected
    for scenario,methods in summary['aggregate'].items():
        for name,record in methods.items():
            data=[calculated[k,scenario,name] for k in groups];prefs=[r['net_preference'] for r in data]
            expected=dict(macro_probability_valid_final=statistics.mean(r['probability_valid_final'] for r in data),macro_net_preference=statistics.mean(prefs),
                median_pool_net_preference=statistics.median(prefs),std_pool_net_preference=statistics.stdev(prefs))
            if any(not close(record[k],v) for k,v in expected.items()):raise ValueError('macro/variance')
            for task,values in record['per_task'].items():
                records=[calculated[k,scenario,name] for k in groups if k[0]==task]
                if not close(values['mean_probability_valid_final'],statistics.mean(r['probability_valid_final'] for r in records)) or not close(values['mean_net_preference'],statistics.mean(r['net_preference'] for r in records)):raise ValueError('task macro')
    if not close(summary['gpu_hours'],summary['allocation_seconds']*2/3600) or summary['gpu_hours']>3000*2/3600:raise ValueError('GPU cost')
    return dict(status='PASS',programs=30,pools=5,source_sha256=source_sha,checks=['exact_closed_labels_and_frozen_predictions','actual_source_native_parser','independent_final_choice_enumeration','never_external_oracle','query_and_cold_cost','failed_task_retained','macro_and_task_variance'])

def main(path,out):
    base=Path(__file__).parent/'results';labels=[]
    for name,digest,seeds in [('comparison_pool_20260919/combined/summary.json','41e42fbff91ca970e8f5ee19a1ffdf57c31ffe0ddd6a24182e5e304c1225ef4f',(1,2,3)),
                            ('comparison_spooky_pool_20260919/summary.json','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1',(1,2))]:
        raw=(base/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('local closed source hash')
        labels.extend(row for row in json.loads(raw)['rows'] if row['seed'] in seeds)
    raw=(base/'comparison_frozen_reward_20260919/summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='a1f7f22787e306512f715948d9abc25cbd499d8370880d4f0e286b35c63a68d9':raise ValueError('frozen summary hash')
    summary_raw=path.read_bytes();result=verify(json.loads(summary_raw),json.loads(raw),labels);result['summary_sha256']=hashlib.sha256(summary_raw).hexdigest()
    with out.open('x') as file:json.dump(result,file,indent=2)
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);p.add_argument('output',type=Path);a=p.parse_args();main(a.summary,a.output)
