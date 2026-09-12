"""CPU-only structural verification using the closed experiment's actual classes."""
import json
import logging
import os
from pathlib import Path
import sys
from forets_environment_build_20260912 import read, write, encode, sha

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')


def run():
    build = read(ROOT/'build.json')
    artifact = read(ROOT/'artifact.json')
    for name, digest in artifact['source_files'].items():
        if sha((ROOT/'source'/name).read_bytes()) != digest:
            raise ValueError('source mutation')
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', LOGGING_DIR=str(ROOT),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path[:0] = [str(ROOT/'source/src'), str(ROOT/'code')]
    logging.disable(logging.CRITICAL)
    from types import SimpleNamespace as NS
    from dojo.solvers.fore_ts.fore_ts import ForeTS
    from dojo.solvers.mcts.mcts import MCTS, MCTSNode
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.solvers.utils.metric import MetricValue, WorstMetricValue
    from forets_incumbent_parent_reference_20260913 import incumbent_path
    assert ForeTS.search_policy is MCTS.search_policy
    root = MCTSNode(code='', parents=[], metric=WorstMetricValue(), is_buggy=True)
    good = MCTSNode(code='fixture good', parents=[root], metric=MetricValue(.8, maximize=True), is_buggy=False)
    bad = MCTSNode(code='fixture bad', parents=[good], metric=WorstMetricValue(), is_buggy=True)
    journal = Journal()
    for node in (root, good, bad): journal.append(node)
    solver = ForeTS.__new__(ForeTS)
    solver.journal = journal
    solver.lower_is_better = False
    solver.global_min_q_val = 0.
    solver.global_max_q_val = 1.
    trials = []
    for uct_c in (0., 1., 100.):
        solver.cfg = NS(uct_c=uct_c)
        path = solver.search_policy(root)
        alternative = incumbent_path(root, journal)
        assert path == [root, good, bad]
        assert alternative == [root, good]
        trials.append(dict(uct_c=uct_c, actual_leaf_step=path[-1].step,
            reference_parent_step=alternative[-1].step))
    result = dict(status='CPU_STRUCTURE_ONLY_NOT_EFFICACY', source_tree=build['source_tree'],
        actual_forets_inherits_mcts=True, trials=trials, gpu_dispatches=0, api_calls=0,
        deployed=False, inspector_sha256=sha(Path(__file__).read_bytes()),
        reference_sha256=sha(Path(__file__).with_name('forets_incumbent_parent_reference_20260913.py').read_bytes()))
    digest = write(ROOT/'parent-reference-integration.json', encode(result))
    print(json.dumps(dict(result=result, sha256=digest)))


if __name__ == '__main__': run()
