"""Same fixed32 quality gate plus independent generation-eligibility audit."""
import argparse,inspect,math,statistics
import colocation_readout_20261016 as old
from generation_quota_policy_20261017 import metadata_audit
ORDER=('partitioned','pooled','pooled','partitioned')
TASKS=old.TASKS

def quality(rows):
    by=[]
    for b,mode in enumerate(ORDER):
        for task in TASKS:
            v=[r['score'] for r in rows if r['block']==b and r['task']==task]
            assert len(v)==4 and all(type(x) in (float,int) and math.isfinite(x) for x in v)
            by.append(dict(block=b,repeat=b//2,pool_mode='shared',quota_mode=mode,task=task,
                best=max(v,key=lambda x:old.SIGN[task]*x),median=statistics.median(v),sample_sd=statistics.stdev(v),n=4))
    cs=[]
    for rep in range(2):
        for task in TASKS:
            d={r['quota_mode']:r for r in by if r['repeat']==rep and r['task']==task}
            a,b=d['partitioned'],d['pooled']
            cs.append(dict(repeat=rep,task=task,partitioned_best=a['best'],pooled_best=b['best'],
                oriented_delta=old.SIGN[task]*(b['best']-a['best']),median_delta=old.SIGN[task]*(b['median']-a['median'])))
    return by,cs,all(x['oriented_delta']>=(.001 if x['task']==TASKS[1] else -1e-12) for x in cs)

def generation_audit(events,mode):
    structural=metadata_audit(events,mode)
    # Reuse ONLY the independent parent/archive audit. Its old2/task assertion
    # is replaced by total4; metadata_audit separately checks the actual quota
    # and the newly explicit common global request order without production code.
    import feedback_parent_readout_20261012 as reader
    source=inspect.getsource(reader.audit)
    a="assert sum(requests[x]['task']==requests[k]['task'] for x in active)<2"
    assert source.count(a)==1;source=source.replace(a,'assert len(active)<4')
    ns=dict(vars(reader));exec(compile(source,'quota-independent-parent-audit','exec'),ns)
    parent=ns['audit'](events,'greedy')
    return dict(quota_mode=mode,**structural,parent_archive_audit=parent)

def metadata_only(events):
    out=[]
    for e in events:
        if e['event'] not in ('queued','admitted','released','cancelled'):continue
        r={k:e[k] for k in ('event','time','key') if k in e}
        if e['event']=='queued':r['request']={k:e['request'][k] for k in ('key','task','role','requested','run')}
        out.append(r)
    return out

def configure():
    original=getattr(old,'_quota_original_analyze',old.analyze);old._quota_original_analyze=original
    old.__file__=__file__;old.ORDER=('shared',)*4;old.quality=quality
    old.generation_audit=generation_audit;old.metadata_only=metadata_only
    source=inspect.getsource(original)
    replacements=(
      ('identities=[];queues=[];bindings=[];partitions=[]','identities=[];queues=[];bindings=[];partitions=[];generation_quotas=[]'),
      ("        audit(lines(root/f'generation-{b}/events.jsonl'),'greedy')", "        ge=lines(root/f'generation-{b}/events.jsonl')\n        mode=p['schedule'][8*b]['quota_mode']\n        generation_quotas.append(dict(block=b,**generation_audit(ge,mode)))\n        write(out/f'generation-{b}.json',metadata_only(ge))"),
      ("dispatched=all(q['co_admissions']>0 for q in queues if q['pool_mode']=='colocated')", "dispatched=all(q['borrowed_admissions']>0 for q in generation_quotas if q['quota_mode']=='pooled')"),
      ('runtime_input_gate=inputs_ok,actual_mode_gate=actual,dispatch_changed=dispatched,queues=queues,',
       'runtime_input_gate=inputs_ok,actual_mode_gate=actual,dispatch_changed=dispatched,queues=queues,generation_quotas=generation_quotas,'))
    for a,b in replacements:
        assert source.count(a)==1;source=source.replace(a,b)
    exec(compile(source,'quota-readout','exec'),old.__dict__)

configure()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');p.add_argument('--gpu-seconds',type=int,required=True)
    a=p.parse_args();old.analyze(a.root,a.out,a.gpu_seconds)
