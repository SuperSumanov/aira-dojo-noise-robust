"""Bounded transport-only reproduction in the existing image; no MLE/API/GPU.

Up to 32 fresh servers, stopping at the first 120-second readiness failure.
On failure compare control/direct-ZMQ/fresh connections, never run ML code.
Not GPU acceptance, model validation, task results, or a deployed repair.
"""
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')
IMAGE='/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'


def ping(client,channel,seconds=10):
    mid=client._send_message(content={},channel=channel,message_type='kernel_info_request')
    end=time.monotonic()+seconds;types=[];foreign=0
    while time.monotonic()<end:
        msg=client._receive_message(max(.001,end-time.monotonic()))
        if msg is None:break
        if msg.get('parent_header',{}).get('msg_id')!=mid:foreign+=1;continue
        types.append(msg.get('msg_type'))
        if msg.get('msg_type')=='kernel_info_reply':break
    return dict(channel=channel,reply='kernel_info_reply' in types,matching_types=types,foreign=foreign)


def run(output, *, keep_gpu=False, max_servers=32):
    output=output.resolve(strict=True)
    os.umask(0o077)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(output),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0,str(ROOT/'source/src'))
    import dojo.core.interpreters.jupyter.singularity_jupyter_server as server_module
    import dojo.core.interpreters.jupyter.jupyter_client as client_module
    # The diagnostic starts no task process and intentionally exposes no GPU.
    original=server_module._build_singularity_command
    def cpu_command(**kwargs):
        args=original(**kwargs)
        if args.count('--nv')!=1:raise ValueError('image launch shape')
        if not keep_gpu:args.remove('--nv')
        return args
    for h in logging.root.handlers[:]:logging.root.removeHandler(h)
    logging.basicConfig(filename=str(output/'transport.private.log'),level=logging.INFO)
    start=time.monotonic();records=[]
    with (output/'transport-intent.json').open('x') as f:
        json.dump(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),max_servers=max_servers,
            image=IMAGE,source_tree='35321718fef54f1907b469ab44334a30fe66b6cd',gpu=keep_gpu,mle=False,paid_api=False,
            job=os.environ.get('SLURM_JOB_ID'),node=os.environ.get('SLURMD_NODENAME')) ,f)
    with patch.object(server_module,'_build_singularity_command',cpu_command):
        for i in range(max_servers):
            if time.monotonic()-start>(600 if keep_gpu else 330):break
            with tempfile.TemporaryDirectory(prefix='transport-',dir=output) as temp:
                server=None;client=None
                t=time.monotonic();record=dict(trial=i)
                try:
                    server=server_module.SingularityJupyterServer(working_dir=Path(temp),
                        superimage_directory=str(Path(IMAGE).parent),superimage_version='2026-07-macos-v1',startup_timeout=30)
                    rest=server.get_client();kernel=rest.start_kernel('python3');client=rest.get_kernel_client(kernel)
                    record['ready']=client.wait_for_ready(120)
                    record['elapsed']=time.monotonic()-t
                    if record['ready']:
                        record['control']=ping(client,'control',5)
                    else:
                        record['control']=ping(client,'control',10)
                        record['kernel_rest_states']=[x.get('execution_state') for x in rest.list_kernels() if x.get('id')==kernel]
                        files=list(Path(temp).rglob('kernel-'+kernel+'.json'))
                        record['connection_file_count']=len(files)
                        if len(files)==1:
                            from jupyter_client import BlockingKernelClient
                            zmq=BlockingKernelClient(connection_file=str(files[0]));zmq.load_connection_file();zmq.start_channels()
                            try:
                                mid=zmq.kernel_info();end=time.monotonic()+10;reply=False
                                while time.monotonic()<end:
                                    m=zmq.get_shell_msg(timeout=max(.001,end-time.monotonic()))
                                    if m.get('parent_header',{}).get('msg_id')==mid:reply=True;break
                                record['direct_zmq_reply']=reply
                            except Exception as e:record['direct_zmq_exception']=type(e).__name__
                            finally:zmq.stop_channels()
                        record['fresh_connections']=[]
                        for aligned in ((False,True) if i%2==0 else (True,False)):
                            original_app=client_module.WebSocketApp
                            class Aligned(client_module.JupyterKernelClient):
                                def __init__(self,url,headers):
                                    def app(url,*args,**kwargs):
                                        return original_app(url+'?session_id='+self._session_id,*args,**kwargs)
                                    with patch.object(client_module,'WebSocketApp',app):super().__init__(url,headers)
                            fresh=(Aligned(client._ws_app.url,rest._get_headers()) if aligned else rest.get_kernel_client(kernel))
                            try:record['fresh_connections'].append(dict(session_aligned=aligned,ready=fresh.wait_for_ready(15)))
                            finally:fresh.stop()
                    client.stop();client=None;rest.delete_kernel(kernel)
                except Exception as exc:
                    record['exception']=type(exc).__name__
                finally:
                    if client is not None:client.stop()
                    if server is not None:server.stop()
                records.append(record)
                print(json.dumps(record),flush=True)
                if record.get('ready') is not True or 'exception' in record:break
    result=dict(role='transport_only_not_efficacy',utc=dt.datetime.now(dt.timezone.utc).isoformat(),rows=records,
        elapsed=time.monotonic()-start,api_calls=0,gpu_jobs=int(keep_gpu),mle_executions=0,
        job=os.environ.get('SLURM_JOB_ID'),node=os.environ.get('SLURMD_NODENAME'),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitation='No-reproduction does not establish a fix. Follow-up connections change timing and connection identity together.')
    with (output/'transport-result.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--keep-gpu',action='store_true')
    p.add_argument('--max-servers',type=int,default=32);a=p.parse_args()
    if not 1<=a.max_servers<=64:raise ValueError('bounded trials')
    if a.keep_gpu and (os.environ.get('SLURMD_NODENAME')!='gpu28' or not os.environ.get('SLURM_JOB_ID')):
        raise ValueError('explicit allocated gpu28 diagnostic only')
    run(a.output,keep_gpu=a.keep_gpu,max_servers=a.max_servers)
