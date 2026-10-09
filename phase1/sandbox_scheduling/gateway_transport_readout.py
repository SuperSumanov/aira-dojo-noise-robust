"""Closed48 diagnostic readout: enum counters only, no raw logs/messages."""
import argparse
import json
from pathlib import Path
import re
from lifecycle_pilot import read,write,sha
from transport_closed_readout import summarize

R=Path('/research/d7/spc/yzyang4/scheduling-readiness-gateway-20261009-v1')
PLAN='72b42e1e39b4a444def1d831b5ade208a3bc6d1e04065571b660b435c6c60d0b'
ALLOWED=re.compile(r'^(?:(?:incoming|outgoing)_(?:kernel_info_request|kernel_info_reply|status|execute_request|execute_reply|error|other|unknown|forwarded)|nudge_(?:enter|done|failed|cancelled|state_starting|state_busy|state_idle|state_dead|state_other))$')


def main():
    p=argparse.ArgumentParser();p.add_argument('--allocation-gpu-seconds',type=int,required=True);args=p.parse_args()
    if not 0<args.allocation_gpu_seconds<=900 or sha(R/'plan.json')!=PLAN:raise ValueError('fixed batch/budget')
    plan=read(R/'plan.json');closed=read(R/'closed.json')
    if closed['planned']!=48 or closed['observed']!=48 or closed['controller_error'] is not None:raise ValueError('incomplete48; separate failure readout required')
    for name,pin in plan['files'].items():
        if sha(R/name)!=pin:raise ValueError('source drift')
    rows=read(R/'rows.json');summary=summarize(rows);details=[]
    for row in rows:
        path=R/f'episode-{row["index"]}/work/gateway-counts.json'
        counts=read(path) if path.exists() else None
        if counts is not None and not all(ALLOWED.fullmatch(k) and type(v) is int and v>=0 for k,v in counts.items()):raise ValueError('nonenum gateway output')
        details.append(dict(index=row['index'],arm=row['arm'],block=row['block'],
            client_calls=row['observation']['calls'],gateway_counts=counts,
            gateway_counts_sha256=sha(path) if path.exists() else None,
            pass_cell=row['observation']['result'] is not None and row['observation']['result']['exit_code']==0))
    out=dict(plan_sha256=PLAN,analysis_sha256=sha(Path(__file__)),rows_sha256=sha(R/'rows.json'),
        closed_sha256=sha(R/'closed.json'),summary=summary,details=details,
        allocation_gpu_seconds=args.allocation_gpu_seconds,allocation_gpu_hours=args.allocation_gpu_seconds/3600,
        boundary='Gateway callbacks were instrumented and wrote counters per event; timings are not comparable to the uninstrumented batch. A failure location is not a proven root cause. No retry/fix or qualification override.')
    write(R/'readout-v1.json',out)
    print(json.dumps(dict(sha256=sha(R/'readout-v1.json'),summary=summary,failures=[x for x in details if not x['pass_cell']])))


if __name__=='__main__':main()
