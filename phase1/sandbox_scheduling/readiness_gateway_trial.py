"""Independent48 empty kernels with client+gateway counters; <=0.25 GPUh.

No fix, retry, timeout extension, candidate execution, data or model. The
additional per-event count I/O precludes any performance claim. Prior48 stays.
"""
import argparse
import inspect
from pathlib import Path
import shutil
import sys

import readiness_transport_trial as trial

trial.R=trial.B/'scheduling-readiness-gateway-20261009-v1'
trial.NAME='readiness_gateway_trial.py'

original_runtime=trial.runtime
def runtime():
    module=original_runtime()
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    server._JUPYTER_BOOTSTRAP="import runpy; runpy.run_path('/workspace/gateway_counter.py',run_name='__main__')"
    return module
trial.runtime=runtime

# The generated native shim must import this configured wrapper, not its base.
source=inspect.getsource(trial.prepare)
old="from readiness_transport_trial import runtime"
if source.count(old)!=1:raise ValueError('native shim changed')
source=source.replace(old,'from readiness_gateway_trial import runtime')
old="(NAME,'bounded_readiness.py','lifecycle_pilot.py','live_identity.py')"
new="(NAME,'readiness_transport_trial.py','gateway_counter.py','bounded_readiness.py','lifecycle_pilot.py','live_identity.py')"
if source.count(old)!=1:raise ValueError('source copy interface changed')
source=source.replace(old,new)
old="(R/'empty-data').mkdir();(R/'bin').mkdir()"
new="""(R/'empty-data').mkdir();(R/'bin').mkdir()
    for row in schedule():
        shutil.copyfile(R/'gateway_counter.py',R/f'episode-{row["index"]}/work/gateway_counter.py')"""
if source.count(old)!=1:raise ValueError('empty fixture interface changed')
source=source.replace(old,new)
old="Does startup concurrency produce an observable kernel-info transport failure? No candidate retrial or effect gate override."
source=source.replace(old,"Where are kernel-info messages lost between native client, gateway and kernel? Client and gateway enum counters only; per-event I/O makes timings diagnostic, not a speed comparison. No fix or candidate retrial.")
exec(compile(source,'gateway-diagnosis-prepare','exec'),trial.__dict__)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','controller','worker'])
    parser.add_argument('--commit');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.mode=='prepare':trial.prepare(args.commit)
    elif args.mode=='submit':trial.submit()
    elif args.mode=='controller':sys.exit(trial.controller())
    else:
        if args.index not in range(48):raise ValueError('fixed48 index')
        sys.exit(trial.worker(args.index))
