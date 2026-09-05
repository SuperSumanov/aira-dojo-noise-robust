import io
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_historical_runtime_prefix import prefix,log_member,read_scope_statement

def test_unknown_line_is_read_but_not_exported():
    stream=io.BytesIO(b'Final fitness: 0.9\nsecond line must not be read\n')
    x=prefix(stream)
    assert x['status']=='UNRECOGNIZED_PREFIX_STOP' and x['paths']=={}
    assert stream.tell()==len(b'Final fitness: 0.9\n')
    scope=read_scope_statement()
    assert scope['task_phase_byte_read_count']=='unknown_for_first_unrecognized_line'
    assert 'task_phase_log_reads' not in scope

def clean():
    return b'Current working directory: /snapshot\n`dojo` package source path: /snapshot/src/dojo/__init__.py\n`aira_core` package source path: /site/aira_core/__init__.py\n`mlebench` package source path: /snapshot/src/dojo/tasks/mlebench/mle-bench/mlebench/__init__.py\n'

class BoundaryStream(io.BytesIO):
    def readline(self,*args):
        if self.tell()==len(self.getvalue()):raise AssertionError('READ_AFTER_BOUNDARY')
        return super().readline(*args)

def test_stops_at_boundary():
    x=prefix(BoundaryStream(clean()+b'Instantiating the task...\n'))
    assert x['status']=='COMPLETE_PRETASK_SOURCE_RECORD' and len(x['paths'])==4

def test_timestamp_loguru_prefix():
    data=b''.join(b'2026-08-01 00:00:00.000 | INFO | dojo.main_run:_main:100 - '+x+b'\n' for x in (clean()+b'Instantiating the task...\n').splitlines())
    assert prefix(BoundaryStream(data))['status']=='COMPLETE_PRETASK_SOURCE_RECORD'

@pytest.mark.parametrize('text,status',[(b'Final fitness: 0.9\n','UNRECOGNIZED_PREFIX_STOP'),(b'Traceback\n','UNRECOGNIZED_PREFIX_STOP'),(b'Current working directory: relative\n','INVALID_SOURCE_PATH'),(b'Current working directory: /a/../b\n','INVALID_SOURCE_PATH'),(b'X'*9000+b'\n','PREFIX_CAP')])
def test_rejects_without_read_ahead(text,status):
    assert prefix(BoundaryStream(text))['status']==status

def test_credentials_stop_without_echo():
    x=prefix(BoundaryStream(b'Current working directory: /'+b'sk-'+b'X'*20+b'\n'))
    assert x['status']=='CREDENTIAL_SHAPE_STOP' and x['paths']=={}

def test_duplicate_field():
    assert prefix(BoundaryStream(clean()+b'Current working directory: /same\n'))['status']=='DUPLICATE_SOURCE_FIELD'

def test_incomplete_and_eof():
    assert prefix(BoundaryStream(b'Instantiating the task...\n'))['status']=='BOUNDARY_WITH_INCOMPLETE_RECORD'
    assert prefix(io.BytesIO(clean()))['status']=='EOF_BEFORE_BOUNDARY'

def test_channel_paths_are_explicit_pool_logs():
    assert log_member('/root/batch/srun_pool/abc/logs/a.out','/root/batch/srun_pool/abc')=='batch/srun_pool/abc/logs/a.out'
    with pytest.raises(Exception):log_member('/root/batch/x/a.out','/root/batch/srun_pool/abc')
    with pytest.raises(Exception):log_member('/root/batch/srun_pool/abc/logs/../other','/root/batch/srun_pool/abc')
