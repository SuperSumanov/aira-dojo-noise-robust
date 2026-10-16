"""Task-diverse device tie-break; shared FIFO order and lease limits unchanged.

Known baseline qualification, not a novel scheduler. Uses task identity only,
never scores, future program contents or protected data. Empty GPU first; among
equally occupied devices, prefer an incumbent from the other task. Falls back
without waiting if none exists. Production task is encoded by episode index%2.
"""
from colocation_pool_20261016 import State as OriginalState


def task_of(key):
    prefix=key.split(':',1)[0]
    if not prefix.isdigit():raise ValueError('numeric episode prefix required')
    return int(prefix)%2


def choose(queue,active,key,mode):
    if not queue or queue[0]['key']!=key:return None
    cap=1 if mode=='shared' else 2
    counts={d:sum(x['device']==d for x in active.values()) for d in range(4)}
    choices=[d for d in range(4) if counts[d]<cap]
    if not choices:return None
    def order(d):
        conflict=sum(task_of(k)==task_of(key) for k,v in active.items() if v['device']==d)
        return (counts[d],conflict if mode=='diverse' else 0,d)
    return min(choices,key=order)


class State(OriginalState):
    def __init__(self,mode,queue=None,active=None,finished=None):
        if mode not in ('shared','colocated','diverse'):raise ValueError('unknown mode')
        super().__init__('colocated' if mode=='diverse' else mode,queue,active,finished)
        self.mode=mode
        for item in self.queue:task_of(item['key'])
        for key in self.active:task_of(key)
    def request(self,key,home):
        task_of(key);super().request(key,home)
    def admit(self,key):
        item=next((x for x in self.queue if x['key']==key),None)
        if item is None:raise ValueError('unknown waiting request')
        device=choose(self.queue,self.active,key,self.mode)
        if device is None:return None
        self.queue.remove(item);self.active[key]=dict(home=item['home'],device=device)
        return device


def independent_audit(events,mode):
    waiting=[];active={};seen=set();requests={};last=float('-inf')
    co=changed=same=0;waits=[];peak=0;migrations=0
    for e in events:
        key=e['key'];assert e['time']>=last;last=e['time']
        if e['event']=='queued':
            assert key not in seen;seen.add(key);waiting.append(key);requests[key]=e
        elif e['event']=='admitted':
            assert waiting[0]==key
            count=[sum(d==i for d in active.values()) for i in range(4)]
            eligible=[i for i in range(4) if count[i]<(1 if mode=='shared' else 2)]
            assert eligible
            baseline=min(eligible,key=lambda d:(count[d],d))
            conflict=lambda d:sum(task_of(k)==task_of(key) for k,v in active.items() if v==d)
            expected=min(eligible,key=lambda d:(count[d],conflict(d) if mode=='diverse' else 0,d))
            assert e['device']==expected
            co+=count[expected]>0;changed+=expected!=baseline
            same+=bool(count[expected] and conflict(expected))
            migrations+=expected!=requests[key]['home']
            waits.append(e['time']-requests[key]['time']);peak=max(peak,count[expected]+1)
            active[key]=expected;waiting.pop(0)
        elif e['event']=='released':assert active.pop(key)==e['device']
        elif e['event']=='queue_cancelled':waiting.remove(key)
        else:raise ValueError('unknown event')
        assert len(waiting)==e['queued'] and len(active)==e['active']
    assert not active and not waiting
    import statistics
    return dict(admissions=len(waits),migrations=migrations,co_admissions=co,
        changed_device_choices=changed,same_task_co_admissions=same,
        peak_device_leases=peak,wait_total=sum(waits),wait_median=statistics.median(waits) if waits else None)
