"""Independent set/BFS recomputation; never imports the producer."""
import argparse
from collections import defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys

ROOT=Path('/research/d7/spc/yzyang4')
FILES={
 'local':(ROOT/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl','0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
 'global':(Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl'),'d9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'),
 'cards':(ROOT/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json','5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb')}


def inventory(edges):
    adj=defaultdict(set)
    for a,b in edges:
        adj[a].add(b); adj[b].add(a)
    assigned={}; component=0
    for node in sorted(adj):
        if node in assigned:
            continue
        q=deque([node]); assigned[node]=component
        while q:
            for neighbor in adj[q.popleft()]:
                if neighbor not in assigned:
                    assigned[neighbor]=component; q.append(neighbor)
        component+=1
    rank=len(adj)-component
    return assigned,dict(edges=len(edges),endpoints=len(adj),components=component,
                         incidence_rank=rank,cycle_edges=len(edges)-rank)


def visits(edges):
    degree=defaultdict(int)
    for a,b in edges:
        degree[a]+=1; degree[b]+=1
    if not degree:
        return dict(endpoint_visits=0,unique_endpoints=0,max_visits=0,median_visits=0,top_decile_endpoint_visit_share=None)
    values=sorted(degree.values()); top=(len(values)+9)//10
    return dict(endpoint_visits=sum(values),unique_endpoints=len(values),max_visits=max(values),
                median_visits=statistics.median(values),top_decile_endpoint_visit_share=sum(values[-top:])/sum(values))


def recompute(local_rows, global_rows, grouped):
    run_of={}; task_of={}
    for run,records in grouped.items():
        for r in records:
            cid=r['id']
            if cid in run_of:
                raise ValueError('duplicate_card')
            run_of[cid]=run; task_of[cid]=r['task']['name']
    def read_pairs(rows):
        result=set()
        for r in rows:
            if r.get('intask_split')!='train' or r['better']==r['worse']:
                raise ValueError('not_train_or_self_edge')
            result.add(tuple(sorted((r['better'],r['worse']))))
        if len(result)!=len(rows) or not result:
            raise ValueError('empty_or_duplicate_pair')
        return result
    local=read_pairs(local_rows); global_all=read_pairs(global_rows)
    local_ids=set().union(*map(set,local))
    local_runs={run_of[v] for v in local_ids}
    if any(task_of[a]!=task_of[b] for a,b in local):
        raise ValueError('cross_task_local')
    missing={p for p in global_all if not set(p)<=run_of.keys()}
    available=global_all-missing
    cross={p for p in available if task_of[p[0]]!=task_of[p[1]]}
    outside={p for p in available-cross if not {run_of[v] for v in p}<=local_runs}
    overlap=(available-cross-outside)&local
    candidates=global_all-missing-cross-outside-overlap
    partitions={i:{p for p in candidates if len(set(p)&local_ids)==i} for i in (0,1,2)}
    reuse=partitions[2]; union=local|reuse
    local_comp,lg=inventory(local); _,rg=inventory(reuse); _,ug=inventory(union)
    inside={p for p in reuse if local_comp[p[0]]==local_comp[p[1]]}
    reuse_ids=set().union(*map(set,reuse)) if reuse else set()
    candidate_ids=set().union(*map(set,candidates)) if candidates else set()
    all_tasks={task_of[v] for v in local_ids}
    task_rows=[]
    for t in all_tasks:
        task_rows.append(dict(local_pairs=sum(task_of[a]==t for a,b in local),
            global_candidate_pairs=sum(task_of[a]==t for a,b in candidates),
            reusable_global_pairs=sum(task_of[a]==t for a,b in reuse)))
    task_rows.sort(key=lambda r:(r['local_pairs'],r['global_candidate_pairs'],r['reusable_global_pairs']))
    exclusions={k:len(v) for k,v in [('missing_card_identity',missing),('cross_task_pair',cross),
        ('outside_local_train_run_boundary',outside),('same_unordered_pair_as_local',overlap)] if v}
    return dict(local_pairs=len(local),global_source_pairs=len(global_all),global_candidate_pairs=len(candidates),
        source_exclusions=exclusions,local_endpoints=len(local_ids),global_candidate_endpoints=len(candidate_ids),
        additional_global_endpoints=len(candidate_ids-local_ids),
        global_endpoint_partition={'both_endpoints_additional':len(partitions[0]),'one_endpoint_additional':len(partitions[1]),
                                   'both_endpoints_already_local':len(reuse)},
        reusable_global_pairs=len(reuse),reusable_endpoint_coverage=len(reuse_ids),
        reusable_endpoint_coverage_fraction=len(reuse_ids)/len(local_ids),
        reused_within_local_component_pairs=len(inside),reused_between_local_component_pairs=len(reuse-inside),
        local_graph=lg,reusable_global_graph=rg,local_plus_reusable_graph=ug,
        additional_incidence_rank=ug['incidence_rank']-lg['incidence_rank'],
        local_exposure=visits(local),reusable_exposure=visits(reuse),local_plus_reusable_exposure=visits(union),
        tasks=len(all_tasks),tasks_with_reusable_pairs=sum(r['reusable_global_pairs']>0 for r in task_rows),
        tasks_with_at_least_20_reusable_pairs=sum(r['reusable_global_pairs']>=20 for r in task_rows),
        anonymous_task_counts=task_rows,reusable_pair_cross_grouped_run_count=sum(run_of[a]!=run_of[b] for a,b in reuse),
        candidate_scope_was_not_changed=True,new_pool_materialized=False,effect_eligible=False)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--receipt',required=True); ap.add_argument('--sha256',required=True)
    args=ap.parse_args(); receipt=Path(args.receipt).absolute()
    allowed={p.absolute() for p,_ in FILES.values()}|{receipt}
    def hook(event,params):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):
            raise PermissionError('offline')
        if event!='open' or not isinstance(params[0],(str,bytes,os.PathLike)):
            return
        p=Path(os.fsdecode(params[0])).absolute(); mode,flags=params[1:3]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise PermissionError('no_writes')
        if p in allowed:
            if p.resolve()!=p:
                raise PermissionError('linked_input')
        elif p.suffix not in ('.py','.pyc'):
            raise PermissionError('unlisted_file')
    sys.addaudithook(hook)
    pattern=re.compile(rb'(?i)(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    def read(path,sha,cap):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:
            raise ValueError('unsafe_file')
        body=path.read_bytes()
        if hashlib.sha256(body).hexdigest()!=sha or pattern.search(body):
            raise ValueError('hash_or_credential_gate')
        return body
    payload=json.loads(read(receipt,args.sha256,128*1024))
    raw={k:read(p,h,650*1024**2) for k,(p,h) in FILES.items()}
    result=recompute([json.loads(x) for x in raw['local'].splitlines()],
                     [json.loads(x) for x in raw['global'].splitlines()],json.loads(raw['cards']))
    if payload['status']!='HISTORICAL_LABEL_REUSE_SUPPORT_ONLY_NOT_EFFECT' or result!=payload['metrics']:
        raise ValueError('independent_mismatch')
    if payload['input_sha256']!={k:h for k,(_,h) in FILES.items()}:
        raise ValueError('binding_mismatch')
    for key in ('new_gpu_jobs','api_calls','model_fits','protected_cohort_files_opened'):
        if payload[key]!=0:
            raise ValueError('scope_mismatch')
    for p,h in [*FILES.values(),(receipt,args.sha256)]:
        with p.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=h:
                raise ValueError('post_hash_drift')
    return dict(status='INDEPENDENT_LABEL_REUSE_SUPPORT_VERIFIED',receipt_sha256=args.sha256,
                metrics=result,input_sha256=payload['input_sha256'],model_fits=0,new_gpu_jobs=0)


if __name__=='__main__':
    try:
        print(json.dumps(main(),sort_keys=True))
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED',exception_type=type(exc).__name__)))
        raise SystemExit(1)
