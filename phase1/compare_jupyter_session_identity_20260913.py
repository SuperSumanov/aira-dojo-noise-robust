"""Balanced transport experiment, no MLE/model/API and no kernel restarts."""
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
from unittest.mock import patch
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')

def run(output):
    os.umask(0o077);output=output.resolve(strict=True)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(output),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from dojo.core.interpreters.jupyter import jupyter_client as mod
    logging.root.handlers.clear();logging.basicConfig(filename=str(output/'identity.private.log'),level=logging.INFO)
    rows=[];begin=time.monotonic();modes=('omitted','aligned','unique_mismatch','omitted_delayed')
    for rep in range(4):
        for mode in modes[rep:]+modes[:rep]:
            server=None;client=None;row=dict(repetition=rep,mode=mode)
            with tempfile.TemporaryDirectory(prefix='identity-',dir=output) as tmp:
                try:
                    server=SingularityJupyterServer(working_dir=Path(tmp),superimage_directory=os.environ['SUPERIMAGE_DIR'],
                        superimage_version='2026-07-macos-v1',startup_timeout=30)
                    rest=server.get_client();kid=rest.start_kernel('python3');client=rest.get_kernel_client(kid)
                    row['initial_ready']=client.wait_for_ready(5);url=client._ws_app.url;client.stop();client=None
                    if mode=='omitted_delayed':time.sleep(1)
                    if mode in ('omitted','omitted_delayed'):client=rest.get_kernel_client(kid)
                    else:
                        original=mod.WebSocketApp
                        class Explicit(mod.JupyterKernelClient):
                            def __init__(self,url,headers):
                                def app(url,*a,**k):
                                    session=self._session_id if mode=='aligned' else uuid.uuid4().hex
                                    return original(url+'?session_id='+session,*a,**k)
                                with patch.object(mod,'WebSocketApp',app):super().__init__(url,headers)
                        client=Explicit(url,rest._get_headers())
                    t=time.monotonic();row['reconnected_ready']=client.wait_for_ready(5);row['probe_seconds']=time.monotonic()-t
                    client.stop();client=None;rest.delete_kernel(kid)
                except Exception as exc:row['exception']=type(exc).__name__
                finally:
                    if client is not None:client.stop()
                    if server is not None:server.stop()
            rows.append(row);print(json.dumps(row),flush=True)
    result=dict(role='balanced_identity_transport_not_mle',utc=dt.datetime.now(dt.timezone.utc).isoformat(),rows=rows,
        source_tree='35321718fef54f1907b469ab44334a30fe66b6cd',image='2026-07-macos-v1',job=os.environ.get('SLURM_JOB_ID'),
        node=os.environ.get('SLURMD_NODENAME'),elapsed=time.monotonic()-begin,api_calls=0,mle_executions=0,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (output/'identity-result.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
