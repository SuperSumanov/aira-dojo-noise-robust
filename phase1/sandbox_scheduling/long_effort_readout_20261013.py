"""Full-denominator24-run qualification. One pool per arm, not replication."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from long_effort_policy_20261013 import ARMS, ORDER, RUN, SLOT, CAP, effort

TASKS = ('aerial-cactus-identification', 'denoising-dirty-documents')
SIGN = {TASKS[0]: 1, TASKS[1]: -1}
def read(p): return json.loads(Path(p).read_text())
def lines(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, value):
    with Path(p).open('x') as f: json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)


def quality(scores):
    contrasts = [dict(task=t, reference=a, method_best=scores['xhigh', t],
        reference_best=scores[a, t], oriented_delta=SIGN[t]*(scores['xhigh', t]-scores[a, t]))
        for t in TASKS for a in ('fast_code', 'medium')]
    return contrasts, all(r['oriented_delta'] >= (.001 if r['task'] == TASKS[1] else -1e-12) for r in contrasts)


def analyze(root, out, gpu_seconds):
    root = Path(root)
    p, closed = read(root/'plan.json'), read(root/'closed.json')
    assert p['planned'] == 24 and p['allocation_seconds'] == CAP and p['prior_failures'] == []
    assert 0 < gpu_seconds <= CAP*6 and p['run_seconds'] == RUN and p['slot_seconds'] == SLOT
    assert all(sha(root/n) == h for n, h in p['files'].items())
    assert all(sha(root/n) == h for n, h in p['input_files'].items())
    sys.path.insert(0, str(root))
    from image_dev_data_20261011 import score_at
    from live_readout import timely_returns, ground_scores, queue_verify
    from live_identity import cores
    from feedback_parent_readout_20261012 import audit
    spec, warm = read(root/'dev-views/spec.json'), read(root/'warm-receipt.json')
    rows, calls, recomputed = [], [], 0
    for s in p['schedule']:
        ep = root/f"episode-{s['index']}"
        f = read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        cl = read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates = [read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name]
        timely = timely_returns(candidates, RUN)
        receipts = []
        for x in ep.glob('scored-*.json'):
            receipt = read(x)['receipt']; receipts.append(receipt)
            actual = score_at(root, spec, s['task'], ep/(x.stem+'.private.csv'))
            metric = spec[s['task']]['metric_name']
            assert actual['submission_sha256'] == receipt['submission_sha256'] and abs(actual[metric]-receipt[metric]) <= 1e-12
            recomputed += 1
        assert ground_scores(dict(f, native_selected_valid=False), timely, receipts)
        eligible = [r['score'] for r in timely if r.get('valid') is True and r.get('exit_code') == 0
            and not r.get('timed_out') and type(r.get('score')) in (int, float) and math.isfinite(r['score'])]
        complete = cl.get('returncode') == 0 and cl.get('cleanup_verified') is True and f.get('status') in ('completed', 'budget_exhausted')
        initial = warm[s['task']]['score']
        best = max([initial]+eligible, key=lambda x: SIGN[s['task']]*x) if complete else None
        rows.append(dict(s, source_commit=p['source_commit'], run_seconds=RUN, pool_seconds=SLOT,
            score=best, initial_score=initial, started=(ep/'deadline.json').exists(), complete=complete,
            cleanup=cl.get('cleanup_verified') is True, candidate_returns=len(timely), valid_returns=len(eligible)))
        if (ep/'effort.jsonl').exists():
            for e in lines(ep/'effort.jsonl'):
                expected = effort(s['arm'], e['role'])
                assert e['arm'] == s['arm'] and e['effort'] == expected and e['enable_thinking'] is (expected != 'none')
                assert e['output_cap'] == (8192 if e['role'] == 'analyze' else 32768)
                assert e['request_cap'] == (600 if e['role'] == 'analyze' else 1500)
                calls.append(dict(index=s['index'], task=s['task'], **e))
    out = Path(out); out.mkdir()
    write(out/'runs.json', rows); write(out/'effort.json', calls)
    with (out/'runs.csv').open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    result = dict(assigned=24, started=sum(r['started'] for r in rows), complete=sum(r['complete'] for r in rows),
        source_commit=p['source_commit'], plan_sha256=sha(root/'plan.json'), readout_sha256=sha(__file__),
        gpu_seconds=gpu_seconds, gpu_hours=gpu_seconds/3600, scores_recomputed=recomputed,
        independent_pools_per_arm=1, no_automatic_expansion=True, limitation=p['limitation'],
        predeclared_success_gate_met=False)
    if not all(r['complete'] for r in rows):
        result['incomplete'] = True
        write(out/'summary.json', result); print(json.dumps(result)); return
    identities, budgets, partitions, policies = [], [], [], []
    for b in range(3):
        bd = root/f'block-{b}'
        slot, steps = read(bd/'budget-slot.json'), read(bd/'steps.json')
        budgets.append(slot['reserved_seconds'] == SLOT and SLOT <= slot['actual_seconds'] <= SLOT+2 and steps['returncodes'] == [0]*4)
        assert all(queue_verify(lines(root/f'queue-{b}-{i}/events.jsonl'), 1)['complete'] for i in range(4))
        policies.append(dict(block=b, arm=ORDER[b], **audit(lines(root/f'generation-{b}/events.jsonl'), 'greedy')))
        state = read(root/f'generation-{b}/state.json')
        assert not state['pending'] and not state['waiting'] and not state['active']
        service = read(bd/'service-native.json')
        lanes = [read(bd/f'lane-{i}-native.json') for i in range(4)]
        devices = [x['gpu_uuid'] for x in lanes]
        sets = [cores(x['cpu_topology']) for x in lanes]+[cores(service['cpu_topology'])]
        valid = len(set(devices)) == 4 and len(set(service['gpu_uuids'])) == 2 and not set(devices)&set(service['gpu_uuids'])
        valid &= all(len(x) == 4 for x in sets[:4]) and len(sets[-1]) == 8 and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
        identities.append(dict(block=b, lanes=devices, service=service['gpu_uuids'], valid=valid))
        for lane in range(4):
            a, c = (read(root/f'episode-{b*8+lane*2+k}/cpu-partition.json') for k in (0, 1))
            ac, cc = cores(a['worker_topology']), cores(c['worker_topology'])
            partitions.append(len(ac) == len(cc) == 2 and not ac&cc and ac|cc == cores(a['parent_topology']) == cores(c['parent_topology']))
    structure = bool(all(budgets) and all(partitions) and closed['error'] is None
        and read(root/'block-0/service-cleanup.json')['gpu_clean']
        and all(i['valid'] and i['lanes'] == identities[0]['lanes'] and set(i['service']) == set(identities[0]['service']) for i in identities))
    scores = {(a, t): max([r['score'] for r in rows if (r['arm'], r['task']) == (a, t)], key=lambda x: SIGN[t]*x) for a in ARMS for t in TASKS}
    contrasts, passed = quality(scores)
    actual = all(any(e['arm'] == a and e['role'] == 'improve' and e['success'] for e in calls) for a in ARMS)
    result.update(contrasts=contrasts, quality_gate=passed, structural_gate=structure,
        actual_mode_gate=actual, predeclared_success_gate_met=bool(passed and structure and actual),
        cpu_pairs_passed=sum(partitions), policies=policies,
        by_arm={a: {t: dict(median=statistics.median([r['score'] for r in rows if (r['arm'], r['task']) == (a, t)]),
            sample_sd=statistics.stdev([r['score'] for r in rows if (r['arm'], r['task']) == (a, t)])) for t in TASKS} for a in ARMS})
    write(out/'identity.json', identities); write(out/'summary.json', result)
    print(json.dumps(result, allow_nan=False))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('out'); ap.add_argument('--gpu-seconds', type=int, required=True)
    a = ap.parse_args(); analyze(a.root, a.out, a.gpu_seconds)
