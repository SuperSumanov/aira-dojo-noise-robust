"""Post-result check of a suspected startup asymmetry, not an effect readout.

Only event metadata from the closed v7 batch is accessed. Success false is not
automatically an infrastructure failure; the frozen primary verdict is retained.
"""
import json
from pathlib import Path
from lifecycle_pilot import read,write,sha


def main():
    root=Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v7')
    closed=read(root/'closed.json');plan=read(root/'plan.json');rows=[]
    if closed.get('complete')!=16:raise ValueError('closed full batch required')
    for s in plan['schedule']:
        path=root/f'episode-{s["index"]}/events.jsonl'
        events=[json.loads(x) for x in path.read_text().splitlines()]
        items=[dict(elapsed=e['elapsed'],seconds=e['seconds'],success=e['success'])
            for e in events if e['event']=='kernel_ready']
        if any(type(e['success']) is not bool for e in items):raise ValueError('readiness flag')
        rows.append(dict(index=s['index'],block=s['block'],arm=s['arm'],task=s['task'],
            attempts=len(items),unsuccessful=sum(not e['success'] for e in items),
            total_seconds=sum(e['seconds'] for e in items),events=items,events_sha256=sha(path)))
    result=dict(plan_sha256=sha(root/'plan.json'),closed_sha256=sha(root/'closed.json'),
        analysis_source_sha256=sha(__file__),rows=rows,
        boundary='Post-result startup diagnosis only. All16 remain in the frozen primary analysis; no subtraction of slow time or exclusion of a run. Does not prove cause of timeout or quality difference.')
    write(root/'readiness-diagnosis-v1.json',result)
    print(json.dumps(dict(written=True,rows=len(rows),unsuccessful=sum(r['unsuccessful'] for r in rows))))


if __name__=='__main__':main()
