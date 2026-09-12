"""Posthoc same-pool decision/cost contrast, never unexecuted candidate labels."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og')
SUMMARY='a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90'

def collect():
    from readout_forets_pool_completion_20260912 import rank
    raw=(ROOT/'wallclock-summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SUMMARY:raise ValueError('closed parent drift')
    receipt=json.loads((ROOT/'recovery-readout-finished.json').read_bytes())
    if receipt['status']!='verified' or receipt['summary_sha256']!=SUMMARY:raise ValueError('closure')
    summary=json.loads(raw);rows=[];incomplete=[];costs=[0,0];calls=[0,0];evidence={}
    def read(p):
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT):raise ValueError('scope')
        b=p.read_bytes();evidence[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest();return json.loads(b)
    with sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for item in summary['rows']:
            if item['arm']!='critic_topk_random':continue
            rid=item['run_id'];cfg=read(ROOT/'configs'/(rid+'.json'));cp=Path(cfg['solver']['checkpoint_path'])
            for directory in sorted((cp/'forets-contextual-judge-private').glob('batch-*')):
                inp=read(directory/'input.json');step=inp['step'];ranks=[]
                for j,order in enumerate(inp['orders']):
                    billed=db.execute('SELECT state,cost FROM calls WHERE id=? AND scope=?',(f'{rid}-context-pool-{step}-order-{j}',rid)).fetchall()
                    if not billed:continue
                    if len(billed)!=1 or billed[0][0]!='settled' or type(billed[0][1]) is not int:raise ValueError('unsettled rank')
                    costs[j]+=billed[0][1];calls[j]+=1
                    response=read(directory/f'response-{j}.json');saved=read(directory/f'rank-{j}.json')
                    r=rank(response,order)
                    if saved['original_slot_order']!=r or saved['response_sha256']!=evidence[str((directory/f'response-{j}.json').relative_to(ROOT))]:raise ValueError('rank receipt')
                    request=read(directory/f'request-{j}.json');displayed=json.loads(request['messages'][1]['content'])['candidates']
                    if len(displayed)!=len(order) or [hashlib.sha256(v['code'].encode()).hexdigest() for v in displayed]!=[inp['codes_sha256'][i] for i in order]:raise ValueError('request code binding')
                    ranks.append(r)
                if len(ranks)!=2:
                    incomplete.append(dict(run_id=rid,step=step,completed_rank_orders=len(ranks)));continue
                done=read(directory/'finished.json');n=len(ranks[0]);scores=[(2*n-ranks[0].index(i)-ranks[1].index(i))/2 for i in range(n)]
                if done['rankings']!=ranks or done['borda']!=scores:raise ValueError('aggregation differs')
                top=sorted(range(n),key=lambda i:(-scores[i],i))[:2];ordered=sorted(scores,reverse=True)
                rows.append(dict(run_id=rid,task=item['task'],seed=item['seed'],step=step,
                    first_reverse_top2_agree=set(ranks[0][:2])==set(ranks[1][:2]),
                    borda_changes_first_top2=set(top)!=set(ranks[0][:2]),
                    borda_changes_reverse_top2=set(top)!=set(ranks[1][:2]),
                    cutoff_borda_tie=ordered[1]==ordered[2]))
    totals=dict(complete_two_order_pools=len(rows),incomplete_pools=len(incomplete),
        first_reverse_top2_agree=sum(r['first_reverse_top2_agree'] for r in rows),
        borda_changes_first_top2=sum(r['borda_changes_first_top2'] for r in rows),
        borda_changes_reverse_top2=sum(r['borda_changes_reverse_top2'] for r in rows),
        cutoff_borda_ties=sum(r['cutoff_borda_tie'] for r in rows),
        first_order_calls=calls[0],reverse_order_calls=calls[1],first_order_cost_usd=costs[0]/1e9,
        reverse_order_cost_usd=costs[1]/1e9,total_ranking_cost_usd=sum(costs)/1e9)
    return dict(role='posthoc_keep_set_and_api_cost_only',totals=totals,rows=rows,incomplete=incomplete,
        summary_sha256=SUMMARY,evidence_sha256=evidence,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitation='Four correlated search runs, not independent pools. Unchanged set does not show the second vote was useless ex ante. No ranking-latency measurement or single-vote end-to-end benefit; incomplete ranking cost retained. No model calls, labels, or source mutations.')

if __name__=='__main__':
    result=collect()
    with (ROOT/'rank-cost-audit.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='evidence_sha256'}))
