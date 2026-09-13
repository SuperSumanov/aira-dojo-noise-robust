"""Opt-in fresh-container IPython-cell interpreter; not deployed in live searches.

Keeps the pinned image, configured binds/environment and cell semantics, while
removing Jupyter HTTP/WebSocket transport. This changes execution overhead and
must be shared by all arms in a new protocol, never patched into a running study.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

from dojo.core.interpreters.base import ExecutionResult, Interpreter


class ProcessInfrastructureError(RuntimeError):pass


def safe_file(work,path,*,relative=False):
    p=Path(path)
    if relative and (p.is_absolute() or '..' in p.parts or not p.parts):raise ValueError('relative workspace file required')
    resolved=(work/p if not p.is_absolute() else p).resolve()
    if resolved==work or not resolved.is_relative_to(work):raise ValueError('path outside workspace')
    return resolved


def positive(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('positive finite timeout')
    return float(v)


def cell_command(filename):
    # run_cell, not exec/runpy: preserve the existing IPython input/magic language.
    # The trusted launcher is outside model text, which is read as data from file.
    return ('import sys; from pathlib import Path; from IPython.core.interactiveshell import InteractiveShell; '
            's=InteractiveShell.instance(); s.colors="NoColor"; '
            'r=s.run_cell(Path('+repr(filename)+').read_text(),store_history=False); '
            'sys.exit(0 if r.success else 1)')


def terminate_group(process,grace=2.):
    """Reclaim only the new group created by this caller, including descendants."""
    if process.pid<=1:raise ValueError('invalid owned group')
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=grace)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:process.wait(timeout=grace)
    except subprocess.TimeoutExpired:raise ProcessInfrastructureError('process cleanup unconfirmed')


class FreshContainerInterpreter(Interpreter):
    local=False
    factory=True

    def __init__(self,cfg,data_dir=None):
        from dojo.core.interpreters.jupyter.singularity_jupyter_server import _resolve_superimage_path,_normalise_read_only_binds
        if cfg.container_runtime!='singularity':raise ValueError('only explicitly verified singularity backend')
        self.timeout=positive(cfg.timeout);self.strip_ansi=cfg.strip_ansi
        self.working_dir=Path(cfg.working_dir).resolve();self.working_dir.mkdir(parents=True,exist_ok=True)
        self.data_dir=Path(data_dir).resolve(strict=True) if data_dir is not None else self.working_dir/'data'
        if data_dir is None:self.data_dir.mkdir(exist_ok=True)
        self.image=_resolve_superimage_path(cfg.superimage_directory,cfg.superimage_version)
        self.overlays=[Path(p).expanduser().resolve(strict=True) for p in (cfg.read_only_overlays or [])]
        self.binds=_normalise_read_only_binds(cfg.read_only_binds or {})
        self.env=dict(cfg.env or {});self.process=None
        for n in ('.home','.local'):(self.working_dir/n).mkdir(exist_ok=True)
        self.records=[]

    def cleanup_line(self,line):
        return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])','',line) if self.strip_ansi else line

    def fetch_file(self,path):
        p=safe_file(self.working_dir,path)
        return p.as_posix() if p.is_file() else None

    def run(self,code,reset_session=True,persist_file=False,file_name='runfile.py',execute_code=True,include_exec_time=True):
        from dojo.core.interpreters.jupyter.singularity_jupyter_server import _build_singularity_command,_build_container_environment,_build_runtime_environment,_publish_container_identity
        import humanize
        if not reset_session:raise ValueError('stateful sessions are not supported by the fresh-container protocol')
        if self.process is not None:raise ProcessInfrastructureError('overlapping run on same interpreter')
        if not isinstance(code,str):raise TypeError('code must be text')
        destination=safe_file(self.working_dir,file_name,relative=True)
        if not destination.parent.is_dir():raise ValueError('parent directory missing')
        started=time.monotonic();destination.write_text(code,encoding='utf-8')
        if not execute_code:
            return ExecutionResult(term_out=[],exec_time=time.monotonic()-started,exit_code=0,timed_out=False)
        args=_build_singularity_command(runtime_executable='singularity',image_path=self.image,
            working_dir=self.working_dir,bind_inputs_dir=self.data_dir,read_only_overlays=self.overlays,
            read_only_binds=self.binds,container_env=_build_container_environment(self.env),token='unused-no-server')
        start_payload=args.index('python',args.index(str(self.image))+1)
        if args[start_payload+1]!='-c':raise ValueError('original container argument shape')
        relative_name=destination.relative_to(self.working_dir).as_posix()
        args=args[:start_payload]+['python','-c',cell_command(relative_name)]
        logpath=self.working_dir.parent/('.process-output-'+uuid.uuid4().hex+'.private.log')
        identity=Path(os.environ['DOJO_WORKER_IDENTITY_PATH'])
        binding=identity.with_suffix('.native-binding.json')
        before_binding=hashlib.sha256(binding.read_bytes()).hexdigest() if binding.exists() else None
        timed=False;process=None;returncode=None
        try:
            with logpath.open('xb') as log:
                process=subprocess.Popen(args,stdout=log,stderr=log,stdin=subprocess.DEVNULL,
                    start_new_session=True,shell=False,env=_build_runtime_environment(os.environ))
                self.process=process
                _publish_container_identity(process.pid)
                try:returncode=process.wait(timeout=max(.001,self.timeout-(time.monotonic()-started)))
                except subprocess.TimeoutExpired:timed=True
                finally:terminate_group(process)
            if returncode is None:returncode=process.returncode
            raw=logpath.read_bytes()
            after_binding=hashlib.sha256(binding.read_bytes()).hexdigest() if binding.exists() else None
            if after_binding is None or before_binding==after_binding:
                raise ProcessInfrastructureError('native binding or launcher failed; no quality label')
            lines=raw.decode('utf-8',errors='replace').splitlines(keepends=True)
            elapsed=time.monotonic()-started
            if timed:lines.append(f'TimeoutError: Execution exceeded the time limit of {humanize.naturaldelta(self.timeout)}')
            elif include_exec_time:lines.append(f'Execution time: {humanize.naturaldelta(elapsed)} (time limit is {humanize.naturaldelta(self.timeout)}).')
            self.records.append(dict(code_sha256=hashlib.sha256(code.encode()).hexdigest(),exit_code=returncode,
                timed_out=timed,exec_time=elapsed,backend='fresh_container_ipython',output_sha256=hashlib.sha256(raw).hexdigest()))
            return ExecutionResult(term_out=[self.cleanup_line(s) for s in lines],exec_time=elapsed,
                exit_code=1 if timed else returncode,timed_out=timed,eval_return=None)
        finally:
            if process is not None and process.poll() is None:terminate_group(process)
            self.process=None
            _publish_container_identity(None)
            if not persist_file:destination.unlink(missing_ok=True)

    def cleanup_session(self):
        if self.process is not None:terminate_group(self.process);self.process=None

    def close(self):self.cleanup_session()
