"""Metadata-only audit of own preparation overlapping timed blocks.

Plan-to-preflight mtime spans include the large-image SHA check in these builders.
This is only a conservative known subset of preparation, not an I/O trace; no
claim of physical disk traffic or causal slowdown follows from overlap alone.
"""
import json
from pathlib import Path
from lifecycle_pilot import read

B=Path('/research/d7/spc/yzyang4')
NAMES=('pool-20261008-v2','neural-20261008-v1','pipeline-20261008-v1',
       'homogeneous-20261008-v1','neural-gpu28-20261008-v2',
       'neural-full-input-20261008-v1','neural-full-input-20261008-v2',
       'neural-overlap-20261008-v1','neural-full-confirmation-20261008-v1')


def main():
    preparations=[];experiments=[]
    for name in NAMES:
        root=B/('scheduling-'+name)
        plan,preflight=root/'plan.json',root/'preflight.json'
        if plan.exists() and preflight.exists():
            preparations.append(dict(root=str(root),start=plan.stat().st_mtime,
                                     end=preflight.stat().st_mtime))
    for name in NAMES:
        root=B/('scheduling-'+name)
        if not (root/'allocation.json').exists():continue
        job=read(root/'launch.json')['job'];blocks=[]
        for path in sorted(root.glob('block-*.json'),key=lambda p:int(p.stem.split('-')[-1])):
            block=read(path);matches=[]
            for prep in preparations:
                seconds=max(0,min(block['end'],prep['end'])-max(block['start'],prep['start']))
                if seconds:matches.append(dict(preparation_root=prep['root'],seconds=seconds))
            blocks.append(dict(block=block['block'],arm=block['arm'],repeat=block['repeat'],
                               start=block['start'],end=block['end'],overlaps=matches))
        experiments.append(dict(job=job,root=str(root),closed=(root/'closed.json').exists(),blocks=blocks))
    print(json.dumps(dict(preparations=preparations,experiments=experiments,
        boundary='Own preparation mtime overlap is a possible measurement confound, not proof of physical I/O contention. No shared-host/disk isolation or clock-synchronization bound was measured; no-overlap here does not prove no external interference.'),sort_keys=True))


if __name__=='__main__':main()
