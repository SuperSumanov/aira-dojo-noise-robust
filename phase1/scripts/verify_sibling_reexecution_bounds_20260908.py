"""Independent metadata verification with subset DP, not sorting group costs."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4')
FILES = {
    'lineage': ('historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json', 'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'),
    'scope': ('historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json', 'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b'),
    'pack': ('historical-program-pack-f702ba2-r2-20260907/A-pack.private.json', '0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7'),
}


def main():
    raw, d = {}, {}
    for name, (relative, sha) in FILES.items():
        blob = (ROOT / relative).read_bytes()
        assert len(blob) <= 64 * 1024 * 1024 and hashlib.sha256(blob).hexdigest() == sha
        assert not re.search(rb'(?i)sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}', blob)
        raw[name], d[name] = blob, json.loads(blob)
    scope = set(d['scope']['selected_runs'])
    assert len(scope) == 84 and set(d['pack']) == scope
    components, tasks, group_members, group_seconds = {}, defaultdict(set), defaultdict(list), {}
    for rid, run in d['pack'].items():
        closure = d['lineage']['closure'][rid]
        c = closure['component_sha256']
        assert closure['old_hold_closure_blocks_train'] is False and run['source_admitted'] is False
        assert run['component_sha256'] == c
        components[rid] = c
        tasks[run['task']].add(c)
        steps = {node['step'] for node in run['nodes']}
        assert len(steps) == len(run['nodes'])
        for n in run['nodes']:
            if n['nonempty_code'] and len(n['parents']) == 1 and n['parents'][0] in steps:
                assert n['parents'][0] < n['step']
                key = (rid, n['parents'][0])
                group_members[key].append(n['code_sha256'])
                group_seconds[key] = run['full_execution_timeout']
    for rid, c in d['lineage']['closure'].items():
        if c['component_sha256'] in set(components.values()):
            assert rid in scope
    counts = Counter()
    # DP state records best/worst cost of exactly j complete groups in a component.
    low = {c: [0, None, None, None, None] for c in set(components.values())}
    high = {c: [0, None, None, None, None] for c in set(components.values())}
    qualified = programs = 0
    for (rid, parent), hashes in group_members.items():
        if len(hashes) < 2 or len(set(hashes)) < 2:
            continue
        qualified += 1
        programs += len(hashes)
        c = components[rid]
        counts[c] += 1
        cost = len(hashes) * group_seconds[(rid, parent)]
        assert type(cost) is int and cost > 0
        for j in range(4, 0, -1):
            if low[c][j-1] is not None:
                candidate = low[c][j-1] + cost
                low[c][j] = candidate if low[c][j] is None else min(candidate, low[c][j])
            if high[c][j-1] is not None:
                candidate = high[c][j-1] + cost
                high[c][j] = candidate if high[c][j] is None else max(candidate, high[c][j])
    scenarios = []
    for k in (1, 2, 4):
        rows = []
        for task in sorted(tasks):
            cs = tasks[task]
            if len(cs) < 2:
                continue
            possible = [c for c in cs if counts[c] >= k]
            rows.append(dict(task=task, conservative_components=len(cs),
                possible_dev_components=len(possible), available_complete_groups=sum(counts[c] for c in cs),
                min_cap_gpu_seconds=min((low[c][k] for c in possible), default=None),
                max_cap_gpu_seconds=max((high[c][k] for c in possible), default=None)))
        supported = [r for r in rows if r['possible_dev_components']]
        scenarios.append(dict(groups_per_hypothetical_dev_component=k, task_rows=rows,
            supported_tasks=len(supported), min_sum_cap_gpu_seconds=sum(r['min_cap_gpu_seconds'] for r in supported),
            max_sum_cap_gpu_seconds=sum(r['max_cap_gpu_seconds'] for r in supported)))
    for name, (relative, _) in FILES.items():
        assert (ROOT / relative).read_bytes() == raw[name]
    print(json.dumps(dict(classification='INDEPENDENT_SUBSET_DP_METADATA_BOUNDS',
        input_sha256={n:s[1] for n,s in FILES.items()},
        qualified_complete_nonempty_sibling_groups=qualified,
        program_instances_in_qualified_groups=programs,
        scenarios=scenarios, selected_programs=0, executed_programs=0, source_admitted=False), sort_keys=True))


if __name__ == '__main__':
    main()
