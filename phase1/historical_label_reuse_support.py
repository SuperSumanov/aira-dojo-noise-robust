"""Historical, label-blind support for an execution-label-matched transfer control.

No training pool is written or approved. Existing G candidate membership is kept;
its structural intersections are counted, never used to repair source eligibility.
The aggregate is not a model result or a claim of independent comparison labels.
"""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys

BASE = Path('/research/d7/spc/yzyang4')
INPUTS = {
    'local': (BASE/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
              '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
    'global': (Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl'),
               'd9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'),
    'cards': (BASE/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
              '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb'),
}
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def check(ok, code):
    if not ok:
        raise ValueError(code)


def install_guard(extra=()):
    allowed = {p.absolute() for p, _ in INPUTS.values()} | {Path(p).absolute() for p in extra}
    counts = Counter()
    def hook(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('no_network_or_process')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).absolute()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write:
            raise PermissionError('read_only_diagnostic')
        if p in allowed:
            check(p.resolve() == p, 'unresolved_or_linked_input')
            counts[str(p)] += 1
        elif p.suffix not in ('.py', '.pyc'):
            raise PermissionError('unlisted_data')
    sys.addaudithook(hook)
    return counts


def checked(path, digest, scan=True):
    check(path.is_file() and not path.is_symlink() and path.stat().st_size <= 650*1024**2, 'unsafe_input')
    h, tail = hashlib.sha256(), b''
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4*1024**2), b''):
            h.update(block)
            if scan:
                check(not CREDENTIAL.search(tail+block), 'credential_shape')
                tail = block[-1024:]
    check(h.hexdigest() == digest, 'input_hash_drift')


def pairs(rows):
    out = []
    for row in rows:
        check(row.get('intask_split') == 'train', 'non_train_row')
        a, b = row['better'], row['worse']
        check(all(isinstance(x, str) and x for x in (a,b)) and a != b, 'invalid_endpoint')
        out.append(tuple(sorted((a,b))))
    check(len(out) == len(set(out)) and len(out)>0, 'empty_or_repeated_pair')
    return out


def project(grouped):
    run_of, task_of = {}, {}
    for run, cards in grouped.items():
        check(isinstance(run, str) and bool(run), 'invalid_run')
        for card in cards:
            cid, task = card['id'], card['task']['name']
            check(isinstance(cid, str) and cid and cid not in run_of, 'duplicate_or_invalid_card')
            check(isinstance(task, str) and task, 'invalid_task')
            run_of[cid], task_of[cid] = run, task
    return run_of, task_of


def components(edges):
    parent = {v:v for e in edges for v in e}
    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    for a,b in edges:
        a,b = find(a),find(b)
        if a!=b:
            parent[max(a,b)] = min(a,b)
    return {v:find(v) for v in parent}


def graph(edges):
    groups = components(edges)
    rank = len(groups)-len(set(groups.values()))
    return dict(edges=len(edges), endpoints=len(groups), components=len(set(groups.values())),
                incidence_rank=rank, cycle_edges=len(edges)-rank)


def exposure(edges):
    counts = Counter(v for edge in edges for v in edge)
    values = sorted(counts.values(), reverse=True)
    total = sum(values)
    if not total:
        return dict(endpoint_visits=0, unique_endpoints=0, max_visits=0, median_visits=0,
                    top_decile_endpoint_visit_share=None)
    return dict(endpoint_visits=total, unique_endpoints=len(values), max_visits=values[0],
                median_visits=statistics.median(values),
                top_decile_endpoint_visit_share=sum(values[:(len(values)+9)//10])/total)


def analyze(local, global_all, run_of, task_of):
    local_ids = {v for edge in local for v in edge}
    check(local_ids <= run_of.keys(), 'local_missing_identity')
    check(len(local)==len(set(local)) and len(global_all)==len(set(global_all)), 'repeated_pair')
    check(all(task_of[a]==task_of[b] for a,b in local), 'local_cross_task')
    local_runs = {run_of[v] for v in local_ids}
    local_edges = set(local)
    candidate, exclusions = [], Counter()
    for a,b in global_all:
        if a not in run_of or b not in run_of:
            exclusions['missing_card_identity'] += 1
        elif task_of[a] != task_of[b]:
            exclusions['cross_task_pair'] += 1
        elif run_of[a] not in local_runs or run_of[b] not in local_runs:
            exclusions['outside_local_train_run_boundary'] += 1
        elif (a,b) in local_edges:
            exclusions['same_unordered_pair_as_local'] += 1
        else:
            candidate.append((a,b))
    partitions = {0:[],1:[],2:[]}
    for edge in candidate:
        partitions[sum(v in local_ids for v in edge)].append(edge)
    reuse = partitions[2]
    labels = {0:'both_endpoints_additional',1:'one_endpoint_additional',2:'both_endpoints_already_local'}
    partition_counts = {labels[k]:len(v) for k,v in partitions.items()}
    check(sum(partition_counts.values()) == len(candidate), 'partition_mismatch')
    component_of = components(local)
    inside = sum(component_of[a]==component_of[b] for a,b in reuse)
    candidate_ids = {v for e in candidate for v in e}
    reuse_ids = {v for e in reuse for v in e}
    per_task = defaultdict(lambda:dict(local_pairs=0, global_candidate_pairs=0, reusable_global_pairs=0))
    for key, edges in [('local_pairs',local),('global_candidate_pairs',candidate),('reusable_global_pairs',reuse)]:
        for a,b in edges:
            per_task[task_of[a]][key] += 1
    # Only anonymous counts leave the process, not task/card/run identities.
    task_rows = sorted(per_task.values(), key=lambda r:(r['local_pairs'],r['global_candidate_pairs'],r['reusable_global_pairs']))
    lgraph, union = graph(local), graph(local+reuse)
    return dict(local_pairs=len(local), global_source_pairs=len(global_all),
        global_candidate_pairs=len(candidate), source_exclusions=dict(sorted(exclusions.items())),
        local_endpoints=len(local_ids), global_candidate_endpoints=len(candidate_ids),
        additional_global_endpoints=len(candidate_ids-local_ids),
        global_endpoint_partition=partition_counts,
        reusable_global_pairs=len(reuse), reusable_endpoint_coverage=len(reuse_ids),
        reusable_endpoint_coverage_fraction=len(reuse_ids)/len(local_ids),
        reused_within_local_component_pairs=inside, reused_between_local_component_pairs=len(reuse)-inside,
        local_graph=lgraph, reusable_global_graph=graph(reuse), local_plus_reusable_graph=union,
        additional_incidence_rank=union['incidence_rank']-lgraph['incidence_rank'],
        local_exposure=exposure(local), reusable_exposure=exposure(reuse),
        local_plus_reusable_exposure=exposure(local+reuse),
        tasks=len(per_task), tasks_with_reusable_pairs=sum(r['reusable_global_pairs']>0 for r in task_rows),
        tasks_with_at_least_20_reusable_pairs=sum(r['reusable_global_pairs']>=20 for r in task_rows),
        anonymous_task_counts=task_rows,
        reusable_pair_cross_grouped_run_count=sum(run_of[a]!=run_of[b] for a,b in reuse),
        candidate_scope_was_not_changed=True, new_pool_materialized=False, effect_eligible=False)


def main():
    opened = install_guard()
    for path,digest in INPUTS.values():
        checked(path,digest)
    local = pairs([json.loads(line) for line in INPUTS['local'][0].read_text().splitlines()])
    global_all = pairs([json.loads(line) for line in INPUTS['global'][0].read_text().splitlines()])
    run_of,task_of = project(json.loads(INPUTS['cards'][0].read_text()))
    check(len(local)==4689 and len(global_all)==14206, 'input_size_mismatch')
    metrics = analyze(local,global_all,run_of,task_of)
    check(metrics['global_candidate_pairs']==9392, 'existing_candidate_drift')
    check(metrics == analyze(list(reversed(local)),list(reversed(global_all)),run_of,task_of), 'order_drift')
    for path,digest in INPUTS.values():
        checked(path,digest,scan=False)
    return dict(status='HISTORICAL_LABEL_REUSE_SUPPORT_ONLY_NOT_EFFECT',
        input_sha256={k:h for k,(_,h) in INPUTS.items()}, metrics=metrics,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        data_open_counts=dict(opened), guard='Python audit hook, not OS sandbox',
        real_labels_used_for_selection=False, scores_or_predictions_used=False,
        new_gpu_jobs=0, api_calls=0, model_fits=0, protected_cohort_files_opened=0,
        limitations=['Structural counts are not statistical independence or model effect.',
                    'No additional endpoints does not prove actual marginal execution cost without producer receipts.',
                    'Historical source/config and experiment-closed gates remain unresolved.',
                    'No frozen protocol, training input, label or checkpoint is changed.'])


if __name__ == '__main__':
    try:
        print(json.dumps(main(),sort_keys=True))
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED',exception_type=type(exc).__name__)))
        raise SystemExit(1)
