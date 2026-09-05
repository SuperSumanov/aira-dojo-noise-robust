"""Necessary task/component support; no split selection or payload reads."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from export_snapshot_request_20260906 import ROOT, canonical, h, load, require

ledger, lineage, scope = load('ledger'), load('lineage'), load('scope')
chosen = set(scope['selected_runs'])
require(len(chosen) == 84, 'scope_changed')
task_by_run = defaultdict(set)
for m in lineage['manifests']:
    for t in m['tasks']:
        if t['run_id'] in chosen:
            task_by_run[t['run_id']].add(t['task_name'])
require(set(task_by_run) == chosen and all(len(x) == 1 for x in task_by_run.values()), 'task_binding_conflict')
task_runs, task_components, task_strata = defaultdict(set), defaultdict(set), defaultdict(set)
components, strata = defaultdict(set), defaultdict(set)
for r in sorted(chosen):
    task = next(iter(task_by_run[r]))
    component = lineage['closure'][r]['component_sha256']
    stratum = ledger[r]['origins'][0]['recorded_config_stratum_sha256']
    require(not lineage['closure'][r]['old_hold_closure_blocks_train'], 'hold_blocked')
    task_runs[task].add(r); task_components[task].add(component); task_strata[task].add(stratum)
    components[component].add(r); strata[stratum].add(r)
summary = {
    'classification': 'HISTORICAL_METADATA_NECESSARY_SUPPORT_ONLY_NOT_ADMISSION_OR_POWER',
    'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'script_sha256': h(Path(__file__).read_bytes()),
    'fixed_runs': len(chosen), 'tasks': len(task_runs),
    'conservative_components': len(components), 'recorded_config_strata': len(strata),
    'sorted_runs_per_task': sorted(map(len, task_runs.values())),
    'sorted_components_per_task': sorted(map(len, task_components.values())),
    'tasks_with_at_least_two_conservative_components': sum(len(x) >= 2 for x in task_components.values()),
    'tasks_with_at_least_three_conservative_components': sum(len(x) >= 3 for x in task_components.values()),
    'largest_task_run_share': max(map(len, task_runs.values())) / len(chosen),
    'component_count_by_run_size': dict(Counter(map(len, components.values()))),
    'stratum_count_by_run_size': dict(Counter(map(len, strata.values()))),
    'full_experiment_semantics_verified': False, 'pair_support_inspected': False,
    'split_selected': False, 'training_qualified': False, 'model_fits': 0,
    'notes': ['Two components per task is only necessary for same-task train/dev coverage; not sufficient for full experiment isolation or statistical power.',
              'No equal-stratum pair yield, finite label yield, code diversity or model performance is inferred.'],
}
os.umask(0o077)
out = ROOT/'historical-screen-support-20260906.json'
with out.open('xb') as f:
    f.write(canonical(summary)); f.flush(); os.fsync(f.fileno())
out.chmod(0o400)
print(json.dumps(summary, sort_keys=True))
