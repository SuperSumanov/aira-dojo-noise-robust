"""Independent post-closure audit of 17308; never repairs the frozen gate.

No source, prediction value, raw log or credential is exported. Completion
curves are descriptive of five completed blocks, not a full 36-run result.
"""
import csv
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/scheduling-neural-width-20261009-v1')
PLAN = '783934f461321858efbca68c9b70505323729ba921f6c9aba002ff4c42f38c5c'
SUMMARY = 'c1dd1c6f746dd5502478a8eda32d30cf7b6c1796d280c307cc2bd45c631d8620'
EVENTS = {
    'waiting_ready': 'Waiting for ready',
    'kernel_not_ready': 'Kernel did not become ready in time',
    'client_created': 'Kernel client ',
    'starting_kernel': 'Starting kernel ',
    'getting_kernel_client': 'Getting kernel client',
    'executing_code': 'Executing code',
    'websocket_error': 'WebSocket error:',
    'connection_closed': 'Connection to remote host was lost',
    'address_in_use': 'Address already in use',
    'kernel_died': 'KernelRestarter',
    'received_kernel_reply': 'kernel_info_reply',
    'unauthorized': '401 Unauthorized',
    'forbidden': '403 Forbidden',
    'connection_refused': 'Connection refused',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def numeric_table(path):
    with path.open(newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    if len(header) < 2 or len(header) != len(set(header)) or not rows:
        raise ValueError('bad schema')
    table = {}
    for row in rows:
        if len(row) != len(header) or row[0] in table:
            raise ValueError('bad row identity/shape')
        values = tuple(Decimal(x) for x in row[1:])
        if not all(x.is_finite() for x in values):
            raise ValueError('nonfinite output')
        table[row[0]] = values
    return header, table


def completion_curve(returns):
    if len(returns) != 4 or any(t <= 0 for t in returns):
        raise ValueError('four positive return times required')
    times = sorted(returns)
    return dict(ordered_return_seconds=times, mean_return_seconds=sum(times)/4,
                full_batch_return_seconds=times[-1])


def curve_comparison(a, b):
    """b-minus-a for each return rank; negative means b is earlier."""
    if len(a) != 4 or len(b) != 4:
        raise ValueError('complete curves required')
    differences = [y-x for x,y in zip(sorted(a), sorted(b))]
    return dict(return_rank_differences_seconds=differences,
                b_no_later_at_every_return_rank=all(x <= 0 for x in differences),
                a_no_later_at_every_return_rank=all(x >= 0 for x in differences),
                crosses=any(x < 0 for x in differences) and any(x > 0 for x in differences))


def main():
    if digest(ROOT/'plan.json') != PLAN or digest(ROOT/'readout-v1/summary.json') != SUMMARY:
        raise ValueError('closed source identity mismatch')
    summary = read(ROOT/'readout-v1/summary.json')
    rows = read(ROOT/'runs.json')
    if len(rows) != 36 or [r['index'] for r in rows] != list(range(36)):
        raise ValueError('full denominator')
    if summary['allocation_state'] != 'FAILED' or summary['complete_valid_comparison']:
        raise ValueError('unexpected frozen status')
    outputs = {0:[], 1:[]}; steps = {0:[], 1:[]}; evidence = []
    for r in rows:
        ep = ROOT/f'episode-{r["index"]}'
        item = dict(index=r['index'], status=r['status'], program=r['program'],
                    arm=r['arm'], block=r['block'], repeat=r['repeat'],
                    candidate_started=(ep/'candidate_started.json').exists())
        if (ep/'completed.json').exists():
            done=read(ep/'completed.json'); close=read(ep/'closed.json')
            item.update(error_type=done['error_type'], returncode=close['returncode'])
            log=ep/'worker.private.log'
            text=log.read_text(errors='replace') if log.exists() else ''
            events=[name for line in text.splitlines() for name,needle in EVENTS.items() if needle in line]
            item['named_event_counts']=dict(Counter(events))
            # Order only on failed workers, never raw lines.
            if r['status'] != 'complete':
                item['named_event_order']=events
                item['cell_receipts']=[{k:read(p).get(k) for k in
                    ('stage','exit_code','timed_out','exec_seconds','timeout_phase')}
                    for p in sorted(ep.glob('cell-*.json'))]
            if r['status'] == 'complete':
                path=ep/'work/submission.csv'
                if not done['complete'] or close['returncode'] != 0 or digest(path) != r['output_sha256'] or digest(path) != done['output']['sha256']:
                    raise ValueError('completed output receipt mismatch')
                outputs[r['program']].append(numeric_table(path))
                steps[r['program']].append(done['gpu_training']['steps'])
        evidence.append(item)
    numeric=[]
    for program, expected in ((0,150),(1,640)):
        tables=outputs[program]
        numeric.append(dict(program=program, observed_complete=len(tables), expected_total=18,
            all_observed_decimal_tables_equal=bool(tables) and all(t == tables[0] for t in tables),
            all_observed_original_steps=bool(steps[program]) and all(s == expected for s in steps[program]),
            required_steps=expected))
    blocks=[]
    for b in range(9):
        path=ROOT/f'block-{b}.json'
        if not path.exists():
            blocks.append(dict(block=b, observed=False, complete=False)); continue
        block=read(path); own=rows[4*b:4*b+4]
        full=all(r['status']=='complete' for r in own)
        item=dict(block=b, observed=True, complete=full, arm=block['arm'], repeat=block['repeat'])
        if full:
            item.update(completion_curve([read(ROOT/f'episode-{r["index"]}/completed.json')['end']-block['start'] for r in own]))
        blocks.append(item)
    comparisons=[]
    for repeat in range(3):
        matched={b['arm']:b for b in blocks if b['complete'] and b['repeat']==repeat}
        if {'share2','share4'} <= matched.keys():
            comparisons.append(dict(repeat=repeat, observed=True, **curve_comparison(
                matched['share2']['ordered_return_seconds'],matched['share4']['ordered_return_seconds'])))
        else: comparisons.append(dict(repeat=repeat, observed=False))
    result=dict(job='17308', analysis_sha256=digest(Path(__file__)), plan_sha256=PLAN,
        frozen_summary_sha256=SUMMARY, full_denominator=36,
        status_counts=dict(Counter(r['status'] for r in rows)),
        observed_output_audit=numeric, rows=evidence, blocks=blocks,
        share4_minus_share2_return_rank_comparisons=comparisons,
        frozen_complete_valid_comparison=False,
        boundary='Post-result diagnosis, no gate change or selection. Missing third repeat stays missing. Exact observed numerical equality is not complete18/program coverage. Return-rank crossings are descriptive, not a new method, live quality gain, or proof of failure cause. Absence of named log events does not prove healthy transport.')
    destination=ROOT/'diagnostics-v1.json'
    with destination.open('x') as f: json.dump(result,f,indent=2,sort_keys=True); f.write('\n')
    print(json.dumps(dict(written=True,sha256=digest(destination),observed_output_audit=numeric,
                         return_rank_comparisons=comparisons)))


if __name__=='__main__': main()
