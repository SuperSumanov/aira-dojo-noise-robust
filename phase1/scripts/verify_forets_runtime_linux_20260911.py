"""Linux CPU-only timer/signal/actual-import check. Never creates a pool or step."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace

os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
                  LITELLM_LOCAL_MODEL_COST_MAP='True',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def audit(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.connect_ex','socket.sendto','os.system','os.posix_spawn'):
        raise RuntimeError('CPU verification forbids external calls')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        path=Path(os.fsdecode(args[0])).absolute()
        if path.name=='.env' or path.name=='env_variables.json' or any(x in path.parts for x in
            ('prospective_decision_v1','mle-bench-data','forets-critic-incoming-20260908-3lcjjcwq')):
            raise RuntimeError('model/data/credential read forbidden')


sys.addaudithook(audit)
import forets_block_runtime_20260911 as r
import forets_block_collect_20260911 as collector

root=Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')
source=root/'source'
os.environ.update(LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
    SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
    DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
sys.path.insert(0,str(source/'src'))
from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
assert hashlib.sha256(Path(inspect.getfile(SrunPoolLauncher)).read_bytes()).hexdigest()==r.POOL_SHA
class WiredPool(r.RuntimePoolControl,SrunPoolLauncher): pass
assert WiredPool.run.__qualname__=='BlockPoolControl.run'
assert WiredPool._cancel_running.__qualname__=='RuntimePoolControl._cancel_running'
assert WiredPool._validate_paths_on_node.__qualname__=='RuntimePoolControl._validate_paths_on_node'

before=time.monotonic()
budget=r.Budget(before,before+16800)
try:
    with r.interrupt_at(budget,before+0.05): time.sleep(2)
    raise AssertionError('timer failed to interrupt blocking call')
except TimeoutError: pass
elapsed=time.monotonic()-before
assert elapsed<1 and signal.getitimer(signal.ITIMER_REAL)==(0.,0.)

events=[]
class FakePool:
    def _recover(self): events.append('pristine')
    def _validate_paths_on_node(self): events.append('paths')
    def run(self): raise AssertionError('SIGTERM must stop before worker dispatch')
class FakeService:
    budget=r.Budget(time.monotonic(),time.monotonic()+16800)
    def start(self): os.kill(os.getpid(),signal.SIGTERM)
old=signal.getsignal(signal.SIGTERM)
def cleanup(pool,service):
    events.append('cleanup')
    return {'remote_step_cleanup_confirmed':True}
result=r.run_lifecycle(FakePool(),FakeService(),cleanup=cleanup)
assert result['error_type']=='InterruptedError' and events==['pristine','paths','cleanup']
assert signal.getsignal(signal.SIGTERM)==old

bound=sum(len(r.inspect_draft(root,b)[1]) for b in (1,2))
try: r.execute_block(root,1,b'{}',node='gpu28',controller_commit='a'*40)
except RuntimeError as exc: assert 'release absent' in str(exc)
else: raise AssertionError('unreleased entry executed')
value=dict(role='linux_cpu_runtime_wiring_not_model_or_scheduler_result',
    observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),python=sys.version.split()[0],
    source_tree=r.inspect_draft.__globals__['TREE'],actual_configs_bound=bound,
    actual_pool_import_and_mro_verified=True,blocking_timer_interrupted=True,
    timer_elapsed_seconds=elapsed,startup_sigterm_cleanup_verified=True,
    release_denied_before_resources=True,pool_instances=0,gpu_submissions=0,api_calls=0,model_loads=0,
    module_sha256={name:hashlib.sha256(Path(r.__file__).with_name(name).read_bytes()).hexdigest() for name in
        ('forets_block_runtime_20260911.py','forets_block_collect_20260911.py')})
print(json.dumps(value,sort_keys=True))
