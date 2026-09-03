"""Independent set-based train-identity count replay. No producer imports."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(report_path):
    r=json.loads(report_path.read_text())
    base=Path('/research/d7/spc/yzyang4')
    paths=[base/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
           base/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
           Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl')]
    hashes=['0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e',
            '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb',
            'd9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010']
    for p,h in zip(paths,hashes):
        state=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1<<20),b''): state.update(chunk)
        assert state.hexdigest()==h==r['bindings'][str(p)]
    def pairs(p):
        out=[]
        with p.open() as f:
            for line in f:
                row=json.loads(line); assert row['intask_split']=='train'
                pair=frozenset((row['better'],row['worse'])); assert len(pair)==2
                out.append(pair)
        return out
    local,global_rows=pairs(paths[0]),pairs(paths[2])
    grouped=json.loads(paths[1].read_text()); metadata={}
    for run,cards in grouped.items():
        for c in cards:
            assert c['id'] not in metadata
            metadata[c['id']]=(run,c['task']['name'])
    local_nodes=set().union(*local); local_runs={metadata[n][0] for n in local_nodes}
    universe=set(range(len(global_rows)))
    known={i for i,p in enumerate(global_rows) if p<=metadata.keys()}
    same_task={i for i in known if len({metadata[n][1] for n in global_rows[i]})==1}
    in_scope={i for i in same_task if {metadata[n][0] for n in global_rows[i]}<=local_runs}
    overlap={i for i in in_scope if global_rows[i] in set(local)}
    remaining=in_scope-overlap
    partition={'missing_card_identity':len(universe-known),'cross_task_pair':len(known-same_task),
        'outside_local_train_run_boundary':len(same_task-in_scope),'same_unordered_pair_as_local':len(overlap),
        'within_boundary_nonlocal_pair':len(remaining)}
    assert {k:v for k,v in partition.items() if v}==r['exclusive_partition_counts']
    unique={global_rows[i] for i in remaining}; nodes=set().union(*unique) if unique else set()
    expected={'proposed_unique_global_pairs':len(unique),'proposed_global_endpoints':len(nodes),
        'proposed_global_runs':len({metadata[n][0] for n in nodes}),
        'proposed_global_tasks':len({metadata[n][1] for n in nodes}),
        'proposed_additional_endpoint_ids':len(nodes-local_nodes),'shared_endpoint_ids_with_local':len(nodes&local_nodes),
        'proposed_repeated_unordered_rows':len(remaining)-len(unique),
        'global_source_repeated_unordered_rows':len(global_rows)-len(set(global_rows)),
        'local_repeated_unordered_rows_across_budgets':len(local)-len(set(local))}
    for k,v in expected.items(): assert r[k]==v,k
    assert sum(partition.values())==len(global_rows) and r['partition_covers_all_rows']
    assert r['new_train_pool_created'] is False and r['effect_authorized'] is False
    return {'status':'PASS_INDEPENDENT_IDENTITY_PARTITION_ONLY','recomputed':expected,
        'exclusive_partition_counts':partition,'new_train_pool_created':False,'model_fits':0,
        'producer_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--report',required=True,type=Path)
    print(json.dumps(verify(p.parse_args().report.resolve()),sort_keys=True))
