"""Historical head-of-line repair delays; not counterfactual policy gains."""
import argparse,hashlib,json,math,statistics,subprocess
from pathlib import Path

def stats(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        mean=statistics.mean(values) if values else None,sd=statistics.stdev(values) if len(values)>1 else None,
        minimum=min(values) if values else None,maximum=max(values) if values else None)

def analyze(runs,nodes,metadata):
    if len({r['run'] for r in runs})!=len(runs):raise ValueError('duplicate run')
    nodekeys=[(n['run'],n['id']) for n in nodes];metkeys=[(n['run'],n['node']) for n in metadata]
    if len(set(nodekeys))!=len(nodekeys) or len(set(metkeys))!=len(metkeys) or set(nodekeys)!=set(metkeys):raise ValueError('exact identity join')
    meta=dict(zip(metkeys,metadata));rows=[]
    for run in runs:
        if not (run['arm'].startswith('forets') and run['journal_present']):continue
        executed=sorted([n for n in nodes if n['run']==run['run'] and n['group']=='executed'],key=lambda n:n['step'])
        if len({n['step'] for n in executed})!=len(executed):raise ValueError('duplicate execution step')
        roots=[n for n in executed if n['parents']==[0] and (n['operators_used'] or [None])[0]=='draft']
        if len(roots)!=2:raise ValueError('fixed complete initial selected pair')
        first,second=roots
        between=[n for n in executed if first['step']<n['step']<second['step']]
        parent_steps={first['step']}
        generation=execution=analysis=0.
        for n in between:
            if not n['operators_used'] or n['operators_used'][0]!='debug' or len(n['parents'])!=1 or n['parents'][0] not in parent_steps:raise ValueError('not sequential first-child repair chain')
            parent_steps.add(n['step']);m=meta[(n['run'],n['id'])]
            if m['operators']!=n['operators_used'] or m['group']!='executed':raise ValueError('metadata roles')
            g=m['numeric_operator_fields'].get('.0.usage.latency')
            a=m['numeric_operator_fields'].get('.1.usage.latency')
            e=n['exec_time']
            if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (g,a,e)):raise ValueError('missing component cost')
            generation+=g;analysis+=a;execution+=e
        repaired=[n for n in between if n['is_buggy'] is False]
        rows.append(dict(run=run['run'],task=run['stratum'].split('/')[0],arm=run['arm'],seed=run['seed'],
            first_buggy=first['is_buggy'],second_buggy=second['is_buggy'],first_step=first['step'],second_step=second['step'],
            intervening_debug_nodes=len(between),native_nonbuggy_repairs=len(repaired),
            ready_second_sibling=second['creation_time']<=min((n['creation_time'] for n in between),default=second['creation_time']),
            delayed_nonbuggy_second_after_only_failed_repairs=bool(between) and first['is_buggy'] is True and second['is_buggy'] is False and not repaired,
            logged_debug_generation_seconds=generation,logged_debug_analysis_seconds=analysis,logged_debug_execution_seconds=execution,
            logged_serial_components_seconds=generation+analysis+execution,
            second_reported_execution_seconds=second['exec_time'],second_external_score_present=second['score'] is not None,
            second_external_score=second['score'],first_external_score=first['score']))
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        group=[r for r in rows if r['task']==task];blocked=[r for r in group if r['intervening_debug_nodes']]
        strong=[r for r in group if r['delayed_nonbuggy_second_after_only_failed_repairs']]
        groups.append(dict(task=task,physical_runs=len(group),blocked_second_siblings=len(blocked),
            blocked_ready=sum(r['ready_second_sibling'] for r in blocked),positive_opportunity_runs=len(strong),
            blocker_component_seconds=stats([r['logged_serial_components_seconds'] for r in blocked]),
            positive_opportunity_component_seconds=stats([r['logged_serial_components_seconds'] for r in strong])))
    return dict(role='historical_selected_sibling_blocking_not_causal_gain',rows=rows,by_task=groups,
        physical_runs=len(rows),blocked=sum(r['intervening_debug_nodes']>0 for r in rows),
        positive_opportunity_runs=sum(r['delayed_nonbuggy_second_after_only_failed_repairs'] for r in rows),
        limitations=['Native nonbuggy is not independently verified correctness.',
            'Serial recorded component times include queuing/retries; not exclusive GPU service time or exact wall savings.',
            'Counterfactual execution order can change workspace, feedback, search state and final quality.',
            'No historical reordering is reported as an online outcome or confirmed speedup.',
            'All complete original selected pairs are included, not selected by positive outcomes.'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('output',type=Path);a=parser.parse_args()
    names=('runs.json','nodes.json','operator-cost-metadata.json');raws=[(a.root/n).read_bytes() for n in names]
    result=analyze(*(json.loads(b) for b in raws));result['input_sha256']={n:hashlib.sha256(b).hexdigest() for n,b in zip(names,raws)}
    result['analysis_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();result['analysis_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x') as h:json.dump(result,h,indent=2,allow_nan=False);h.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
