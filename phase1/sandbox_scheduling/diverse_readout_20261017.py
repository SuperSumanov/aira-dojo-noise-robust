"""Frozen48-denominator readout; quality must beat BOTH controls in BOTH repeats."""
import argparse
import inspect
import math
import statistics
import colocation_readout_20261016 as old
from diverse_pool_20261017 import independent_audit

ORDER=('shared','colocated','diverse','diverse','colocated','shared')
TASKS=old.TASKS


def quality(rows):
    blocks=[]
    for b,mode in enumerate(ORDER):
        for task in TASKS:
            values=[r['score'] for r in rows if r['block']==b and r['task']==task]
            assert len(values)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in values)
            blocks.append(dict(block=b,repeat=b//3,pool_mode=mode,task=task,
                best=max(values,key=lambda v:old.SIGN[task]*v),median=statistics.median(values),
                sample_sd=statistics.stdev(values),n=4))
    contrasts=[]
    for rep in range(2):
        for task in TASKS:
            d={r['pool_mode']:r for r in blocks if r['repeat']==rep and r['task']==task}
            for control in ('shared','colocated'):
                contrasts.append(dict(repeat=rep,task=task,control=control,
                    baseline_best=d[control]['best'],diverse_best=d['diverse']['best'],
                    oriented_delta=old.SIGN[task]*(d['diverse']['best']-d[control]['best']),
                    median_delta=old.SIGN[task]*(d['diverse']['median']-d[control]['median'])))
    gate=all(r['oriented_delta']>=(.001 if r['task']==TASKS[1] else -1e-12) for r in contrasts)
    return blocks,contrasts,gate


def configure():
    original=getattr(old,'_diverse_analyze_original',old.analyze);old._diverse_analyze_original=original
    old.__file__=__file__
    old.ORDER=ORDER;old.CAP=8400;old.quality=quality;old.verify_queue=independent_audit
    source=inspect.getsource(original)
    replacements=[("p['planned']==32","p['planned']==48",1),
        ('gpu_seconds<=36000','gpu_seconds<=50400',1),
        ('dict(assigned=32,','dict(assigned=48,',1),
        ('for b in range(4)','for b in range(6)',2),
        ("dispatched=all(q['co_admissions']>0 for q in queues if q['pool_mode']=='colocated')",
         "dispatched=all(q['co_admissions']>0 for q in queues if q['pool_mode'] in ('colocated','diverse')) and all(q['changed_device_choices']>0 for q in queues if q['pool_mode']=='diverse')",1)]
    for a,b,n in replacements:
        assert source.count(a)==n,(a,source.count(a),n);source=source.replace(a,b)
    exec(compile(source,'independent-diverse-readout','exec'),old.__dict__)


configure()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');p.add_argument('--gpu-seconds',type=int,required=True)
    a=p.parse_args();old.analyze(a.root,a.out,a.gpu_seconds)
