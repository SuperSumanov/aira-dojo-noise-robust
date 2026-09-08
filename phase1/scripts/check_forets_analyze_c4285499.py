"""Targeted CPU regression of the actual analyzer path, with an artificial LLM.

No model, API, task execution, data access or full-suite rerun. The old source is
retained beside the new isolated integration. This is not an e2e outcome test.
"""
import ast
import asyncio
import hashlib
import inspect
import json
import os
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

BASE = Path('/research/d7/spc/yzyang4/forets-e2e-dev-20260908-IMuJx6')
ROOT = BASE / 'upstream-c4285499'
assert ROOT.is_dir(), 'deployment is separate; this diagnostic never extracts or modifies source'
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'src'))
os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
    LOGGING_DIR=str(ROOT / 'logs'), DEFAULT_SLURM_PARTITION='gpu_24h',
    DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
    MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
    SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage')

if '--solver-first' in sys.argv:
    from dojo.solvers.fore_ts import ForeTS as PublicForeTS
from dojo.core.solvers.operators.analyze import analyze_op
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.solvers.mcts.mcts import MCTS
from dojo.solvers.fore_ts.fore_ts import ForeTS
from dojo.solvers.fore_ts import ForeTS as PublicForeTS

assert PublicForeTS is ForeTS
assert ForeTS._analyze is MCTS._analyze
assert inspect.iscoroutinefunction(GenericLLM.__call__)
source = BASE / 'src/dojo/solvers/mcts/mcts.py'
tree = ast.parse(source.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MCTS')
old_method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_analyze')
old_method.returns = None
for arg in old_method.args.args:
    arg.annotation = None
namespace = {}
exec(compile(ast.Module(body=[old_method], type_ignores=[]), str(source), 'exec'), namespace)

class ArtificialLLM:
    def __init__(self, fail=False):
        self.fail, self.completed, self.coroutines = fail, 0, []

    def __call__(self, **kwargs):
        assert kwargs['function_name'] == 'submit_review'

        async def reply():
            await asyncio.sleep(0)  # Enforce a real await, not an immediate tuple.
            if self.fail:
                raise RuntimeError('artificial analyzer failure')
            self.completed += 1
            return 'artificial analysis', {'artificial': True}

        coroutine = reply()
        self.coroutines.append(coroutine)
        return coroutine

def fixture(llm):
    node = SimpleNamespace(code='print("artificial")', term_out='artificial output',
                           operators_used=[], operators_metrics=[])
    solver = SimpleNamespace(task_desc='artificial task',
        analyze_fn=partial(analyze_op, llm, SimpleNamespace()),
        logger=SimpleNamespace(info=lambda *args: None))
    return solver, node

old_llm = ArtificialLLM()
solver, node = fixture(old_llm)
try:
    namespace['_analyze'](solver, node)
except TypeError as error:
    assert 'coroutine' in str(error)
    old_failure = type(error).__name__
else:
    raise AssertionError('old failure not reproduced')
finally:
    for coroutine in old_llm.coroutines:
        coroutine.close()
assert old_llm.completed == 0 and not node.operators_used

good_llm = ArtificialLLM()
solver, node = fixture(good_llm)
assert ForeTS._analyze(solver, node) == 'artificial analysis'
assert good_llm.completed == 1 and node.operators_used == ['analysis']
assert node.operators_metrics == [{'artificial': True}]

bad_llm = ArtificialLLM(fail=True)
solver, node = fixture(bad_llm)
try:
    ForeTS._analyze(solver, node)
except RuntimeError as error:
    assert str(error) == 'artificial analyzer failure'
else:
    raise AssertionError('failure swallowed')
assert not node.operators_used and not node.operators_metrics

print(json.dumps(dict(upstream='c428549973beb4a3289bf669675fac13f64e63b8',
    import_order='solver_first' if '--solver-first' in sys.argv else 'analyzer_first',
    mcts_sha256=hashlib.sha256((ROOT/'src/dojo/solvers/mcts/mcts.py').read_bytes()).hexdigest(),
    package_init_sha256=hashlib.sha256((ROOT/'src/dojo/solvers/fore_ts/__init__.py').read_bytes()).hexdigest(),
    source_root=str(ROOT), old_failure=old_failure, fixed_async_path_pass=True,
    analyzer_exception_propagated=True, actual_analyze_op_used=True,
    actual_generic_llm_is_async=True, model_or_api_called=False,
    task_or_data_access=False), sort_keys=True))
