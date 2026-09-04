"""One predeclared label-blind structural experiment; no train pool or fit."""
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from phase1.fixed_forward_rewire import plan, verify, require
from phase1.historical_label_reuse_support import INPUTS, checked, pairs, install_guard
from phase1.global_local_execution_plan import BatchShape, Endpoint, Pair, digest_records
from phase1.global_local_token_budget_plan import _ordered_pool, _layout

ROOT = Path(__file__).resolve().parent
BINDINGS = {k: INPUTS[k] for k in ('local', 'cards')}
BINDINGS.update({
    'lengths': (Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv'),
                '789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a'),
    'old_plan': (ROOT/'results/global_local_token_plan_20260904/summary.json',
                 'c40f9b696530c2303c5129fa5571a2ffc484986472d1962871170d30a509043b'),
    'frozen': (ROOT/'global_local_calibration_candidate_protocol_v2.json',
               '3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9'),
    'historical': (ROOT/'global_local_historical_development_protocol_v1.json',
                   '1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902'),
})
CONTRACT = dict(version='fixed-forward-structural-v1-20260905',seeds=[6,7,8],
    shapes=[[2,8,8],[4,8,4]],modes=['legacy','stratum_shared'],
    minimum_changed_fraction=0.10,minimum_tasks=10,minimum_changed_pairs_per_task=20,
    selection='canonical forest retained; first eligible pair-slot double swap',
    new_budget_adopted=False,model_fits=0)


def main():
    opened = install_guard([p for p,_ in BINDINGS.values()])
    for path,sha in BINDINGS.values():checked(path,sha)
    local = pairs([json.loads(line) for line in BINDINGS['local'][0].read_text().splitlines()])
    grouped=json.loads(BINDINGS['cards'][0].read_text())
    task, stratum = {}, {}
    for run,cards in grouped.items():
        require(isinstance(run,str) and run, 'invalid_run')
        for card in cards:
            cid, name = card['id'],card['task']['name']
            require(isinstance(cid,str) and cid and cid not in task and isinstance(name,str) and name,'invalid_metadata')
            values=tuple(card.get(k) for k in ('client','hardware','time_limit','execution_timeout'))
            task[cid]=name
            stratum[cid]=json.dumps((name,values),sort_keys=True,separators=(',',':'),allow_nan=False) if all(v is not None and v!='' for v in values) else None
    del grouped
    ids=sorted({v for e in local for v in e})
    require(len(local)==4689 and len(ids)==4095 and set(ids)<=task.keys(),'fixed_input_counts')
    require(all(task[a]==task[b] for a,b in local),'cross_task_local')
    with BINDINGS['lengths'][0].open(newline='') as handle:cache=list(csv.DictReader(handle))
    require(len(cache)==len(ids),'cache_coverage')
    endpoints={}
    for i,(cid,row) in enumerate(zip(ids,cache)):
        require(set(row)=={'ordinal','raw_tokens','valid_tokens','encoding_sha256'} and int(row['ordinal'])==i,'cache_binding')
        raw,valid=int(row['raw_tokens']),int(row['valid_tokens'])
        require(raw>0 and valid==min(raw,16384),'cache_length')
        endpoints[cid]=Endpoint(cid,valid,row['encoding_sha256'])
    old=json.loads(BINDINGS['old_plan'][0].read_text())['input_bindings']
    require(old['local_train_sha256']==BINDINGS['local'][1] and old['grouped_cards_sha256']==BINDINGS['cards'][1],'encoder_source_binding')
    rows=tuple(Pair.canonical('L',endpoints[a],endpoints[b],digest_records([(old['serialization_binding_sha256'],task[a])])) for a,b in local)
    results=[]
    for seed in CONTRACT['seeds']:
        legacy=_ordered_pool(rows,'L',seed)
        groups=defaultdict(list)
        for row in legacy:
            # Shared ordering for BOTH arms; not a modification to frozen legacy.
            key=(task[row.a.card_id],stratum[row.a.card_id],stratum[row.b.card_id])
            groups[key].append(row)
        shared=tuple(row for key in sorted(groups,key=lambda k:digest_records([('shared-stratum',seed,k)])) for row in groups[key])
        require(Counter(r.key for r in shared)==Counter(r.key for r in legacy),'shared_order_loss')
        for mode,ordered in [('legacy',legacy),('stratum_shared',shared)]:
            for shape_values in CONTRACT['shapes']:
                shape=BatchShape(*shape_values)
                _,descriptors=_layout([('L',0,ordered)],shape,1)
                before=digest_records(asdict(b) for b in descriptors)
                batches=tuple(tuple((row.a.card_id,row.b.card_id) for row in b.rows) for b in descriptors)
                candidate=plan(batches,stratum)
                counts=verify(batches,stratum,candidate)
                require(before==digest_records(asdict(b) for b in descriptors),'forward_descriptor_mutated')
                by_task=Counter()
                for batch,indices in zip(batches,candidate.losses):
                    flat=[v for e in batch for v in e]
                    original={tuple(sorted(e)) for e in batch}
                    for i,j in indices:
                        a,b=flat[i],flat[j]
                        if tuple(sorted((a,b))) not in original:by_task[task[a]]+=1
                require(sum(by_task.values())==counts['changed_pairs'],'task_count')
                task_support=sum(n>=CONTRACT['minimum_changed_pairs_per_task'] for n in by_task.values())
                decision=(counts['changed_fraction']>=CONTRACT['minimum_changed_fraction'] and task_support>=CONTRACT['minimum_tasks'])
                results.append(dict(seed=seed,mode=mode,shape=shape_values,**counts,
                    changed_tasks=len(by_task),tasks_with_at_least_20_changed_pairs=task_support,
                    anonymous_task_changed_counts=sorted(by_task.values(),reverse=True),
                    maximum_task_share=max(by_task.values(),default=0)/max(1,counts['changed_pairs']),
                    forward_descriptor_sha256=before,loss_indices_sha256=digest_records(candidate.losses),
                    valid_tokens=sum(b.valid_tokens for b in descriptors),
                    padded_slots=sum(b.padded_slots for b in descriptors),
                    optimizer_updates=len({b.optimizer_step for b in descriptors}),
                    local_microbatches=len(descriptors),priority_gate_passed=decision))
    for path,sha in BINDINGS.values():checked(path,sha,scan=False)
    require(set(opened)<={str(p.absolute()) for p,_ in BINDINGS.values()},'unexpected_data_read')
    primary=[r for r in results if r['mode']=='stratum_shared']
    return dict(status='STRUCTURAL_ONLY_NOT_EFFECT',contract=CONTRACT,
        input_sha256={k:s for k,(_,s) in BINDINGS.items()},results=results,
        primary_all_cells_priority_gate_passed=all(r['priority_gate_passed'] for r in primary),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        data_open_counts=dict(opened),guard='Python audit hook, not OS sandbox',
        historical_container_unused_fields_parsed=True,grade_gap_orientation_used_for_selection=False,
        source_config_gate_passed=False,experiment_closed_gate_passed=False,
        pool_written=False,new_budget_adopted=False,model_fits=0,model_weights_loaded=0,
        new_gpu_jobs=0,api_calls=0,protected_cohort_files_opened=0,
        real_forward_state_equivalence_tested=False,new_comparison_labels_bound=False)


if __name__=='__main__':
    try:print(json.dumps(main(),sort_keys=True,allow_nan=False))
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED',exception_type=type(exc).__name__)))
        raise SystemExit(1)
