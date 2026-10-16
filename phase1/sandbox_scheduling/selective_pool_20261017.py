"""Simple task-specific sharing control, NOT a general semantic scheduler.

In this known two-task development cohort, odd episode indices are Denoise.
Those leases are exclusive; only two Aerial leases may share. FIFO request
order, empty-first placement, fixed CPU shares and deadlines remain unchanged.
No waiting is introduced solely to create a preferred pair.
"""
from colocation_pool_20261016 import State as OriginalState


def protected(key):
    prefix=key.split(':',1)[0]
    if not prefix.isdigit():raise ValueError('numeric episode prefix required')
    return int(prefix)%2==1


def eligible(active,key,mode):
    out=[]
    for device in range(4):
        members=[k for k,v in active.items() if v['device']==device]
        if not members or (mode=='selective' and len(members)<2 and not protected(key)
                           and all(not protected(k) for k in members)):
            out.append(device)
    return out


class State(OriginalState):
    def __init__(self,mode,queue=None,active=None,finished=None):
        if mode not in ('shared','selective'):raise ValueError('unknown mode')
        super().__init__('colocated' if mode=='selective' else mode,queue,active,finished)
        self.mode=mode
        for device in range(4):
            keys=[k for k,v in self.active.items() if v['device']==device]
            if len(keys)>1 and any(protected(k) for k in keys):raise ValueError('protected lease shared')
    def request(self,key,home):protected(key);super().request(key,home)
    def admit(self,key):
        item=next((x for x in self.queue if x['key']==key),None)
        if item is None:raise ValueError('unknown waiting request')
        if self.queue[0]['key']!=key:return None
        choices=eligible(self.active,key,self.mode)
        if not choices:return None
        device=min(choices,key=lambda d:(sum(v['device']==d for v in self.active.values()),d))
        self.queue.remove(item);self.active[key]=dict(home=item['home'],device=device);return device


def independent_audit(events,mode):
    assert mode in ('shared','selective')
    waiting=[];active={};seen=set();requests={};waits=[];last=float('-inf')
    migrations=co=peak=protected_deferrals=0;deferred=set()
    for e in events:
        key=e['key'];assert e['time']>=last;last=e['time']
        if e['event']=='queued':
            assert key not in seen;seen.add(key);waiting.append(key);requests[key]=e
        elif e['event']=='admitted':
            assert waiting[0]==key
            count=[sum(d==i for d in active.values()) for i in range(4)]
            available=[]
            for d in range(4):
                members=[k for k,v in active.items() if v==d]
                if not members or (mode=='selective' and len(members)==1 and not protected(key) and not protected(members[0])):
                    available.append(d)
            assert available and e['device']==min(available,key=lambda d:(count[d],d))
            co+=count[e['device']]>0;peak=max(peak,count[e['device']]+1)
            migrations+=e['device']!=requests[key]['home'];waits.append(e['time']-requests[key]['time'])
            active[key]=e['device'];waiting.pop(0)
        elif e['event']=='released':assert active.pop(key)==e['device']
        elif e['event']=='queue_cancelled':waiting.remove(key)
        else:raise ValueError('unknown event')
        assert e['active']==len(active) and e['queued']==len(waiting)
        if mode=='selective' and waiting and protected(waiting[0]):
            counts=[sum(d==i for d in active.values()) for i in range(4)]
            if all(counts) and any(n<2 for n in counts) and waiting[0] not in deferred:
                deferred.add(waiting[0]);protected_deferrals+=1
    assert not active and not waiting
    import statistics
    return dict(admissions=len(waits),migrations=migrations,co_admissions=co,
        peak_device_leases=peak,protected_deferrals=protected_deferrals,
        wait_total=sum(waits),wait_median=statistics.median(waits) if waits else None)
