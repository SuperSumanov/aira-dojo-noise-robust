"""Pure source preparation for a possible successor; no activation or spending.

The caller must first close the current block and hand over every ledger row.
The original USD10/CNY100 authorization is an absolute cumulative ceiling.
"""
from decimal import Decimal
import re

UNIT=10**9
POLICIES={
    'qwen/qwen3-coder-flash':dict(reserve=700000000,run_cap=1500000000,
        increment=2000000000,prompt='0.65',completion='2.6'),
    'qwen/qwen3-coder-plus':dict(reserve=2600000000,run_cap=5500000000,
        increment=8000000000,prompt='2.4375',completion='9.75'),
}


def terms(model, *, accounted, settled, calls, unknown, authorization, seed):
    if model not in POLICIES:raise ValueError('unreviewed model')
    if any(type(v) is not int or v<0 for v in (accounted,settled,calls,unknown,seed)):
        raise ValueError('integer cumulative facts required')
    if settled>accounted or accounted>=10*UNIT or unknown>calls or seed not in (12,13):
        raise ValueError('invalid parent facts or future seed')
    if not re.fullmatch('[0-9a-f]{64}',authorization):raise ValueError('exact parent authorization required')
    p=POLICIES[model]
    worst=Decimal(p['prompt'])+Decimal(8192)*Decimal(p['completion'])/10**6
    if worst>Decimal(p['reserve'])/UNIT:raise ValueError('request reservation below public price envelope')
    total=min(10*UNIT,accounted+p['increment'])
    if total-accounted<p['reserve']:raise ValueError('insufficient cumulative room for one request')
    return dict(version=5,total=total,incremental_cap=total-accounted,
        predecessor_authorization=authorization,predecessor_accounted=accounted,
        predecessor_settled=settled,predecessor_calls=calls,predecessor_unresolved=unknown,
        run_limit=p['run_cap'],route_limit=p['run_cap'],model=model,reservation=p['reserve'],
        context_tokens=1000000,output_tokens=8192,
        experiment=f'future-seed{seed}-'+model.rsplit('/',1)[1],
        accounted_cny_ceiling=str(Decimal(total)/UNIT*Decimal('8.8')))


def patch(source, model, **parent):
    """No initializer, database operation or alteration of the live parent."""
    auth=terms(model,**parent);p=POLICIES[model]
    if 'raise RuntimeError("use exact cumulative ledger handover")' not in source:
        raise ValueError('parent initializer is not disabled')
    patterns=[(r"(?m)^MODEL = '[^']+'$",'MODEL = '+repr(model)),
              (r'(?m)^RESERVE = [0-9_]+$',f"RESERVE = {p['reserve']}"),
              (r'(?m)^ +max_price=dict\(prompt=[0-9.]+, completion=[0-9.]+, request=0\)\)$',
               f"                max_price=dict(prompt={p['prompt']}, completion={p['completion']}, request=0))")]
    for pattern,replacement in patterns:
        source,n=re.subn(pattern,replacement,source)
        if n!=1:raise ValueError('unexpected parent budget source')
    anchor='AUTH_RAW = json.dumps(AUTH,'
    if source.count(anchor)!=1:raise ValueError('unexpected authorization anchor')
    # Provider is set before the base AUTH declaration; append the actual parent
    # facts after any older version updates and before computing the new digest.
    source=source.replace(anchor,'AUTH.update('+repr(auth)+')\n'+anchor)
    return source,auth


def patch_catalog(source):
    """Keep the route capability checks; price bounds follow the new AUTH."""
    old="""        for name,limit in [('prompt','0.00000065'),('completion','0.0000026'),
                            ('input_cache_read','0.00000065'),('input_cache_write','0.00000065')]:"""
    new="""        for name,limit in [('prompt', Decimal(str(AUTH['provider']['max_price']['prompt'])) / 10**6),
                           ('completion', Decimal(str(AUTH['provider']['max_price']['completion'])) / 10**6),
                           ('input_cache_read', Decimal(str(AUTH['provider']['max_price']['prompt'])) / 10**6),
                           ('input_cache_write', Decimal(str(AUTH['provider']['max_price']['prompt'])) / 10**6)]:"""
    if source.count(old)!=1:raise ValueError('unexpected catalog price anchors')
    return source.replace(old,new)
