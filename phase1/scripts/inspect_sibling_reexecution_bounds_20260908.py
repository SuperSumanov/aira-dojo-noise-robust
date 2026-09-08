"""Outcome-unused metadata bounds for a separately registered fresh-dev route.

No roles, tasks, components or programs are selected. No program/label files are
opened. Fixed inputs were already outcome-unused historical metadata projections.
The strict four-fit admission gate is not modified by these conditional bounds.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4')
INPUTS = {
    'lineage': ('historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json',
                'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'),
    'scope': ('historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json',
              'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b'),
    'pack': ('historical-program-pack-f702ba2-r2-20260907/A-pack.private.json',
             '0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7'),
}
K_VALUES = (1, 2, 4)
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def main():
    inputs, raw_inputs = {}, {}
    for name, (relative, sha) in INPUTS.items():
        path = ROOT / relative
        require(path.stat().st_size <= 64 * 1024 * 1024, 'metadata size cap')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == sha, 'input hash drift')
        require(not SECRET.search(raw), 'credential shape')
        raw_inputs[name], inputs[name] = raw, json.loads(raw)
    chosen = set(inputs['scope']['selected_runs'])
    pack, lineage = inputs['pack'], inputs['lineage']['closure']
    require(len(chosen) == 84 and set(pack) == chosen, 'fixed scope mismatch')
    component_runs, component_tasks, task_components = defaultdict(set), defaultdict(set), defaultdict(set)
    group_costs = defaultdict(list)
    diagnostic = defaultdict(int)
    total_programs = 0
    for rid in sorted(chosen):
        run, closure = pack[rid], lineage[rid]
        require(closure['old_hold_closure_blocks_train'] is False, 'old hold changed')
        require(run['source_admitted'] is False, 'source admission changed')
        component = closure['component_sha256']
        require(run['component_sha256'] == component, 'component join mismatch')
        cap = run['full_execution_timeout']
        require(type(cap) is int and cap > 0, 'invalid full timeout')
        task = run['task']
        component_runs[component].add(rid)
        component_tasks[component].add(task)
        task_components[task].add(component)
        by_step = {node['step']: node for node in run['nodes']}
        require(len(by_step) == len(run['nodes']), 'duplicate step')
        families = defaultdict(list)
        for node in run['nodes']:
            require(type(node['nonempty_code']) is bool, 'invalid nonempty flag')
            require(type(node['parents']) is list and all(type(p) is int for p in node['parents']), 'parent schema')
            total_programs += node['nonempty_code']
            if not node['nonempty_code']:
                diagnostic['empty_code_nodes'] += 1
                continue
            if len(node['parents']) != 1:
                diagnostic['nonempty_without_exactly_one_parent'] += 1
                continue
            parent = node['parents'][0]
            require(parent < node['step'], 'noncausal parent')
            if parent not in by_step:
                diagnostic['nonempty_missing_parent'] += 1
                continue
            families[parent].append(node)
        for children in families.values():
            if len(children) < 2:
                diagnostic['single_child_groups'] += 1
                continue
            if len({n['code_sha256'] for n in children}) < 2:
                diagnostic['all_identical_code_groups'] += 1
                continue
            # All nonempty children remain: no syntax/score/exit-status filter or
            # cheapest-child selection. Distinct-code presence defines a contrast.
            group_costs[component].append(len(children) * cap)
            diagnostic['qualified_complete_nonempty_sibling_groups'] += 1
            diagnostic['program_instances_in_qualified_groups'] += len(children)
    require(total_programs == 3447 and len(component_runs) == 24 and len(task_components) == 15,
            'scope support changed')
    require(all(len(tasks) == 1 for tasks in component_tasks.values()), 'cross-task component')
    for rid, closure in lineage.items():
        if closure['component_sha256'] in component_runs:
            require(rid in chosen, 'partial conservative component')

    scenarios = []
    for k in K_VALUES:
        rows = []
        for task, components in sorted(task_components.items()):
            if len(components) < 2:
                continue  # Need another whole component for hypothetical train role.
            eligible = [c for c in components if len(group_costs[c]) >= k]
            bounds = [(sum(sorted(group_costs[c])[:k]), sum(sorted(group_costs[c])[-k:])) for c in eligible]
            rows.append(dict(task=task, conservative_components=len(components),
                possible_dev_components=len(eligible),
                available_complete_groups=sum(len(group_costs[c]) for c in components),
                min_cap_gpu_seconds=min((a for a,b in bounds), default=None),
                max_cap_gpu_seconds=max((b for a,b in bounds), default=None)))
        supported = [r for r in rows if r['possible_dev_components']]
        low = sum(r['min_cap_gpu_seconds'] for r in supported)
        high = sum(r['max_cap_gpu_seconds'] for r in supported)
        scenarios.append(dict(groups_per_hypothetical_dev_component=k, task_rows=rows,
            supported_tasks=len(supported), hypothetical_dev_components=len(supported),
            min_sum_cap_gpu_seconds=low, max_sum_cap_gpu_seconds=high,
            min_sum_cap_gpu_hours=low / 3600, max_sum_cap_gpu_hours=high / 3600))

    for name, (relative, _) in INPUTS.items():
        require((ROOT / relative).read_bytes() == raw_inputs[name], 'post-read drift')
    result = dict(classification='CONDITIONAL_SMALL_SIBLING_DEV_COST_BOUNDS_NOT_SELECTION_OR_POWER',
        input_sha256={name: value[1] for name,value in INPUTS.items()},
        historical_runs=84, conservative_components=24, historical_tasks=15,
        nonempty_programs=total_programs, structural_diagnostics=dict(diagnostic), scenarios=scenarios,
        source_admitted=False, selected_programs=0, executed_programs=0, model_fits=0,
        protected_inputs_opened=False, outcomes_used=False,
        limitations=[
            'Only a separately registered historical-weak-training plus fresh-dev route; strict four-fit unchanged.',
            'Hypothetical one dev component per supported task; the whole component remains excluded from training.',
            'All nonempty children of a single existing parent are counted, including repeated code; at least two distinct code hashes.',
            'No syntax, grade, success, outcome, candidate code or protected cohort is read for this calculation.',
            'Each program is assumed to use one GPU for its original full timeout; this is not actual GPU need or wall time.',
            'Bounds range over possible groups, not a selected cheapest subset or an approved execution matrix.',
            'Excludes initialization, grading, I/O, debug or ancestor replay, and critic training; new-state standalone failures must remain.',
            'Groups in the same component are correlated; these counts are not independent trials or adequate statistical power.',
            'This changes the workload relative to full-component reexecution, so it is not a speedup result.',
        ])
    encoded = json.dumps(result, sort_keys=True, allow_nan=False)
    require(not SECRET.search(encoded.encode()), 'output credential shape')
    print(encoded)


if __name__ == '__main__':
    main()
