"""Observe original provisioner exits; no retry, signal, env or source reads."""
import hashlib,inspect,json,time
from pathlib import Path

POLL_SHA='12ca1197bc501486308321bf4739b8661ff4acb7032c7315dfc74c38ffbdf2ed'
LAUNCH_SHA='5a5d3e639018fd53cf6228502194ab00931c8a96266861b7f42b2e90f4e17664'

def wrap(cls,emit):
    poll=cls.poll;launch=cls.launch_kernel;seen=set()
    def safe(event):
        try:emit(event)
        except Exception:pass # Missing observer evidence fails the independent gate.
    async def observed_poll(self,*args,**kwargs):
        result=await poll(self,*args,**kwargs)
        process=getattr(self,'process',None)
        if process is not None and result is not None:
            key=(int(process.pid),int(result))
            if key not in seen:
                seen.add(key);safe(dict(event='exit_observed',pid=key[0],returncode=key[1],time=time.time()))
        return result
    async def observed_launch(self,*args,**kwargs):
        result=await launch(self,*args,**kwargs)
        safe(dict(event='launched',pid=int(self.process.pid),time=time.time()))
        return result
    cls.poll=observed_poll;cls.launch_kernel=observed_launch

def install():
    from jupyter_client.provisioning.local_provisioner import LocalProvisioner as cls
    assert hashlib.sha256(inspect.getsource(cls.poll).encode()).hexdigest()==POLL_SHA
    assert hashlib.sha256(inspect.getsource(cls.launch_kernel).encode()).hexdigest()==LAUNCH_SHA
    path=Path('/workspace/kernel-lifecycle.jsonl')
    def emit(row):
        with path.open('a') as f:f.write(json.dumps(row,sort_keys=True)+'\n')
    wrap(cls,emit)
    with Path('/workspace/kernel-lifecycle-installed.json').open('x') as f:
        json.dump(dict(poll_sha256=POLL_SHA,launch_sha256=LAUNCH_SHA,no_retry=True,no_signals=True),f)

if __name__!='__main__':
    # The sitecustomize hook is restricted to the original gateway CLI child.
    import os,sys
    if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':install()
