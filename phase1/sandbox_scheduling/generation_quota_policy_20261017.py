"""Fixed total4 generation slots: partitioned2+2 versus a shared quota.

Both conditions use the SAME completion-first/FIFO arbitration across eligible
requests. Only quota eligibility differs. This is a work-conserving baseline,
not a novel scheduler, and cannot by itself establish a final-quality benefit.
"""
MODES=('partitioned','pooled')

def eligible_requests(state,mode):
    if mode not in MODES:raise ValueError('unknown quota')
    active=state['active']
    if len(active)>=4:return []
    return [r for r in state['waiting'] if mode=='pooled' or sum(a['task']==r['task'] for a in active)<2]

def choice(state,mode):
    eligible=eligible_requests(state,mode)
    return min(eligible,key=lambda r:(-int(r['role']=='analyze'),r['requested'],r['run'])) if eligible else None

def install(mode):
    if mode not in MODES:raise ValueError('unknown quota')
    import feedback_parent_policy_20261012 as parent
    def select(state,task,arm):
        # All workers in a pool make the same global decision while holding the
        # existing process-safe lock; only the selected worker can claim it.
        request=choice(state,mode)
        if request is None:return None,None
        target=parent.parent_choice(state,request['task'],arm) if request['role']=='improve' else None
        if request['role']=='improve' and target is None:return None,None
        return request['key'],target
    select.quota_mode=mode
    parent.select_request=select

def metadata_audit(events,mode):
    waiting={};active={};seen=set();borrowed=peak=0
    for e in events:
        kind=e['event'];key=e.get('key')
        if kind=='queued':
            r=e['request'];key=r['key'];assert key not in seen;seen.add(key);waiting[key]=r
        elif kind=='admitted':
            assert key in waiting
            # Independent priority/eligibility, not calling production choice.
            choices=[r for r in waiting.values() if len(active)<4 and
                (mode=='pooled' or sum(a['task']==r['task'] for a in active.values())<2)]
            assert choices
            chosen=sorted(choices,key=lambda r:(0 if r['role']=='analyze' else 1,r['requested'],r['run']))[0]
            assert chosen['key']==key
            borrowed+=sum(a['task']==chosen['task'] for a in active.values())>=2
            active[key]=waiting.pop(key);peak=max(peak,len(active))
        elif kind=='released':assert key in active;active.pop(key)
        elif kind=='cancelled':assert key in waiting;waiting.pop(key)
        elif kind not in ('parent_used','round_complete','abandoned','warm_start'):raise ValueError('unexpected event')
    assert not active and not waiting
    return dict(requests=len(seen),borrowed_admissions=borrowed,peak_active=peak,closed=True)
