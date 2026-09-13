"""In-session CPU check of execute-two in the unchanged production batch path."""
import copy
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read, write, encode, sha
from forets_branching_control_20260913 import execute_two

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-2o9mw39n')


def run():
    stage = Path(__file__).resolve().parent
    build = read(ROOT/'build.json')
    artifact = read(ROOT/'artifact.json')
    for name, digest in artifact['source_files'].items():
        if sha((ROOT/'source'/name).read_bytes()) != digest: raise ValueError('source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', LOGGING_DIR=str(stage),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path[:0] = [str(ROOT/'source/src'), str(ROOT/'code')]
    logging.disable(logging.CRITICAL)
    from dojo.solvers.fore_ts.batch_runtime import expand_batch
    from dojo.core.solvers.utils.response import extract_code
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    from dojo.core.interpreters.base import ExecutionResult
    records = []
    with tempfile.TemporaryDirectory(prefix='execute-two-cpu-', dir=stage) as temp:
        temp = Path(temp)
        for arm in ('uniform_random', 'critic_topk_random'):
            planned = next(r for r in read(ROOT/'prepared.json')['run_configs'] if r['arm']==arm)
            original = read(ROOT/'configs'/(planned['run_id']+'.json'))
            cfg = copy.deepcopy(original)['solver']
            assert cfg['num_children_to_choose']==2
            cfg['checkpoint_path'] = str(temp/arm)
            root = MCTSNode(code='', parents=[])
            journal = Journal(); journal.append(root)
            solver = NS(cfg=NS(**cfg), state=NS(current_step=1, running_time=0.),
                task_name='leaf-classification', task_desc='fixture', data_preview='fixture',
                journal=journal, journal_for_unselected=Journal(), global_min_q_val=0., global_max_q_val=1.,
                critic_top_k=2, num_children_to_choose=2, remaining_steps=63)
            counts = dict(generation=0, ranking=0, execution=0)
            async def generate(*args):
                counts['generation'] += 1
                return MCTSNode(code='print('+str(counts['generation'])+')', parents=[], operators_metrics=[])
            async def rank(*args): counts['ranking'] += 1; return [1., 2., 3., 4.]
            def parse(node, eval_result):
                node.is_buggy=False; node.metric=NS(value=.5, info={}, maximize=True)
            def step(state, code):
                counts['execution'] += 1
                result=ExecutionResult.get_empty(); result.exit_code=0; result.timed_out=False; result.exec_time=.01
                return state, {EXECUTION_OUTPUT:result}
            solver._draft=solver._improve=generate; solver.parse_eval_result=parse
            solver.log_journal=lambda:None; solver._backprop_step=lambda *a,**kw:None
            solver.set_global_q_values=lambda v:None
            state={'solver_interpreter':NS(timeout=300)}
            with patch('dojo.solvers.fore_ts.batch_runtime.rank_pool', side_effect=rank):
                expand_batch(solver, [root], state, NS(step_task=step), MCTSNode, extract_code, cfg)
                assert counts==dict(generation=0, ranking=0, execution=1)
                baseline=journal.nodes[-1]
                expand_batch(solver, [root,baseline], state, NS(step_task=step), MCTSNode, extract_code, cfg)
            assert counts==dict(generation=4, ranking=int(arm=='critic_topk_random'), execution=3)
            assert len(baseline.children)==2 and all(n.parents==[baseline] for n in baseline.children)
            path=Path(cfg['checkpoint_path'])/'forets-candidates-private/batch-2.sqlite'
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
                value=json.loads(db.execute('select payload from snapshot').fetchone()[0])
            assert value['phase']=='complete' and len(value['selected'])==2 and len(value['task_calls'])==2
            # Independent replay runs on actual production ledger payloads.
            from verify_branching_selection_20260913 import verify_pool
            inp = dict(codes_sha256=[sha(c['node']['code'].encode()) for c in value['candidates']],
                aggregation='single_order_rank_v1') if arm=='critic_topk_random' else None
            done = dict(borda=[1.,2.,3.,4.]) if arm=='critic_topk_random' else None
            verify_pool(value,cfg,dict(task=solver.task_name,arm=arm,seed=cfg['selector_seed']),inp,done)
            if arm=='critic_topk_random': assert set(value['selected'])=={2,3}
            assert len(journal.nodes)==4 and len(solver.journal_for_unselected.nodes)==2
            records.append(dict(arm=arm, counts=counts, first_executions=1, later_executions=2,
                actual_siblings=len(baseline.children), selected_slots=value['selected'], unexecuted_export_only=2))
    result=dict(status='CPU_ACTUAL_BATCH_BRANCHING_NOT_EFFICACY', source_tree=build['source_tree'],
        rows=records, api_calls=0, gpu_dispatches=0, deployed=False,
        inspector_sha256=sha(Path(__file__).read_bytes()))
    digest=write(stage/'branching-reference-integration.json', encode(result))
    print(json.dumps(dict(result=result, sha256=digest)))


if __name__=='__main__':
    ROOT=Path(sys.argv[1]).resolve(strict=True)
    run()
