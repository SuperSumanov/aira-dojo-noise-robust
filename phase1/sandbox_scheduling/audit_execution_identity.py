"""Read-only postflight input/resource check; run only after timing closes.

Supplement to frozen readouts, not a new trial or quality analysis. Export only
counts, hashes and verification flags. Hashing inputs is intentionally forbidden
while this allocation is open. No writes to frozen experiment roots.
"""
import argparse
import json
from pathlib import Path
from lifecycle_pilot import read, sha

BASE = Path('/research/d7/spc/yzyang4')
SCOPES = {
 'neural': ('scheduling-neural-20261008-v1', '8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'),
 'full-input': ('scheduling-neural-full-input-20261008-v2', 'e836f8c49b13ce52ef02c138b873bc1464cdb147dc06254f656b707ff93afade'),
 'confirmation': ('scheduling-neural-full-confirmation-20261008-v1', 'b8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f'),
 'overlap-retry': ('scheduling-neural-overlap-retry-20261008-v2', '528026478eff9138b06ff53023d5793139ea3bd9246fc3082cc3d749c8c25dfc'),
}


def resource_check(allocation, started, native, complete):
    if complete and (started is None or native is None):
        raise ValueError('completed execution lacks identity receipt')
    if started is not None and started['affinity'] != allocation['affinity']:
        raise ValueError('CPU affinity differs from allocation')
    if native is not None and (native['gpu_uuids'] != [allocation['gpu_uuid']]
                               or native['job'] != allocation['job']):
        raise ValueError('GPU/allocation identity mismatch')
    return started is not None and native is not None


def audit(kind):
    name, pin = SCOPES[kind]
    root = BASE / name
    if not (root / 'closed.json').exists() or sha(root / 'plan.json') != pin:
        raise ValueError('not a closed fixed scope')
    plan = read(root / 'plan.json')
    allocation = read(root / 'allocation.json')
    report = read(root / 'readout-v1/summary.json')
    if report['allocation_state'] in ('PENDING', 'RUNNING', 'COMPLETING'):
        raise ValueError('allocation not terminal')
    if report['job'] != allocation['job'] or report['plan_sha256'] != pin:
        raise ValueError('readout provenance')
    for name, expected in plan['files'].items():
        if sha(root / name) != expected:
            raise ValueError('frozen source/fixture drift')
    inputs = plan.get('input_files', {})
    for name, expected in inputs.items():
        if sha(name) != expected:
            raise ValueError('referenced input drift')
    rows = read(root / 'runs.json')
    if report['runs'] != rows or [r['index'] for r in rows] != list(range(12)):
        raise ValueError('formal denominator')
    verified = missing = complete_count = 0
    for row in rows:
        ep = root / ('episode-' + str(row['index']))
        started = read(ep / 'started.json') if (ep / 'started.json').exists() else None
        native = read(ep / 'native.json') if (ep / 'native.json').exists() else None
        complete = row['status'] == 'complete'
        complete_count += complete
        full_identity = resource_check(allocation, started, native, complete)
        verified += full_identity
        missing += not full_identity
    if complete_count != report['completed']:
        raise ValueError('completion denominator')
    return dict(job=allocation['job'], plan_sha256=pin,
        primary_sha256=sha(root / 'readout-v1/summary.json'),
        analysis_source_sha256=sha(__file__), formal_slots=len(rows),
        completed=complete_count, identity_verified_slots=verified,
        identity_unavailable_slots=missing, frozen_file_hashes_verified=len(plan['files']),
        referenced_input_hashes_verified=len(inputs),
        all_completed_same_allocation_CPU_GPU=True if complete_count else None,
        boundary='Postflight metadata and hashes only. Same affinity/device is not shared-host isolation, absence of interference, kernel concurrency, or quality evidence. Missing unstarted/failed identities remain explicit.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=SCOPES)
    print(json.dumps(audit(parser.parse_args().kind), sort_keys=True))
