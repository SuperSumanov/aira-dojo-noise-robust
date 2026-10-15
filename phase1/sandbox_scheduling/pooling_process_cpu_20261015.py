"""Linux process/lock/deadline test of the exact production lease, CPU only."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import time
from shared_pool_20261015 import Lease,initialize,audit,locked


def worker(args):
    path,index=args
    for operation in range(3):
        end=time.monotonic()+10
        def check():
            if time.monotonic()>end:raise TimeoutError('test deadline')
        lease=Lease(path,f'{index}:{operation}',check,lambda *a,**kw:None)
        lease.acquire()
        with locked(path) as state:
            assert state.active[lease.key]['device']==lease.device
        time.sleep(.015);lease.release(cleanup_verified=True)
    return index


if __name__=='__main__':
    results=[]
    with tempfile.TemporaryDirectory(prefix='pool-process-cpu-') as d:
        for mode in ('fixed','shared'):
            path=Path(d)/mode;initialize(path,mode)
            with concurrent.futures.ProcessPoolExecutor(max_workers=8) as p:
                assert sorted(p.map(worker,[(path,i) for i in range(8)]))==list(range(8))
            events=[json.loads(x) for x in (path/'events.jsonl').read_text().splitlines()]
            report=audit(events,mode);assert report['admissions']==24 and report['all_released']
            results.append(dict(mode=mode,**report))
        path=Path(d)/'cancel';initialize(path,'fixed')
        held=Lease(path,'0:0',lambda:None,lambda *a,**kw:None);held.acquire()
        def expired():raise TimeoutError('synthetic expiration')
        waiting=Lease(path,'1:0',expired,lambda *a,**kw:None)
        try:waiting.acquire()
        except TimeoutError:pass
        else:raise AssertionError('deadline did not cancel')
        assert not waiting.held;held.release(cleanup_verified=True)
        events=[json.loads(x) for x in (path/'events.jsonl').read_text().splitlines()]
        assert audit(events,'fixed')['all_released']
    print(json.dumps(dict(passed=True,processes=8,conditions=results,deadline_cancel=True,gpu_calls=0,model_calls=0)))
