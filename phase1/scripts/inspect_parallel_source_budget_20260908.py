"""Read-only historical support/cost join. Does not select or execute programs."""
import hashlib
import itertools
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
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

raws, data = {}, {}
for name, (relative, digest) in INPUTS.items():
    path = ROOT / relative
    require(path.stat().st_size <= 64 * 1024 * 1024, 'metadata_size_cap')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, 'input_hash_drift')
    require(not SECRET.search(raw), 'credential_shape')
    raws[name], data[name] = raw, json.loads(raw)

chosen = set(data['scope']['selected_runs'])
require(len(chosen) == 84 and set(data['pack']) == chosen, 'scope_mismatch')
component_runs, component_tasks = defaultdict(set), defaultdict(set)
component_costs, task_components = defaultdict(int), defaultdict(set)
total_programs = 0
for rid in chosen:
    closure = data['lineage']['closure'][rid]
    require(closure['old_hold_closure_blocks_train'] is False, 'hold_blocked')
    component = closure['component_sha256']
    run = data['pack'][rid]
    require(run['source_admitted'] is False, 'admission_changed')
    cap = run['full_execution_timeout']
    require(type(cap) is int and cap > 0, 'bad_cap')
    require(all(type(x['nonempty_code']) is bool for x in run['nodes']), 'bad_code_flag')
    count = sum(x['nonempty_code'] for x in run['nodes'])
    total_programs += count
    component_runs[component].add(rid)
    component_tasks[component].add(run['task'])
    component_costs[component] += count * cap
    task_components[run['task']].add(component)

for rid, closure in data['lineage']['closure'].items():
    if closure['component_sha256'] in component_runs:
        require(rid in chosen, 'partial_component')
require(all(len(v) == 1 for v in component_tasks.values()), 'cross_task_component')
require(len(component_runs) == 24 and len(task_components) == 15, 'support_changed')
require(total_programs == 3447 and sum(component_costs.values()) == 22912800, 'cost_changed')

rows = []
for task, components in sorted(task_components.items()):
    costs = sorted(component_costs[c] for c in components)
    possible_sums = [component_costs[a] + component_costs[b]
                     for a, b in itertools.combinations(components, 2)]
    lower = sum(costs[:2]) if len(costs) >= 2 else None
    require(lower == (min(possible_sums) if possible_sums else None), 'bound_crosscheck')
    rows.append({'task': task, 'components': len(components),
                 'runs': sum(len(component_runs[c]) for c in components),
                 'all_programs_cap_gpu_hours': sum(costs) / 3600,
                 'minimum_two_complete_components_cap_gpu_hours':
                     lower / 3600 if lower is not None else None})

feasible = sorted(r['minimum_two_complete_components_cap_gpu_hours']
                  for r in rows if r['components'] >= 2)
require(len(feasible) == 6, 'two_component_support_changed')
for name, (relative, _) in INPUTS.items():
    require((ROOT / relative).read_bytes() == raws[name], 'post_read_drift')

result = {
    'classification': 'METADATA_ONLY_BUDGET_FRONTIER_NOT_SOURCE_ADMISSION_OR_SELECTION',
    'input_sha256': {name: spec[1] for name, spec in INPUTS.items()},
    'task_rows': rows,
    'minimum_full_component_cap_by_task_count': {
        str(n): sum(feasible[:n]) for n in range(1, len(feasible) + 1)},
    'programs_selected': 0, 'programs_executed': 0, 'model_fits': 0,
    'old_outcomes_read': False, 'protected_inputs_opened': False,
    'source_admitted': False,
    'limitations': [
        'Each admitted component would need all its nonempty programs at their original full caps.',
        'One GPU per program is a planning assumption, not a measured resource need.',
        'This minimizes the sum of conditional caps; it is not actual cost or time prediction.',
        'Task minimization is diagnostic only: no tasks, components or train/dev roles are selected.',
        'Two conservative components are necessary coverage, not experiment independence or power.',
        'Excludes queue, environment startup, grading, IO and critic training.',
    ],
}
encoded = json.dumps(result, sort_keys=True, allow_nan=False)
require(not SECRET.search(encoded.encode()), 'output_credential_shape')
print(encoded)
