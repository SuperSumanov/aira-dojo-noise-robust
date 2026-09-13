"""Actual original-image connection recovery, synthetic marker only, no MLE/API."""
import datetime as dt
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
from forets_environment_build_20260912 import read,write,encode,sha

def run(root):
    artifact=read(root/'artifact.json')
    for name,digest in artifact['source_files'].items():
        if sha((root/'source'/name).read_bytes())!=digest:raise ValueError('source drift')
    if os.environ.get('SLURMD_NODENAME')!='gpu28':raise ValueError('allocated original node required')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    logging.root.handlers.clear();logging.basicConfig(filename=str(root/'channel-live.private.log'),level=logging.INFO)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='channel-live-',dir=root) as d:
        for inject in (False,True):
            server=None;executor=None;t=time.monotonic()
            try:
                server=SingularityJupyterServer(working_dir=Path(d),
                    superimage_directory='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
                    superimage_version='2026-07-macos-v1',startup_timeout=30)
                executor=JupyterCodeExecutor(server,kernel_name='python3',timeout=15,output_dir=Path(d))
                kernel=executor._kernel_id;first=executor._jupyter_kernel_client;connections=[];dispatches=[]
                original_get=executor._jupyter_client.get_kernel_client
                def track_client(client):
                    original_execute=client.execute
                    def execute(code,**kwargs):
                        dispatches.append(sha(code.encode()))
                        return original_execute(code,**kwargs)
                    client.execute=execute;return client
                def get(k,**kwargs):
                    if k!=kernel:raise ValueError('kernel changed')
                    connections.append(k);return track_client(original_get(k,**kwargs))
                track_client(first);executor._jupyter_client.get_kernel_client=get
                if inject:
                    receive=first._receive_message
                    def blackhole(seconds):
                        deadline=time.monotonic()+seconds
                        while time.monotonic()<deadline:receive(max(.001,deadline-time.monotonic()))
                        return None
                    first._receive_message=blackhole
                def forbid(*a,**k):raise AssertionError('kernel mutation forbidden during recovery')
                with patch.object(executor._jupyter_client,'start_kernel',forbid),patch.object(executor._jupyter_client,'restart_kernel',forbid):
                    code="recovery_marker_count = globals().get('recovery_marker_count', 0) + 1\nprint('RECOVERY_COUNT', recovery_marker_count)"
                    outputs=[]
                    for count in (1,2):
                        result=executor.execute_code(code)
                        if result.exit_code!=0 or result.timed_out or ('RECOVERY_COUNT '+str(count)) not in '\n'.join(result.term_out):
                            raise ValueError('wrong actual marker result or duplicate execution')
                        outputs.append(count)
                    if len(dispatches)!=2 or len(connections)!=int(inject) or executor._kernel_id!=kernel:
                        raise ValueError('unexpected kernel/dispatch/channel count')
                rows.append(dict(injected_first_channel_receive_blackhole=inject,same_kernel=True,
                    replacements=len(connections),actual_execute_requests=len(dispatches),actual_kernel_marker_counts=outputs,
                    elapsed_seconds=time.monotonic()-t))
            finally:
                if executor is not None:executor.stop()
                if server is not None:server.stop()
    result=dict(status='PASSED_ORIGINAL_IMAGE_CHANNEL_MITIGATION_NOT_ROOT_CAUSE',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_tree=artifact['source_tree'],rows=rows,job=os.environ.get('SLURM_JOB_ID'),node='gpu28',api_calls=0,mle_executions=0,
        image='2026-07-macos-v1',script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Injected client receive blackhole is not the observed gateway no-egress fault. Confirms bounded same-kernel replacement and no duplicated execution, not disappearance of natural faults.')
    print(json.dumps(dict(result=result,sha256=write(root/'channel-live.json',encode(result)))),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
