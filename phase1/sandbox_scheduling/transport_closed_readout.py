"""One-time readout of fixed48 empty kernels, never a qualification override."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import statistics

from lifecycle_pilot import read, write, sha

ROOT=Path('/research/d7/spc/yzyang4/scheduling-readiness-transport-20261009-v1')
PINS={'rows.json':'a2e5ce4cd857d8c2d7754b59cf1dadafc77afb1e277b885c5e66a4c3d61739f7',
      'closed.json':'d5d375c4e023d3739724e90bcc32c3291f050da213902233a86dd307478f89bc'}


def summarize(rows):
    if len(rows)!=48 or sorted(r['index'] for r in rows)!=list(range(48)):
        raise ValueError('fixed48 denominator')
    arms={}
    for arm in ('serial','parallel4'):
        subset=[r for r in rows if r['arm']==arm]
        if len(subset)!=24:raise ValueError('24 per arm')
        observations=[r['observation'] for r in subset if r.get('observation') is not None]
        calls=[v for o in observations for v in o['calls']]
        if len(calls)!=24:raise ValueError('one handshake per empty kernel')
        seconds=[v['seconds'] for v in calls]
        arms[arm]=dict(assigned=24,attempted=sum(r['attempted'] for r in subset),
            observed=len(observations),cleanup=sum(o['cleanup'] for o in observations),
            pass_cells=sum(o['result'] is not None and o['result']['exit_code']==0 for o in observations),
            ready_true=sum(v['ready'] is True for v in calls),
            ready_false=sum(v['ready'] is False for v in calls),
            median_handshake_seconds=statistics.median(seconds),
            sample_std_handshake_seconds=statistics.stdev(seconds),max_handshake_seconds=max(seconds),
            counts=dict(sum((Counter(v['counts']) for v in calls),Counter())))
    failures=[dict(index=r['index'],arm=r['arm'],block=r['block'],repeat=r['repeat'],
                   observation=r['observation']) for r in rows
              if r['observation'] is None or r['observation']['result'] is None
              or r['observation']['result']['exit_code']!=0]
    return dict(arms=arms,failures=failures,
        boundary='Post-closure diagnosis. One failure in clustered startups does not establish concurrency causation or a failure-rate difference. Socket/thread liveness is not shell-channel health. No candidate executed; cannot infer candidate behavior, training throughput, or quality. Prior17308 gate remains false.')


def safe_log(raw):
    # Remote stream only, for this no-data/no-model batch. No raw log is copied.
    text=raw.decode('utf-8',errors='replace')
    text=re.sub(r'(?i)(?:sk-[A-Za-z0-9_.-]{10,}|hf_[A-Za-z0-9]{15,}|gh[pousr]_[A-Za-z0-9]{15,}|Bearer\s+\S+)','[CREDENTIAL]',text)
    text=re.sub(r'(?i)((?:auth_token|token|api_key|password|secret)[\s=:\"\x27]+)\S+',r'\1[REDACTED]',text)
    text=re.sub(r'(?:https?|wss?)://\S+','[URL]',text)
    text=re.sub(r'\b[a-fA-F0-9-]{24,}\b','[ID]',text)
    return text


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--write',action='store_true');parser.add_argument('--failure-log',action='store_true')
    args=parser.parse_args()
    for name,pin in PINS.items():
        if sha(args.root/name)!=pin:raise ValueError('closed source drift')
    closed=read(args.root/'closed.json')
    if closed!={'attempted':48,'controller_error':None,'elapsed_seconds':343.13175320252776,'observed':48,'planned':48}:
        raise ValueError('closure changed')
    result=summarize(read(args.root/'rows.json'))
    result.update(inputs=PINS,analysis_sha256=sha(Path(__file__)),job='17322',
        allocation_gpu_seconds=347,allocation_gpu_hours=347/3600)
    if args.write:write(args.root/'readout-v1.json',result)
    print(json.dumps(result,sort_keys=True))
    if args.failure_log:
        for failure in result['failures']:
            print(safe_log((args.root/f'episode-{failure["index"]}/worker.private.log').read_bytes()))


if __name__=='__main__':main()
