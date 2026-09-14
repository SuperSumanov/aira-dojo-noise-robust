"""Closed-only reservation waits; never change the frozen quality eligibility."""
import json,re,statistics
from collections import defaultdict
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import read,checked,sha,BASE

ROOT=BASE/'forets-wallclock-20260912-km65uuej'
WAIT=re.compile(rb'reservation_backpressure seconds=([0-9.]+) polls=([0-9]+)')
REJECT=re.compile(rb'reservation_rejected total_nusd=([0-9]+) scope_nusd=([0-9]+) amount_nusd=([0-9]+) fresh=([0-9]+) waited=([0-9.]+) permanent=(True|False)')
def summarize(raw):
    waits=WAIT.findall(raw);rejects=REJECT.findall(raw)
    return dict(logged_completed_waits=len(waits),logged_completed_wait_seconds=sum(float(v[0]) for v in waits),
        logged_rejections=len(rejects),logged_rejected_wait_seconds=sum(float(v[4]) for v in rejects),
        any_logged_permanent_rejection=any(v[5]==b'True' for v in rejects))
def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('all closed and frozen readout first')
    effect=read(ROOT/'cheap-selector-summary.json',finish['files']['cheap-selector-summary.json'])
    prepared=read(ROOT/'prepared.json',read(ROOT/'build.json')['prepared_sha256'])
    if len(effect['rows'])!=12 or {r['seed'] for r in prepared['run_configs']}!={46,47}:raise ValueError('matrix')
    rows=[]
    for block in (1,2):
        pool=read(ROOT/read(ROOT/f'block-{block}.runtime/started.json')['pool_manifest'])
        for rid,task in pool['tasks'].items():
            if task['status'] in ('running','launching','pending'):raise ValueError('active slot')
            if len(task['attempts'])!=1:raise ValueError('expected exactly one attempt')
            identity=Path(task['attempts'][0]['identity_path'])
            if not identity.resolve().is_relative_to(ROOT/'runs/srun_pool'):raise ValueError('scope')
            path=identity.with_suffix('.bounded')/'execution/stderr.private.log'
            raw=checked(path)  # Credential check before any text extraction; values are never printed.
            cfg=next(r for r in prepared['run_configs'] if r['run_id']==rid)
            rows.append(dict(run_id=rid,task=cfg['task'],seed=cfg['seed'],arm=cfg['arm'],log_sha256=sha(raw),**summarize(raw)))
    if len(rows)!=12:raise ValueError('all twelve')
    groups=[]
    for arm in ('uniform','short_code','learned_validity'):
        rr=[r for r in rows if r['arm']==arm]
        values=[r['logged_completed_wait_seconds']+r['logged_rejected_wait_seconds'] for r in rr]
        groups.append(dict(arm=arm,runs=len(rr),summed_logged_wait_seconds=sum(values),median_logged_wait_seconds=statistics.median(values),
            sample_sd_logged_wait_seconds=statistics.stdev(values),runs_with_rejection=sum(r['logged_rejections']>0 for r in rr)))
    value=dict(role='closed_shared_reservation_contention_diagnostic_not_quality_correction',rows=rows,groups=groups,
        frozen_finish_sha256=sha((ROOT/'readout-finished.json').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Only completed logged waits/rejections observed. Cancellation can omit terminal wait messages; zero is not proof of no wait. Shared cumulative reservations can couple simultaneous runs. No time subtraction, outcome adjustment, eligibility change or deleted run.')
    raw=(json.dumps(value,sort_keys=True)+'\n').encode()
    with (ROOT/'cheap-reservation-waits.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),groups=groups)))
if __name__=='__main__':main()
