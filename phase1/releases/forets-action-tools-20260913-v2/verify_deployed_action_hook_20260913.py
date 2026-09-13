"""Actual ForeTS log / MCTS parse and debug hooks, fake programs, no API/GPU."""
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_action_delivery_20260913 import patch_sources,PROTOCOL
from read_forets_action_delivery_20260913 import read_latest
from forets_environment_build_20260912 import read,sha,write,encode

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')

def run():
    artifact=read(ROOT/'artifact.json')
    if artifact['base_tree']!='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798':raise ValueError('exact source parent')
    for n,h in artifact['source_files'].items():
        if sha((ROOT/'source'/n).read_bytes())!=h:raise ValueError('source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(Path(__file__).parent),MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(ROOT/'source/src'),str(ROOT/'code')];logging.disable(logging.CRITICAL)
    import dojo.solvers.fore_ts.fore_ts as production
    from dojo.solvers.fore_ts import wallclock
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.core.solvers.utils.response import extract_code
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,AUX_EVAL_INFO
    paths=('src/dojo/config_dataclasses/solver/fore_ts.py','src/dojo/solvers/fore_ts/fore_ts.py')
    modified=[(ROOT/'source'/p).read_text() for p in paths]
    ns=dict(production.__dict__)
    with tempfile.TemporaryDirectory(prefix='action-hook-cpu-',dir=Path(__file__).parent) as temp:
        base=Path(temp);start=time.monotonic_ns();logs=[];analysis=[]
        env=dict(FORETS_SEARCH_START_NS=str(start),FORETS_SEARCH_SECONDS='600',FORETS_INCUMBENT_DIR=str(base/'incumbents'))
        with patch.dict(os.environ,env):
            solver=ns['ForeTS'].__new__(ns['ForeTS'])
            solver.cfg=NS(action_delivery_protocol=PROTOCOL,use_test_score=False,max_debug_depth=1,max_debug_time=300,step_limit=64)
            solver.state=NS(current_step=0);solver.journal=Journal();solver.lower_is_better=True
            solver.logger=NS(log=lambda *a,**k:logs.append(k),debug=lambda *a:None,info=lambda *a:None,
                warning=lambda *a:None,error=lambda *a:None)
            def analyze(n):
                analysis.append(n.code)
                return dict(metric=.3 if n.code.strip()=='print(3)' else .5,summary='',is_bug=n.code.strip()=='raise RuntimeError()')
            solver._analyze=analyze
            solver.create_root_node()
            assert not (base/'incumbents').exists()
            def evaluation(code,exitcode=0):
                r=ExecutionResult.get_empty();r.exit_code=exitcode;r.exec_time=.01;r.timed_out=False
                return {EXECUTION_OUTPUT:r,AUX_EVAL_INFO:{'private_grade_marker':'DO_NOT_EXPORT'},
                    '_forets_submission_archive':dict(code_sha256=sha(code.encode()),submission_sha256='a'*64,
                        report_sha256='b'*64,archive_dir=str(base/'fake-archive'))}
            first=MCTSNode(code=extract_code('print(1)'),parents=[solver.root_node])
            solver.parse_eval_result(first,evaluation(first.code));solver.journal.append(first)
            solver.log_journal();solver.state.current_step+=1
            assert read_latest(base/'incumbents',start_ns=start,seconds=600)['node_id']==first.id
            buggy=MCTSNode(code=extract_code('raise RuntimeError()'),parents=[first])
            solver.parse_eval_result(buggy,evaluation(buggy.code,1));solver.journal.append(buggy)
            solver.log_journal();solver.state.current_step+=1
            assert read_latest(base/'incumbents',start_ns=start,seconds=600)['node_id']==first.id
            solver._debug=lambda parent:MCTSNode(code=extract_code('print(3)'),parents=[parent])
            task=NS(step_task=lambda state,code:(state,evaluation(code)))
            _,debug_path,_=solver.debug_cycle({},task,buggy)
            final=read_latest(base/'incumbents',start_ns=start,seconds=600)
            assert final['node_id']==debug_path[-1].id and final['action']==3
            assert len(logs)==4 and len(analysis)==3
            assert not list((base/'incumbents').glob('step-*'))
            assert 'DO_NOT_EXPORT' not in ''.join(p.read_text() for p in (base/'incumbents/action-incumbents').glob('*.json'))
    result=dict(role='deployed_source_hooks_with_fake_execution_not_efficacy',source_tree=artifact['source_tree'],
        parsed_actions=3,original_log_calls=4,original_primary_receipts_written=0,api_calls=0,gpu_jobs=0,
        independent_reader_matches=True,debug_hook_exercised=True,hidden_marker_exported=False,
        files={n:sha(Path(__file__).with_name(n).read_bytes()) for n in
            ('forets_action_delivery_20260913.py','read_forets_action_delivery_20260913.py',Path(__file__).name)})
    out=ROOT/'action-integration.json'
    print(json.dumps(dict(result=result,sha256=write(out,encode(result)))))
if __name__=='__main__':run()
