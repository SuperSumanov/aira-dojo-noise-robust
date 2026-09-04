"""Follow-up after reuse support: annotate source defects and cached input cost.

Counts ALL reuse edges and all four source/config cells; no cell is promoted to a
training pool. Reuses two independently implemented provenance projections.
"""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from phase1.historical_label_reuse_support import INPUTS, checked, install_guard, pairs, project, analyze, check
from phase1.historical_global_local_source_gate import project_cards, project_batches, summarize
from phase1.verify_historical_global_local_source_gate import recompute

BASE=Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1')
EXTRA={
 'batches':(BASE/'run_batch_manifest.jsonl','60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'),
 'manifest':(BASE/'sha256_manifest.json','e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'),
 'lengths':(Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv'),'789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a'),
 'support':(Path('/tmp/gl-label-reuse-20260904-HB29tF/results/producer_a.json'),'8b797c29659358473f3412b9ce5e7bd52f5af06ed756987cf31fabc7605ca21c')}


def length_map(local, rows):
    ids=sorted({v for edge in local for v in edge})
    check(len(rows)==len(ids), 'length_coverage')
    result={}
    for i,(cid,row) in enumerate(zip(ids,rows)):
        check(set(row)=={'ordinal','raw_tokens','valid_tokens','encoding_sha256'}, 'length_schema')
        check(int(row['ordinal'])==i, 'length_order')
        raw,valid=int(row['raw_tokens']),int(row['valid_tokens'])
        check(raw>0 and valid==min(raw,16384), 'invalid_length')
        check(len(row['encoding_sha256'])==64 and all(c in '0123456789abcdef' for c in row['encoding_sha256']), 'encoding_digest')
        result[cid]=valid
    return result


def annotate(edges,cards,batches):
    keys=('equal_config_unique_source','equal_config_unresolved_source',
          'unequal_config_unique_source','unequal_config_unresolved_source')
    by_cell={k:[] for k in keys}
    for a,b in edges:
        same=cards[a][2]==cards[b][2]
        unique=all(batches[cards[x][0]][1]=='unique' for x in (a,b))
        key=('equal' if same else 'unequal')+'_config_'+('unique_source' if unique else 'unresolved_source')
        by_cell[key].append((a,b))
    # Independent set/intersection construction of the four cells.
    all_edges=set(edges)
    equal={e for e in all_edges if cards[e[0]][2]==cards[e[1]][2]}
    unresolved={e for e in all_edges if any(batches[cards[x][0]][1]!='unique' for x in e)}
    sets=(equal-unresolved,equal&unresolved,(all_edges-equal)-unresolved,(all_edges-equal)&unresolved)
    check(all(set(by_cell[k])==value for k,value in zip(keys,sets)), 'joint_cell_mismatch')
    return {k:dict(pairs=len(es),endpoints=len({v for e in es for v in e}),
        tasks=len({cards[a][1] for a,b in es}),
        anonymous_task_pair_counts=sorted(Counter(cards[a][1] for a,b in es).values())) for k,es in by_cell.items()}


def costs(local,reuse,lengths):
    # Pairwise summation and independent endpoint-degree dot products.
    def total(edges):
        direct=sum(lengths[a]+lengths[b] for a,b in edges)
        degree=Counter(v for e in edges for v in e)
        check(direct==sum(n*lengths[v] for v,n in degree.items()), 'cost_arithmetic_disagrees')
        return direct
    l,g=total(local),total(reuse)
    return dict(local_once_valid_tokens=l,reuse_global_once_valid_tokens=g,
        hypothetical_reuse_then_local_tokens=l+g,original_candidate_then_local_tokens=104863947,
        hypothetical_token_fraction_of_original=(l+g)/104863947,
        hypothetical_token_reduction_fraction=1-(l+g)/104863947,
        hypothetical_pair_visits=len(local)+len(reuse),unique_endpoints=len(lengths),
        new_endpoints_over_local=0,tokenizer_reruns=0,model_fits=0,
        equal_gpu_time_or_equal_effect_claimed=False,new_budget_adopted=False)


def main():
    opened=install_guard([p for p,h in EXTRA.values()])
    for p,h in [*INPUTS.values(),*EXTRA.values()]: checked(p,h)
    local=pairs([json.loads(x) for x in INPUTS['local'][0].read_text().splitlines()])
    glob=pairs([json.loads(x) for x in INPUTS['global'][0].read_text().splitlines()])
    grouped=json.loads(INPUTS['cards'][0].read_text()); run_of,task_of=project(grouped)
    support=json.loads(EXTRA['support'][0].read_text())
    check(analyze(local,glob,run_of,task_of)==support['metrics'],'support_projection_drift')
    ids={v for edge in local for v in edge}; le=set(local)
    reuse=[e for e in glob if set(e)<=ids and e not in le and task_of[e[0]]==task_of[e[1]]]
    check(len(reuse)==3058, 'reuse_count_drift')
    cards=project_cards(grouped)
    batch_rows=[json.loads(x) for x in EXTRA['batches'][0].read_text().splitlines()]
    batches=project_batches(batch_rows)
    check(json.loads(EXTRA['manifest'][0].read_text())['run_batch_manifest.jsonl']==EXTRA['batches'][1], 'upstream_manifest_drift')
    primary=summarize(reuse,local,cards,batches)
    wrap=lambda edges:[dict(better=a,worse=b,intask_split='train') for a,b in edges]
    independent=recompute(grouped,batch_rows,wrap(reuse),wrap(local))
    check(primary==independent, 'independent_source_projection_mismatch')
    with EXTRA['lengths'][0].open(newline='') as f:
        lengths=length_map(local,list(csv.DictReader(f)))
    budget=costs(local,reuse,lengths)
    check(budget['local_once_valid_tokens']==32187742 and len(lengths)==4095, 'cached_local_cost_binding')
    cells=annotate(reuse,cards,batches)
    check(sum(v['pairs'] for v in cells.values())==len(reuse), 'joint_cell_total')
    for p,h in [*INPUTS.values(),*EXTRA.values()]: checked(p,h,scan=False)
    return dict(status='REUSE_COST_SOURCE_DIAGNOSTIC_NOT_TRAINING_AUTHORIZATION',
        inputs={k:h for k,(_,h) in {**INPUTS,**EXTRA}.items()},
        reused_global_source=primary['global_candidate'],joint_source_config_cells=cells,
        cached_input_cost=budget,independent_source_projection_equal=True,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),data_open_counts=dict(opened),
        unresolved_local_source_pairs=primary['local']['unresolved_source_pairs'],
        producer_config_attested=False,experiment_closed_split_verified=False,
        pool_written=False,source_gate_relaxed=False,protected_cohort_files_opened=0,model_fits=0,new_gpu_jobs=0,api_calls=0)


if __name__=='__main__':
    try: print(json.dumps(main(),sort_keys=True))
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED',exception_type=type(exc).__name__)))
        raise SystemExit(1)
