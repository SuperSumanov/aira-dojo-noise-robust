"""Independent list-scan verification and run-level exploratory contrasts.

Does not import the producer or reuse its choice/summary functions.
"""
import argparse,csv,hashlib,json,math,statistics
from collections import defaultdict
from pathlib import Path

def main(root):
    rows=json.loads((root/'runs.json').read_text())
    nodes=json.loads((root/'nodes.json').read_text())
    summary=json.loads((root/'summary.json').read_text())
    by_run=defaultdict(list)
    for n in nodes:by_run[n['run']].append(n)
    assert len({r['run'] for r in rows})==len(rows)==46
    journals=[r['journal_sha256'] for r in rows if r['journal_sha256']]
    assert len(journals)==len(set(journals))
    checked=0;root_pools=[];eligible_slots=[];mismatches=[]
    for r in rows:
        ns=[n for n in by_run[r['run']] if n['group']=='executed']
        best=None;seen_directions=set()
        for n in ns:
            if n['is_buggy'] or n['metric'] is None:continue
            assert isinstance(n['metric_maximize'],bool)
            seen_directions.add(n['metric_maximize'])
            if best is None or (n['metric']>best['metric'] if n['metric_maximize'] else n['metric']<best['metric']):best=n
        assert len(seen_directions)<=1
        value=best['score'] if best else None
        if value!=r['selected_score']:mismatches.append(r['run'])
        checked+=bool(ns)
        if r['arm'].startswith('forets'):
            pool=[n for n in by_run[r['run']] if n['parents']==[0] and 'draft' in n['operators_used']]
            executed=[n for n in pool if n['group']=='executed']
            unselected=[n for n in pool if n['group']=='unselected']
            complete=(len(pool)==r['num_children']==6 and len(executed)==2 and len(unselected)==4
                      and len({n['id'] for n in pool})==6)
            item=dict(run=r['run'],stratum=r['stratum'],arm=r['arm'],seed=r['seed'],
                executed=len(executed),unselected=len(unselected),complete_6_candidate_pool=complete,
                unique_codes=len({n['code_sha256'] for n in pool}),
                original_ranks_available=any('critic' in k or 'estimated_value' in k for n in pool for k in n['field_names']))
            root_pools.append(item)
            if complete:
                for n in sorted(pool,key=lambda n:(n['creation_time'],n['id'])):
                    eligible_slots.append({**{k:item[k] for k in ('run','stratum','arm','seed')},
                        'node':n['id'],'code_sha256':n['code_sha256'],'originally_executed':n['group']=='executed'})
    assert not mismatches
    comparisons=[]
    strata=sorted({r['stratum'] for r in rows})
    for stratum in strata:
        relevant=[r for r in rows if r['stratum']==stratum]
        base={r['seed']:r for r in relevant if r['arm']=='mcts'}
        for arm in sorted({r['arm'] for r in relevant if r['arm']!='mcts'}):
            forets={r['seed']:r for r in relevant if r['arm']==arm}
            pairs=[];unknown=[]
            for seed in sorted(set(base)&set(forets)):
                a,b=forets[seed],base[seed]
                assert a['search_budget']==b['search_budget'] and a['execution_timeout']==b['execution_timeout']
                if a['selected_score'] is None or b['selected_score'] is None:
                    unknown.append(seed);continue
                sign=-1 if a['lower_better'] else 1
                pairs.append({'seed':seed,'forets':a['selected_score'],'mcts':b['selected_score'],
                    'oriented_difference':sign*(a['selected_score']-b['selected_score']),
                    'forets_seconds':a['running_time'],'mcts_seconds':b['running_time'],
                    'commit_equal':a['commit']==b['commit']})
            differences=[p['oriented_difference'] for p in pairs]
            w=sum(d>0 for d in differences);l=sum(d<0 for d in differences);t=sum(d==0 for d in differences);n=w+l
            p=min(1.0,2*sum(math.comb(n,i) for i in range(min(w,l)+1))/2**n) if n else None
            comparisons.append(dict(stratum=stratum,arm=arm,paired=len(pairs),unknown_shared_seeds=unknown,
                unpaired_forets_seeds=sorted(set(forets)-set(base)),wins=w,losses=l,ties=t,
                median_oriented_difference=statistics.median(differences) if differences else None,
                mean_oriented_difference=statistics.mean(differences) if differences else None,
                sd_oriented_difference=statistics.stdev(differences) if len(differences)>1 else None,
                descriptive_two_sided_sign_p=p,pairs=pairs,
                caveat='Shared seed and nominal budget only; actual duration/hardware not matched. Not causal confirmation.'))
    # Independently reproduce all group means/medians/SD from the chosen values.
    for g in summary['groups']:
        vs=[r['selected_score'] for r in rows if r['stratum']==g['stratum'] and r['arm']==g['arm'] and r['selected_score'] is not None]
        assert len(vs)==g['selected']['n']
        if vs:
            assert math.isclose(sum(vs)/len(vs),g['selected']['mean'],abs_tol=1e-12)
            assert statistics.median(vs)==g['selected']['median']
            if len(vs)>1:assert math.isclose(statistics.stdev(vs),g['selected']['sd'],abs_tol=1e-12)
    result=dict(status='INDEPENDENT_PASS',runs=46,journals_checked=checked,choice_mismatches=0,
        shared_journal_hashes=0,contrasts=comparisons,root_pools=root_pools,
        complete_root_pools=sum(p['complete_6_candidate_pool'] for p in root_pools),
        unselected_nodes=sum(n['group']=='unselected' for n in nodes),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'runs.json',root/'nodes.json',root/'summary.json']})
    with (root/'independent.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    # A structural inventory, not a GPU replay authorization or grade-derived selection.
    with (root/'root_pool_inventory.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(eligible_slots[0]));writer.writeheader();writer.writerows(eligible_slots)
    print(json.dumps({k:v for k,v in result.items() if k!='root_pools'},indent=2))
    print(json.dumps({'pool_groups':{s:sum(p['complete_6_candidate_pool'] for p in root_pools if p['stratum']==s) for s in strata},
        'pool_sizes':[(p['stratum'],p['seed'],p['executed'],p['unselected']) for p in root_pools if not p['complete_6_candidate_pool']],
        'ranks_available':sum(p['original_ranks_available'] for p in root_pools)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);main(parser.parse_args().root)
