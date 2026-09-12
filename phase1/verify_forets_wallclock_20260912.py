"""Actual imported task/MCTS/archive hooks, with synthetic task/LLM boundaries.

CPU-only integration, plus a real POSIX subprocess deadline. No models, paid
API, dataset labels, scheduler dispatch, or claims of GPU/cgroup acceptance.
"""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


def run(root, blocks=(1,)):
    root=Path(root).resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('explicit new development root required')
    result_path=root/'integration-check.json'
    if result_path.exists(): raise ValueError('integration receipt already exists')
    info=json.loads((root/'artifact.json').read_bytes())
    for name,digest in info['source_files'].items():
        path=root/'source'/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('source hash')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    logging.disable(logging.CRITICAL)
    import dojo.solvers.fore_ts.wallclock as wc
    import dojo.solvers.mcts.mcts as mcts
    import dojo.tasks.mlebench.task as task_module
    from dojo.tasks.mlebench.submission_archive import archive_submission
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.core.tasks.constants import AUX_EVAL_INFO
    from dojo.core.runners.slurm.bounded_process import run_bounded
    from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
    from forets_block_controller_20260911 import inspect_draft
    from forets_native_run_20260911 import static_ready
    configs=[]
    for block in blocks:
        spec,part=inspect_draft(root,block);SrunPoolConfig(**spec.launcher).validate()
        static_ready(root/'code',block);configs.extend(part)
    if len(configs)!=8 or spec.launcher['worker_wall_seconds']!=600: raise ValueError('wrong experiment matrix')
    for cfg in configs:
        if cfg['solver']['step_limit']!=64 or cfg['solver']['time_limit_secs']!=600: raise ValueError('wrong cutoff configuration')
    with tempfile.TemporaryDirectory(prefix='forets-cutoff-test-',dir=root) as temp:
        tmp=Path(temp);(tmp/'results').mkdir();(tmp/'results/submission-escrow').mkdir()
        started=time.monotonic_ns()
        env=dict(FORETS_SEARCH_START_NS=str(started),FORETS_SEARCH_SECONDS='600',FORETS_INCUMBENT_DIR=str(tmp/'incumbents'))
        code='print( 1 )';csv_path=tmp/'submission.csv';executed=[]
        class Interpreter:
            factory=False
            def run(self, source, file_name):
                executed.append(source);csv_path.write_bytes(b'id,value\n1,2\n')
                output=ExecutionResult.get_empty();output.exit_code=0;output.timed_out=False;output.exec_time=1.
                return output
            def fetch_file(self, path): return None
        def synthetic_grade(**kwargs):
            report={'score':.5,'valid_submission':True}
            archive_submission(csv_path,csv_path.read_bytes(),report,tmp/'results/submission-escrow')
            return .5,report
        task=task_module.MLEBenchTask.__new__(task_module.MLEBenchTask)
        task.cfg=SimpleNamespace(cache_dir=str(tmp),name='synthetic',results_output_dir=str(tmp/'results'))
        task.logger=logging.getLogger('cutoff-test');task.competition=object();task._submission_file_path=csv_path
        with (patch.dict(os.environ,env),patch.object(task_module,'validate_submission',return_value=(True,'fixture')),
              patch.object(task_module.evaluate,'evaluate_submission',side_effect=synthetic_grade)):
            _,evaluation=task.step_task({'solver_interpreter':Interpreter()},code)
            assert len(executed)==1 and '_forets_submission_archive' not in evaluation[AUX_EVAL_INFO]
            association=evaluation['_forets_submission_archive']
            assert association['code_sha256']==wc.sha(code.encode())
            assert association['executed_code_sha256']==wc.sha(executed[0].encode())
            node=SimpleNamespace(id='fixture-node',code=code,exit_code=0,_term_out=[],absorb_exec_result=lambda output:None)
            solver=mcts.MCTS.__new__(mcts.MCTS)
            solver.logger=logging.getLogger('cutoff-test');solver.lower_is_better=True
            solver.cfg=SimpleNamespace(step_limit=2,time_limit_secs=600,use_test_score=False)
            solver._analyze=lambda n:dict(metric=.7,summary='fixture',is_bug=False)
            solver.parse_eval_result(node,evaluation)  # Actual production parsing hook.
            assert not node.is_buggy and '_forets_submission_archive' not in node.metric.info
            solver.state=SimpleNamespace(current_step=0,running_time=0.)
            solver.journal=SimpleNamespace(get_best_node=lambda:node)
            solver.create_root_node=lambda:None;solver.save_checkpoint=lambda:None
            def step(task,state):
                solver.state.current_step+=1
                if solver.state.current_step==2: raise wc.SearchBudgetExpired('fixture partial iteration')
                return state
            solver.step=step
            try:
                solver(task,{})  # Actual __call__: completed iteration then interrupted iteration.
            except wc.SearchBudgetExpired:
                pass
            else:
                raise AssertionError('budget boundary did not propagate')
            selected=wc.read_incumbent(tmp/'incumbents',expected_start_ns=started,expected_seconds=600)
            assert selected['current_step']==1 and selected['submission']==association
            assert not (tmp/'incumbents/step-000002.json').exists()
            # Before reserving money/connecting to a ledger, timeout must escape
            # the actual paid-budget entry point, not merely a mocked caller.
            from dojo.core.solvers.llm_helpers.backends.paid_budget import reserve
            with patch.dict(os.environ,{'FORETS_SEARCH_START_NS':str(time.monotonic_ns()-500*10**9)}):
                try: reserve(tmp/'ledger-does-not-exist','fixture','fixture')
                except wc.SearchBudgetExpired: pass
                else: raise AssertionError('late API admitted')
        child_env=dict(os.environ,FORETS_SEARCH_SECONDS='.1',FORETS_INCUMBENT_DIR=str(tmp/'unused'))
        bounded=run_bounded([sys.executable,'-c','import time; time.sleep(2)'],cwd=tmp,
            output_dir=tmp/'bounded',wall_seconds=.1,grace_seconds=.1,environment=child_env)
        assert bounded['status']=='timed_out' and bounded['search_seconds']==.1
        assert bounded['containment']=='posix_process_group_only' and bounded['search_start_ns']>0
    report=dict(status='PASSED_CPU_INTEGRATION_NOT_GPU_ACCEPTANCE',source_tree=info['source_tree'],
        imported_task_archive_mcts=True,formatted_execution_bound=True,interrupted_iteration_excluded=True,
        no_archive_in_agent_feedback=True,actual_paid_reserve_rejects_late_call=True,
        actual_posix_timeout=True,slurm_cgroup_verified=False,actual_typed_configs=8,
        api_requests=0,gpu_dispatches=0,models_loaded=0)
    with result_path.open('x') as stream:json.dump(report,stream,sort_keys=True,indent=2)
    print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();run(args.root)
