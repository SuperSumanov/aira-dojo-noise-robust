"""Closed-run resource contention diagnostics, no quality filtering/reselection."""
import json
from pathlib import Path
import re
import sys
from forets_environment_build_20260912 import read,write,encode,sha

def run(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4'):raise ValueError('scope')
    finish=read(root/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('closed result first')
    prepared=read(root/'prepared.json');rows=[]
    if {r['seed'] for r in prepared['run_configs']} not in ({38,39},{40,41}):raise ValueError('frozen future contrasts only')
    for block in (1,2):
        start=read(root/f'block-{block}.runtime/started.json');pool=read(root/start['pool_manifest'])
        for rid,task in pool['tasks'].items():
            if task['status'] in ('running','launching','pending'):raise ValueError('still active')
            if len(task['attempts'])!=1:raise ValueError('exact one attempt')
            identity=Path(task['attempts'][0]['identity_path'])
            if not identity.resolve().is_relative_to(root/'runs/srun_pool'):raise ValueError('identity scope')
            path=identity.with_suffix('.bounded')/'execution/stderr.private.log';raw=path.read_bytes()
            text=raw.decode(errors='replace')
            waits=re.findall(r'reservation_backpressure seconds=([0-9.]+) polls=([0-9]+)',text)
            rejects=re.findall(r'reservation_rejected total_nusd=([0-9]+) scope_nusd=([0-9]+) amount_nusd=([0-9]+) fresh=([0-9]+) waited=([0-9.]+) permanent=(True|False)',text)
            planned=next(p for p in prepared['run_configs'] if p['run_id']==rid)
            rows.append(dict(run_id=rid,task=planned['task'],seed=planned['seed'],arm=planned['arm'],
                logged_successful_waits=len(waits),logged_successful_wait_seconds=sum(float(x[0]) for x in waits),
                logged_rejections=len(rejects),logged_rejected_wait_seconds=sum(float(x[4]) for x in rejects),
                any_logged_permanent_rejection=any(x[5]=='True' for x in rejects),log_sha256=sha(raw)))
    if len(rows)!=8:raise ValueError('complete matrix')
    value=dict(role='accounting_backpressure_sensitivity_not_quality_endpoint',rows=rows,
        source_finish_sha256=sha((root/'readout-finished.json').read_bytes()),
        limitations='Only emitted completed-wait and rejection messages are observable. Cancellation during waiting may lack a terminal message; zero logged waits is not a proof of zero true wait. No quality eligibility changes or exclusions.')
    digest=write(root/'reservation-waits.json',encode(value))
    print(json.dumps(dict(sha256=digest,rows=rows)))

if __name__=='__main__':run(Path(sys.argv[1]))
