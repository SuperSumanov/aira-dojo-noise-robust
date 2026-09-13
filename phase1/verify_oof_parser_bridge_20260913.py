"""Actual MCTS parser plus real measured arrays, fixed analyze stub; no API/GPU."""
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from forets_environment_build_20260912 import read,write,encode,sha
from oof_accuracy_contract_20260913 import OOFAccuracy

BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'forets-wallclock-20260912-5_czzimk'
ROOT=BASE/'forets-pool-completion-20260912-dcrffcf9'


def main():
    measured=read(ROOT/'cv-alignment-summary.json','60b903f151eda292a251b6579c570086292c8e4662b9a47a01f4f3086a688da7')
    path=ROOT/'work-0/cv_alignment_private.npz'
    if sha(path.read_bytes())!=measured['private_array_sha256']:raise ValueError('real prediction evidence')
    import numpy as np
    with np.load(path,allow_pickle=False) as a:
        accumulator=OOFAccuracy(a['y'].tolist());order=a['order'].tolist();pred=a['concatenated'].tolist()
        for start in range(0,len(order),1000):accumulator.add(order[start:start+1000],pred[start:start+1000])
    if accumulator.score()!=measured['metrics']['aligned_accuracy']:raise ValueError('independent contract score')
    marker=accumulator.marker()
    artifact=read(PARENT/'artifact.json');relative='src/dojo/solvers/mcts/mcts.py'
    if sha((PARENT/'source'/relative).read_bytes())!=artifact['source_files'][relative]:raise ValueError('production parser changed')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(Path(__file__).parent),
        MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(PARENT/'source/src'),str(PARENT/'code')];logging.disable(logging.CRITICAL)
    from dojo.solvers.mcts.mcts import MCTS,MCTSNode
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,AUX_EVAL_INFO,VALID_SOLUTION
    solver=MCTS.__new__(MCTS);solver.cfg=NS(use_test_score=False);solver.lower_is_better=False
    solver.logger=NS(debug=lambda *a:None,error=lambda *a:None,warning=lambda *a:None,info=lambda *a:None)
    solver._analyze=lambda n:dict(metric=None,summary='Fixed missing-analysis test input; not another LLM call.',is_bug=True)
    actual=read(ROOT/'result-0.json');output=(ROOT/'program-0.txt').read_bytes()
    if sha(output)!=actual['output_sha256']:raise ValueError('actual stdout drift')
    parsed=[]
    for extra in ('', '\n'+marker+'\n'):
        execution=ExecutionResult.get_empty();execution.exit_code=0;execution.exec_time=actual['execution_seconds']
        execution.term_out=[output.decode()+extra]
        node=MCTSNode(code='actual diagnostic program identity '+measured['code_sha256'])
        # Only validity, no external score, is supplied to this parser test.
        solver.parse_eval_result(node,{EXECUTION_OUTPUT:execution,AUX_EVAL_INFO:{},VALID_SOLUTION:True})
        parsed.append(dict(is_buggy=node.is_buggy,metric=node.metric.value,maximize=node.metric.maximize))
    # Direct source inspection confirmed this version has NO deterministic
    # stdout-marker fallback. Preserve that negative integration result.
    if any(not v['is_buggy'] or v['metric'] is not None for v in parsed):
        raise ValueError('observed parser contract changed '+json.dumps(parsed))
    out=dict(role='real_parser_negative_marker_integration_not_autonomous_repair_or_e2e',source_tree=artifact['source_tree'],
        actual_prediction_rows=len(order),before=parsed[0],after=parsed[1],api_calls=0,gpu_jobs=0,
        oof_contract_matches_independent_measurement=True,marker_alone_restores_node=False,
        initial_expectation_rejected='Two preliminary attempts expected a nonexistent stdout fallback; both rejected. No live source changed.',
        external_score_supplied_to_parser=False,changed_live_source=False,
        measurement_sha256=sha((ROOT/'cv-alignment-summary.json').read_bytes()),
        contract_sha256=sha(Path(__file__).with_name('oof_accuracy_contract_20260913.py').read_bytes()),
        script_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(sha256=write(ROOT/'oof-parser-bridge.json',encode(out)),**out)))


if __name__=='__main__':main()
