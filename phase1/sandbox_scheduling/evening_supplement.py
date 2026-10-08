"""Independent closed-batch resource and return-latency checks; no new trials.

Supplementary timing is descriptive, not a replacement for the frozen primary
full-denominator makespan gate. Reads only this evening's public fixture study.
"""
import argparse
import json
from pathlib import Path
from lifecycle_pilot import read, sha, write
from feedback_latency import block_metrics, paired_metrics
import audit_execution_identity as identity


def analyze(pin):
    name = 'scheduling-neural-qualified-overlap-20261008-evening-v1'
    root = Path('/research/d7/spc/yzyang4')/name
    if sha(root/'plan.json') != pin:
        raise ValueError('independent plan pin')
    identity.SCOPES['evening'] = (name, pin)
    resources = identity.audit('evening')
    summary = read(root/'readout-v1/summary.json')
    if summary['reference_arm'] != 'pipeline':
        raise ValueError('wrong reference')
    rows = summary['runs']
    blocks, calls = [], []
    for item in summary['blocks']:
        record = read(root/f'block-{item["block"]}.json')
        closures = []
        for row in rows[2*item['block']:2*item['block']+2]:
            ep = root/f'episode-{row["index"]}'
            close = read(ep/'closed.json')
            done = read(ep/'completed.json') if (ep/'completed.json').exists() else {}
            success = close['returncode'] == 0 and done.get('complete') is True and bool(done.get('output'))
            if success != (row['status'] == 'complete'):
                raise ValueError('completion mismatch')
            closures.append({'end':close['end'],'success':success})
            path = ep/'handshake.json'
            if path.exists():
                calls.append(dict(index=row['index'], calls=read(path)))
        metrics = block_metrics(record['start'], record['end'], closures)
        if abs(metrics['makespan']-item['makespan']) > 1e-6:
            raise ValueError('primary timing mismatch')
        blocks.append(dict(block=item['block'], arm=item['arm'],repeat=item['repeat'],program=None,**metrics))
    prep_start = (root/'plan.json').stat().st_mtime
    prep_end = (root/'preflight.json').stat().st_mtime
    overlaps = []
    for item in summary['blocks']:
        b = read(root/f'block-{item["block"]}.json')
        overlaps.append(max(0, min(b['end'],prep_end)-max(b['start'],prep_start)))
    return dict(resources=resources, job=summary['job'], plan_sha256=pin,
        primary_sha256=sha(root/'readout-v1/summary.json'),
        completed=summary['completed'], planned=12,
        blocks=blocks, paired_return_metrics=paired_metrics(blocks,'pipeline'),
        handshake_calls=calls, own_preflight_overlap_seconds=overlaps,
        boundary='Same source-seed restarts and two reused fixed small public workloads; neither independent task generalization nor live search utility. Return latency is descriptive; metadata does not exclude all host interference.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan-sha',required=True)
    p.add_argument('--output',required=True)
    args = p.parse_args()
    result = analyze(args.plan_sha)
    write(Path(args.output),result)
    print(json.dumps({k:result[k] for k in ('job','completed','planned','paired_return_metrics','own_preflight_overlap_seconds')},sort_keys=True))
