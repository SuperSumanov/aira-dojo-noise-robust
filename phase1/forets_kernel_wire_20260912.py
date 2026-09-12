"""Bounded fresh-gateway reproduction; stop at first fault, never a failure-rate trial."""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import time

BASE = Path('/research/d7/spc/yzyang4')
SOURCE = BASE/'forets-wallclock-20260912-cxb9p0og/source'
MAX_TRIALS = 32
MAX_SECONDS = 1950

# Running the generic `jupyter` CLI execs a new interpreter and discards hooks.
# Invoke the identical installed gateway entry point in this process instead.
DIAGNOSTIC_BOOTSTRAP = (
    "import sys, runpy, site; from pathlib import Path; "
    "Path(site.getusersitepackages()).mkdir(parents=True, exist_ok=True); "
    "assert sys.argv[1] == 'kernelgateway'; sys.argv.pop(1); "
    "sys.path.insert(0, '/workspace'); import kernel_wire_hook_20260912; "
    "runpy.run_module('kernel_gateway', run_name='__main__')"
)


def trace_is_observable(trace, ready):
    counts = trace.get('event_counts', {})
    if counts.get('instrumentation_loaded') != 1 or counts.get('instrumentation_error', 0):
        return False
    if not counts.get('server_connect') or not counts.get('server_incoming'):
        return False
    return not ready or trace.get('matched_egress', {}).get('shell:kernel_info_reply', 0) > 0


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)


def setup(root):
    logging.disable(logging.CRITICAL)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost', LOGGING_DIR=str(root),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'), MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    for name in ('DOJO_WORKER_IDENTITY_PATH', 'FORETS_NATIVE_RELEASE', 'FORETS_CURRENT_POOL_ROOT', 'FORETS_CLOSED_POOL_ROOT'):
        os.environ.pop(name, None)
    sys.path[:0] = [str(root), str(SOURCE/'src')]
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server_module
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    from dojo.core.interpreters.jupyter.jupyter_interpreter import _gateway_port
    # Instrument an isolated diagnostic process, not the image or source files.
    server_module._JUPYTER_BOOTSTRAP = DIAGNOSTIC_BOOTSTRAP
    return server_module.SingularityJupyterServer, JupyterKernelClient, _gateway_port


def control_check(kernel, limit=8.):
    start = time.monotonic()
    ident = kernel._send_message(content={}, channel='control', message_type='kernel_info_request')
    types = []
    while time.monotonic()-start < limit:
        msg = kernel._receive_message(min(1., limit-(time.monotonic()-start)))
        if msg is not None and msg.get('parent_header', {}).get('msg_id') == ident:
            types.append(msg.get('msg_type'))
            if msg.get('msg_type') == 'kernel_info_reply':
                return dict(reply=True, message_types=types, seconds=time.monotonic()-start)
    return dict(reply=False, message_types=types, seconds=time.monotonic()-start)


def trial_trace(work, index):
    path = work/'kernel-wire.jsonl'
    if not path.exists():
        return dict(instrumentation_missing=True)
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    rows = [r for r in records if r['trial'] == index]
    return dict(events=len(rows), event_counts=dict(Counter(r['event'] for r in rows)),
        ingress=dict(Counter((r.get('channel') or 'none')+':'+str(r.get('message_type')) for r in rows if r['event']=='server_incoming')),
        matched_egress=dict(Counter((r.get('channel') or 'none')+':'+str(r.get('message_type')) for r in rows if r['event']=='server_outgoing' and r['parent_matches'])),
        unmatched_egress=dict(Counter(str(r.get('message_type')) for r in rows if r['event']=='server_outgoing' and not r['parent_matches'])),
        session_match_counts=dict(Counter(str(r['session_matches']) for r in rows if r['event']=='server_incoming')))


def run(root, commit):
    if socket.gethostname().split('.')[0] != 'gpu28' or not os.environ.get('SLURM_STEP_ID', '').isdigit():
        raise ValueError('dedicated gpu28 step required')
    limit = time.monotonic()+10
    while not (root/'launch.json').exists() and time.monotonic()<limit:
        time.sleep(.1)
    launch = json.loads((root/'launch.json').read_bytes())
    if launch['commit'] != commit or str(launch['job']) != os.environ['SLURM_JOB_ID']:
        raise ValueError('wrong allocation/source')
    for name, digest in launch['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('diagnostic code drift')
    artifact = json.loads((SOURCE.parent/'artifact.json').read_bytes())
    for name, digest in artifact['source_files'].items():
        if hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() != digest:
            raise ValueError('closed source drift')
    Server, Kernel, port_factory = setup(root)
    work = root/'workspace'
    work.mkdir(exist_ok=False)
    shutil.copyfile(root/'kernel_wire_hook_20260912.py', work/'kernel_wire_hook_20260912.py')
    port = port_factory()
    start = time.monotonic()
    rows = []
    write(root/'started.json', dict(job=launch['job'], commit=commit, utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_tree=artifact['source_tree'], maximum_trials=MAX_TRIALS, maximum_seconds=MAX_SECONDS,
        mode='fresh_gateway_fixed_port_stop_on_first_fault', api_calls=0, models=0, historical_candidate_reruns=0))
    stop = 'fixed_matrix_complete_without_reproduction'
    for index in range(MAX_TRIALS):
        if time.monotonic()-start > MAX_SECONDS-210:
            stop = 'bounded_time_stop'
            break
        row = dict(index=index, ready=False, marker_ok=False)
        server = None
        try:
            server = Server(working_dir=work, bind_inputs_dir=None,
                superimage_directory=BASE/'aira-dojo/build/superimage', superimage_version='2026-07-macos-v1',
                port=port, startup_timeout=90, env={'KERNEL_DIAG_TRIAL':str(index)})
            client = server.get_client()
            kid = client.start_kernel('python3')
            k = client.get_kernel_client(kid)
            try:
                timer = time.monotonic()
                row['ready'] = k.wait_for_ready(timeout_seconds=120)
                row['handshake_seconds'] = time.monotonic()-timer
                row['websocket_thread_alive'] = k._thread.is_alive()
                row['websocket_connected'] = bool(k._ws_app.sock and k._ws_app.sock.connected)
                row['server_alive'] = server._subprocess.poll() is None
                row['trace_before_secondary_checks'] = trial_trace(work, index)
                if row['ready']:
                    answer = k.execute("print('KERNEL_WIRE_DIAGNOSTIC_MARKER')", timeout_seconds=10)
                    row['marker_ok'] = bool(answer.is_ok and not answer.timed_out and
                        any('KERNEL_WIRE_DIAGNOSTIC_MARKER' in s for s in answer.output))
                else:
                    # New diagnosis only, not an original task retry or success relabel.
                    row['control_channel_check'] = control_check(k)
                    connection = server.connection_info
                    url = f'ws://{connection.host}:{connection.port}/api/kernels/{kid}/channels?session_id=diagnostic-reconnect'
                    with Kernel(url, client._get_headers()) as other:
                        other._session_id = 'diagnostic-reconnect'
                        row['fresh_connection_ready'] = other.wait_for_ready(timeout_seconds=15)
            finally:
                k.stop()
                client.delete_kernel(kid)
        except Exception as exc:
            row['error_type'] = type(exc).__name__
        finally:
            if server is not None:
                server.stop()
        row['trace_complete'] = trial_trace(work, index)
        rows.append(row)
        write(root/f'row-{index:02d}.json', row)
        print(json.dumps(dict(completed=len(rows), ready=row['ready'], marker_ok=row['marker_ok'],
                             error_type=row.get('error_type'))), flush=True)
        if not trace_is_observable(row['trace_complete'], row['ready']):
            stop = 'instrumentation_not_observing_actual_channel'
            break
        if not row['ready'] or not row['marker_ok']:
            stop = 'first_failure_preserved_and_diagnosed'
            break
    result = dict(job=launch['job'], commit=commit, source_tree=artifact['source_tree'], rows=rows,
        stop_reason=stop, seconds=time.monotonic()-start, utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        api_calls=0, models=0, task_dataset_reads=0, historical_candidate_reruns=0,
        limitation='Targeted fresh-gateway reproduction with passive server hooks and fixed markers; not a model/e2e result or unbiased failure-rate comparison. Secondary checks never relabel the first failure.')
    write(root/'result.json', result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--commit')
    p.add_argument('--check-import', action='store_true')
    a = p.parse_args()
    root = a.root.resolve(strict=True)
    if root.parent != BASE or not re.fullmatch(r'forets-kernel-wire-20260912-[A-Za-z0-9_]+', root.name):
        raise ValueError('root outside explicit diagnostic namespace')
    if a.check_import:
        setup(root)
        print('IMPORT_OK_NO_KERNEL_NO_MODEL')
    else:
        run(root, a.commit)
