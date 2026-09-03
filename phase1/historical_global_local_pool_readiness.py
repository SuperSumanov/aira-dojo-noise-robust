"""Historical train identity intersection only; never creates a training pool.

Output is aggregate. Does not read grade/gap/outcome fields, select a checkpoint,
or evaluate a model. The source global train was historical schema-smoke input,
NOT eligible by itself for the frozen effect experiment.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

from phase1.historical_train_encoding_readiness import TRAIN, CARDS, EXPECTED, checked_digest

GLOBAL=Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl')
GLOBAL_SHA='d9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'


def project_pairs(raw):
    pairs=[]
    for line in raw.splitlines():
        row=json.loads(line)
        if row.get('intask_split')!='train': raise ValueError('non_train_row')
        a,b=row['better'],row['worse']
        if not all(isinstance(x,str) and x for x in (a,b)) or a==b:
            raise ValueError('invalid_endpoint')
        pairs.append(tuple(sorted((a,b))))
    if not pairs: raise ValueError('empty_pairs')
    return pairs


def summarize(global_pairs,local_pairs,card_runs,card_tasks):
    # The proposed scope is already approved historical L-train runs only.
    # This is a coverage diagnostic, not adoption of that scope for v2.
    local_ids={x for p in local_pairs for x in p}
    if not local_ids<=card_runs.keys(): raise ValueError('local_missing_card')
    local_runs={card_runs[x] for x in local_ids}
    local_unordered=set(local_pairs)
    reason=Counter(); proposed=[]
    for a,b in global_pairs:
        if a not in card_runs or b not in card_runs: reason['missing_card_identity']+=1
        elif card_tasks[a]!=card_tasks[b]: reason['cross_task_pair']+=1
        elif card_runs[a] not in local_runs or card_runs[b] not in local_runs:
            reason['outside_local_train_run_boundary']+=1
        elif (a,b) in local_unordered: reason['same_unordered_pair_as_local']+=1
        else: reason['within_boundary_nonlocal_pair']+=1; proposed.append((a,b))
    c=Counter(proposed)
    proposed_ids={x for p in proposed for x in p}
    return {'global_source_rows':len(global_pairs),'local_source_rows':len(local_pairs),
        'local_train_endpoints':len(local_ids),'local_train_runs':len(local_runs),
        'global_source_repeated_unordered_rows':len(global_pairs)-len(set(global_pairs)),
        'local_repeated_unordered_rows_across_budgets':len(local_pairs)-len(local_unordered),
        'exclusive_partition_counts':dict(sorted(reason.items())),
        'proposed_unique_global_pairs':len(c),'proposed_repeated_unordered_rows':sum(n-1 for n in c.values()),
        'proposed_global_endpoints':len(proposed_ids),'proposed_global_runs':len({card_runs[x] for x in proposed_ids}),
        'proposed_global_tasks':len({card_tasks[x] for x in proposed_ids}),
        'shared_endpoint_ids_with_local':len(proposed_ids&local_ids),
        'proposed_additional_endpoint_ids':len(proposed_ids-local_ids),
        'proposed_unique_global_remainder_at_128':len(c)%128,
        'partition_covers_all_rows':sum(reason.values())==len(global_pairs)}


def run():
    allowed={p.resolve() for p in (TRAIN,CARDS,GLOBAL)}; opened=Counter()
    def audit(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):
            raise PermissionError('offline_identity_check')
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)): return
        p=Path(os.fsdecode(args[0])).resolve()
        mode,flags=args[1],args[2]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            raise PermissionError('read_only_identity_check')
        if p in allowed: opened[str(p)]+=1
        elif p.suffix in ('.json','.jsonl','.csv','.pt','.safetensors'):
            raise PermissionError('unlisted_data_read')
    sys.addaudithook(audit)
    bindings={str(p):checked_digest(p,h,scan=True) for p,h in
              ((TRAIN,EXPECTED[TRAIN]),(CARDS,EXPECTED[CARDS]),(GLOBAL,GLOBAL_SHA))}
    g,l=project_pairs(GLOBAL.read_text()),project_pairs(TRAIN.read_text())
    if len(g)!=14206 or len(l)!=4689: raise ValueError('source_count_mismatch')
    grouped=json.loads(CARDS.read_text()); runs={}; tasks={}
    for run,cards in grouped.items():
        if not isinstance(run,str) or not run: raise ValueError('invalid_run')
        for card in cards:
            cid=card['id']
            if cid in runs: raise ValueError('duplicate_card')
            runs[cid]=run; tasks[cid]=card['task']['name']
    a=summarize(g,l,runs,tasks)
    # Input-orientation and file-order invariance; not an effect rerun.
    b=summarize(list(reversed(g)),list(reversed(l)),runs,tasks)
    if a!=b: raise ValueError('order_dependent_identity_diagnostic')
    for p,h in ((TRAIN,EXPECTED[TRAIN]),(CARDS,EXPECTED[CARDS]),(GLOBAL,GLOBAL_SHA)):
        checked_digest(p,h)
    return {'status':'HISTORICAL_IDENTITY_DIAGNOSTIC_NOT_EFFECT_ELIGIBILITY',
        'base_commit':'7677501b66859284f41545f39a1f00469b20ee4f',
        'source_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'bindings':bindings,**a,'new_train_pool_created':False,'effect_authorized':False,
        'data_open_counts':dict(opened),'python_audit_not_os_sandbox':True,
        'exact_producer_config_verified':False,'experiment_closed_split_verified':False,
        'dev_test_vault_files_opened':0,'model_fits':0,'gpu_jobs':0,'api_calls':0}


if __name__=='__main__':
    argparse.ArgumentParser().parse_args()
    try: print(json.dumps(run(),sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','exception_type':type(exc).__name__}))
        raise SystemExit(1)
