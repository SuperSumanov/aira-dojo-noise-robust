"""Independent returned routing, cost, context-size and generation receipts."""
from collections import Counter
from decimal import Decimal, ROUND_CEILING
import json
import sqlite3
from contextlib import closing
from run_repair_transfer_20260913 import ROOT, checked, OLD_COUNTS, now
from prepare_repair_transfer_20260913 import read, sha, dump


def main():
    p=checked();finish=read(ROOT/'generation-finished.json')
    if not finish['complete'] or finish['completed']!=24:raise ValueError('not closed')
    models=Counter();providers=Counter();reasons=Counter();rows=[];total=0
    for row in p['rows']:
        index=row['index'];gen=read(ROOT/f'generated-{index}.json')
        response=read(ROOT/f'response-{index}.private.json',gen['response_sha256'])
        model=response.get('model');provider=response.get('provider')
        if model!='qwen/qwen3-coder-flash' or str(provider).lower()!='alibaba':raise ValueError('returned routing mismatch')
        models[model]+=1;providers[provider]+=1
        choices=response.get('choices') or [];reason=choices[0].get('finish_reason') if len(choices)==1 else 'bad_schema';reasons[str(reason)]+=1
        usage=response['usage'];cost=int((Decimal(str(usage['cost']))*10**9).to_integral_value(rounding=ROUND_CEILING));total+=cost
        if cost<0 or cost>100000000:raise ValueError('price bound')
        if usage['prompt_tokens']>102000 or usage['completion_tokens']>8192:raise ValueError('token envelope')
        if gen['status']=='generated' and sha((ROOT/'codes'/f'{index}.py').read_bytes())!=gen['code_sha256']:raise ValueError('code hash')
        rows.append(dict(index=index,model=model,provider=provider,status=gen['status'],finish_reason=reason,
            cost_nusd=cost,prompt_tokens=usage['prompt_tokens'],completion_tokens=usage['completion_tokens'],seconds=gen['seconds'],
            generated_receipt_sha256=sha((ROOT/f'generated-{index}.json').read_bytes())))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        new=db.execute("SELECT id,held,cost,state FROM calls WHERE scope LIKE 'transfer_case_%'").fetchall()
        all_counts=db.execute('SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)),SUM(state="unresolved") FROM calls').fetchone()
    if len(new)!=24 or sum(r[2] for r in new)!=total or any(r[1]!=r[2] or r[3]!='settled' for r in new):raise ValueError('settlement binding')
    if all_counts!=(OLD_COUNTS[0]+24,OLD_COUNTS[1]+total,OLD_COUNTS[2]+total,2):raise ValueError('cumulative old liabilities')
    result=dict(utc=now(),status='PASS',requests=24,models=dict(models),providers=dict(providers),finish_reasons=dict(reasons),
        incremental_api_cost_usd=str(Decimal(total)/10**9),all_calls=all_counts[0],unresolved=all_counts[3],
        generated=sum(r['status']=='generated' for r in rows),max_generation_seconds=max(r['seconds'] for r in rows),rows=rows,
        caveat='HTTP timeout is per transport phase, not an independent hard 120-second total timer; whole generation process has a 3300-second bound. T1 is not a strict combined wallclock e2e trial.')
    digest=dump(ROOT/'generation-verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}|dict(verification_sha256=digest)))


if __name__=='__main__':main()
