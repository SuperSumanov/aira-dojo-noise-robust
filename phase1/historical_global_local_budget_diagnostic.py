"""Train-only what-if budgets. Reuse L lengths; encode additional G only.

No pool creation, model fit, evaluation, or protocol amendment. Diagnostic SHA
order is explicitly NOT an adopted training sampler.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

from phase1.historical_train_encoding_readiness import (
    TRAIN,CARDS,MODEL,SOURCE,EXPECTED,CONFIG,ENCODER_CONFIG,checked_digest,
    independent_encode,install_access_guard,extract_train_inputs,
)
from phase1.historical_global_local_pool_readiness import GLOBAL,GLOBAL_SHA,project_pairs

LENGTHS=Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv')
LENGTH_SHA='789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a'


def cycle_prefix_cost(costs,n):
    cycles,tail=divmod(n,len(costs))
    return cycles*sum(costs)+sum(costs[:tail])


def whole_prefix_for_tokens(costs,target):
    cycles,remaining=divmod(target,sum(costs))
    count=cycles*len(costs)
    for cost in costs:
        if remaining==0: return {'reachable':True,'pairs':count,'overshoot_tokens':0}
        remaining-=cost; count+=1
        if remaining<0: return {'reachable':False,'pairs_if_next_included':count,'overshoot_tokens':-remaining}
    assert remaining==0
    return {'reachable':True,'pairs':count,'overshoot_tokens':0}


def run(output):
    assert not output.exists() and output.is_relative_to(Path('/tmp'))
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('HF_HUB_OFFLINE')=='1'
    output.mkdir(mode=0o700); os.environ['TMPDIR']=str(output)
    opens,denied=install_access_guard(output); start=time.monotonic()
    for p,h in EXPECTED.items(): checked_digest(p,h,scan=p in (TRAIN,CARDS))
    checked_digest(GLOBAL,GLOBAL_SHA,scan=True); checked_digest(LENGTHS,LENGTH_SHA)
    cfg=json.loads(CONFIG.read_text()); assert all(cfg[k]==v for k,v in ENCODER_CONFIG.items())
    local=project_pairs(TRAIN.read_text()); allglobal=project_pairs(GLOBAL.read_text())
    needed_local={x for p in local for x in p}
    grouped=json.loads(CARDS.read_text()); runs={};tasks={}
    for run,cards in grouped.items():
        for c in cards:
            assert c['id'] not in runs
            runs[c['id']]=run;tasks[c['id']]=c['task']['name']
    local_runs={runs[x] for x in needed_local}; local_pairs=set(local)
    global_pairs=[p for p in allglobal if all(x in runs and runs[x] in local_runs for x in p)
                  and tasks[p[0]]==tasks[p[1]] and p not in local_pairs]
    assert len(global_pairs)==len(set(global_pairs))==9392
    needed_global={x for p in global_pairs for x in p}; additional=needed_global-needed_local
    assert len(additional)==3640
    lengths={}
    with LENGTHS.open() as f: cached=list(csv.DictReader(f))
    for ordinal,(cid,row) in enumerate(zip(sorted(needed_local),cached)):
        assert int(row['ordinal'])==ordinal
        lengths[cid]=int(row['valid_tokens'])
    assert len(lengths)==len(cached)==4095
    code,_,_,_=extract_train_inputs(grouped,additional); del grouped
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(1)
    tok=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=False)
    tok.model_max_length=10**9
    spec=importlib.util.spec_from_file_location('bound_g_pairs',SOURCE)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    encoder=module.CardEncoder(code,tasks,tok,**ENCODER_CONFIG)
    new_raw=[]
    for i,cid in enumerate(sorted(additional)):
        assert time.monotonic()-start<1200,'bounded_cpu_time'
        ids,raw_n=independent_encode(code[cid],tasks[cid],tok)
        assert tuple(encoder(cid))==ids
        lengths[cid]=len(ids);new_raw.append(raw_n)
        if i%250==0: (output/'progress.json').write_text(json.dumps({'new_endpoints_done':i+1,'total':len(additional)}))
    target=sum(lengths[x] for p in global_pairs+local for x in p)
    total_pairs=len(global_pairs)+len(local); rows=[]
    for seed in (6,7,8):
        for source,pool in (('G',global_pairs),('L',local)):
            key=lambda p:hashlib.sha256(json.dumps([seed,source,*p],separators=(',',':')).encode()).hexdigest()
            costs=[sum(lengths[x] for x in p) for p in sorted(pool,key=key)]
            spend=cycle_prefix_cost(costs,total_pairs)
            rows.append({'seed':seed,'source':source,'unique_source_pairs':len(pool),
                'source_once_valid_tokens':sum(costs),'same_pair_visits':total_pairs,
                'same_pair_visits_valid_tokens':spend,'G_to_L_valid_tokens':target,
                'relative_valid_token_difference':spend/target-1,
                'exact_token_prefix':whole_prefix_for_tokens(costs,target)})
    assert not torch.cuda.is_initialized() and not denied
    # Anonymous per-pair costs permit arithmetic replay without re-tokenizing.
    with (output/'diagnostic_costs.csv').open('x',newline='') as f:
        w=csv.writer(f); w.writerow(('seed','source','ordinal','valid_tokens'))
        for seed in (6,7,8):
            for source,pool in (('G',global_pairs),('L',local)):
                key=lambda p:hashlib.sha256(json.dumps([seed,source,*p],separators=(',',':')).encode()).hexdigest()
                w.writerows((seed,source,i,sum(lengths[x] for x in p)) for i,p in enumerate(sorted(pool,key=key)))
    result={'status':'HISTORICAL_WHAT_IF_BUDGET_DIAGNOSTIC_NOT_ADOPTED',
        'base_commit':'7677501b66859284f41545f39a1f00469b20ee4f',
        'script_sha256':checked_digest(__file__),'encoder_source_sha256':EXPECTED[SOURCE],
        'train_sha256':EXPECTED[TRAIN],'global_sha256':GLOBAL_SHA,'cards_sha256':EXPECTED[CARDS],
        'reused_local_length_sha256':LENGTH_SHA,'encoder_config':ENCODER_CONFIG,
        'reused_local_endpoints':len(needed_local),'new_global_endpoints_encoded':len(additional),
        'new_global_endpoints_truncated':sum(n>16384 for n in new_raw),
        'global_pairs':len(global_pairs),'local_pairs':len(local),'combined_pair_visits':total_pairs,
        'combined_valid_tokens':target,'rows':rows,
        'diagnostic_order_rule':'sha256(compact_json([seed,source,sorted_endpoint_0,sorted_endpoint_1]))',
        'not_existing_or_approved_training_sampler':True,
        'new_pool_created':False,'model_fits':0,'gpu_context_created':False,
        'dev_test_vault_files_opened':0,'data_open_counts':dict(opens),'denied_attempts':dict(denied),
        'diagnostic_costs_sha256':checked_digest(output/'diagnostic_costs.csv'),
        'wall_seconds_not_throughput':time.monotonic()-start}
    for p,h in ((TRAIN,EXPECTED[TRAIN]),(CARDS,EXPECTED[CARDS]),(GLOBAL,GLOBAL_SHA),(LENGTHS,LENGTH_SHA)):
        checked_digest(p,h)
    (output/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-root',type=Path,required=True)
    try: run(p.parse_args().output_root.resolve())
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','exception_type':type(exc).__name__}))
        raise SystemExit(1)
