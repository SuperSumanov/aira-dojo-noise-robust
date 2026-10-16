"""Outcome-blind shared FIFO with one or two container leases per GPU.

Both arms acquire before container startup, hold through verified cleanup, and
use the SAME exact-device container boundary. No lease timeout/reclamation.
Host orchestration is trusted; its private state is never container-mounted.
"""
import contextlib
import json
import os
from pathlib import Path
import signal
import threading
import time


class State:
    def __init__(self, mode, queue=None, active=None, finished=None):
        if mode not in ('fixed', 'shared', 'colocated'):
            raise ValueError('unknown pool mode')
        self.mode, self.queue = mode, list(queue or [])
        self.active, self.finished = dict(active or {}), list(finished or [])
        ids = [x['key'] for x in self.queue]+list(self.active)+self.finished
        devices = [x['device'] for x in self.active.values()]
        limit = 2 if mode == 'colocated' else 1
        if len(ids)!=len(set(ids)) or any(devices.count(d)>limit for d in devices):
            raise ValueError('duplicate key/device')
        if any(type(x) is not int or not 0<=x<4 for x in devices):
            raise ValueError('invalid device')

    def request(self, key, home):
        if type(home) is not int or not 0<=home<4:
            raise ValueError('invalid home')
        if key in [x['key'] for x in self.queue]+list(self.active)+self.finished:
            raise ValueError('duplicate request')
        self.queue.append(dict(key=key,home=home))

    def admit(self, key):
        item=next((x for x in self.queue if x['key']==key),None)
        if item is None: raise ValueError('unknown waiting request')
        busy={x['device'] for x in self.active.values()}
        if self.mode in ('shared','colocated'):
            if self.queue[0]['key']!=key:return None
            counts={d:sum(x['device']==d for x in self.active.values()) for d in range(4)}
            limit=2 if self.mode=='colocated' else 1
            free=[d for d in range(4) if counts[d]<limit]
            if not free:return None
            device=min(free,key=lambda d:(counts[d],d))
        else:
            earlier=next(x for x in self.queue if x['home']==item['home'])
            if earlier['key']!=key or item['home'] in busy:return None
            device=item['home']
        self.queue.remove(item);self.active[key]=dict(home=item['home'],device=device)
        return device

    def release(self,key,clean):
        if clean is not True or key not in self.active:raise ValueError('unsafe release')
        del self.active[key];self.finished.append(key)

    def cancel(self,key):
        item=next((x for x in self.queue if x['key']==key),None)
        if item is None:raise ValueError('cannot cancel active/missing request')
        self.queue.remove(item);self.finished.append(key)

    def value(self):return dict(mode=self.mode,queue=self.queue,active=self.active,finished=self.finished)


def emit(path,event):
    raw=(json.dumps(event,sort_keys=True,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        if os.write(fd,raw)!=len(raw):raise OSError('short append')
    finally:os.close(fd)


def initialize(root,mode):
    root=Path(root);root.mkdir(mode=0o700)
    (root/'mutex').touch(exist_ok=False)
    with (root/'state.json').open('x') as f:json.dump(State(mode).value(),f)


@contextlib.contextmanager
def locked(root):
    import fcntl
    root=Path(root)
    with (root/'mutex').open('r+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        prior=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGALRM})
        try:
            state=State(**json.loads((root/'state.json').read_text()))
            yield state
            tmp=root/f'.state-{os.getpid()}-{threading.get_ident()}'
            with tmp.open('x') as out:json.dump(state.value(),out,allow_nan=False)
            os.replace(tmp,root/'state.json')
        finally:
            fcntl.flock(f,fcntl.LOCK_UN)
            signal.pthread_sigmask(signal.SIG_SETMASK,prior)


class Lease:
    def __init__(self,directory,key,check_deadline,record):
        self.directory=Path(directory);self.key=key
        self.check_deadline,self.record=check_deadline,record
        self.index=int(key.split(':')[0]);self.home=(self.index%8)//2
        self.held=False;self.wait_seconds=0.;self.device=None

    def event(self,kind,state):
        emit(self.directory/'events.jsonl',dict(event=kind,key=self.key,home=self.home,
             device=self.device,time=time.time(),queued=len(state.queue),active=len(state.active)))

    def acquire(self):
        if self.held:return
        start=time.monotonic()
        try:
            with locked(self.directory) as state:
                state.request(self.key,self.home);self.event('queued',state)
            while True:
                self.check_deadline()
                with locked(self.directory) as state:
                    device=state.admit(self.key)
                    if device is not None:
                        self.device=device;self.held=True
                        self.event('admitted',state)
                        break
                time.sleep(.025)
        except BaseException:
            with locked(self.directory) as state:
                self.held=self.key in state.active
                if self.held:self.device=state.active[self.key]['device']
                if any(x['key']==self.key for x in state.queue):
                    state.cancel(self.key);self.event('queue_cancelled',state)
            self.wait_seconds=time.monotonic()-start
            raise
        self.wait_seconds=time.monotonic()-start
        self.record('admitted',wait_seconds=self.wait_seconds,device=self.device)

    def release(self,*,cleanup_verified):
        if not self.held:return
        with locked(self.directory) as state:
            state.release(self.key,cleanup_verified);self.event('released',state)
        self.held=False;self.record('released',device=self.device)


def assigned(root,block,index):
    with locked(Path(root)/f'pool-{block}') as state:
        active=[(k,v) for k,v in state.active.items() if int(k.split(':')[0])==index]
        if len(active)!=1:raise ValueError('container requires one live device lease')
        return active[0]


def audit(events,mode):
    state=State(mode);count=migrations=0
    for e in events:
        k=e['key']
        if e['event']=='queued':state.request(k,e['home'])
        elif e['event']=='admitted':
            d=state.admit(k)
            if d is None or d!=e['device']:raise ValueError('incorrect FIFO dispatch')
            count+=1;migrations+=d!=e['home']
        elif e['event']=='released':state.release(k,True)
        elif e['event']=='queue_cancelled':state.cancel(k)
        else:raise ValueError('unknown event')
        if e['queued']!=len(state.queue) or e['active']!=len(state.active):
            raise ValueError('event/state mismatch')
    return dict(admissions=count,migrations=migrations,all_released=not state.active and not state.queue)
