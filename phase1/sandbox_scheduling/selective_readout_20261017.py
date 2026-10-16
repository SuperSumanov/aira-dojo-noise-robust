"""Full32 failure-inclusive search endpoints, fixed two-replicate quality gate."""
import argparse,inspect,math,statistics
import colocation_readout_20261016 as old
from selective_pool_20261017 import independent_audit
ORDER=('shared','selective','selective','shared');TASKS=old.TASKS


def quality(rows):
    by=[]
    for b,mode in enumerate(ORDER):
        for task in TASKS:
            v=[r['score'] for r in rows if r['block']==b and r['task']==task]
            assert len(v)==4 and all(type(x) in (int,float) and math.isfinite(x) for x in v)
            by.append(dict(block=b,repeat=b//2,pool_mode=mode,task=task,best=max(v,key=lambda x:old.SIGN[task]*x),
                median=statistics.median(v),sample_sd=statistics.stdev(v),n=4))
    cs=[]
    for rep in range(2):
        for task in TASKS:
            d={r['pool_mode']:r for r in by if r['repeat']==rep and r['task']==task}
            cs.append(dict(repeat=rep,task=task,baseline_best=d['shared']['best'],selective_best=d['selective']['best'],
                oriented_delta=old.SIGN[task]*(d['selective']['best']-d['shared']['best']),
                median_delta=old.SIGN[task]*(d['selective']['median']-d['shared']['median'])))
    return by,cs,all(r['oriented_delta']>=(.001 if r['task']==TASKS[1] else -1e-12) for r in cs)


def configure():
    original=getattr(old,'_selective_original_analyze',old.analyze);old._selective_original_analyze=original
    old.__file__=__file__;old.ORDER=ORDER;old.quality=quality;old.verify_queue=independent_audit
    source=inspect.getsource(original)
    before="dispatched=all(q['co_admissions']>0 for q in queues if q['pool_mode']=='colocated')"
    after="dispatched=all(q['co_admissions']>0 and q['protected_deferrals']>0 for q in queues if q['pool_mode']=='selective')"
    assert source.count(before)==1;source=source.replace(before,after)
    exec(compile(source,'selective-readout','exec'),old.__dict__)


configure()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');p.add_argument('--gpu-seconds',type=int,required=True)
    a=p.parse_args();old.analyze(a.root,a.out,a.gpu_seconds)
