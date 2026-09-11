"""CPU regression of actual MCTS node acceptance; all inputs are artificial."""
import argparse
from contextlib import redirect_stdout,redirect_stderr
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',LOGGING_DIR='/tmp',MLE_BENCH_DATA_DIR='/unread',SUPERIMAGE_DIR='/unread',
    DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
sys.path.insert(0,str(a.source/'src'))
with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
    import jsonschema
    from dojo.solvers.mcts import mcts
    from dojo.core.solvers.operators.analyze import analyze_schema_with_eval
    from dojo.core.solvers.llm_helpers.backends.review_metric import normalize_review
    schema=json.loads(analyze_schema_with_eval)
    fixtures=[('0.75',False,0,True,False),('not available',True,1,False,True),
        ('not available',True,0,True,True),('75%',False,0,True,True),
        (True,False,0,True,True),('0.75',False,0,False,True),('0.75',False,1,True,True)]
    def exercise(value,bug,exit_code,valid,use_fix):
        def analyze(node):
            raw=dict(is_bug=bug,metric=value,summary='artificial')
            output=normalize_review(raw,schema,'submit_review') if use_fix else raw
            jsonschema.Draft7Validator(schema).validate(output)
            return output
        solver=SimpleNamespace(_analyze=analyze,logger=logging.getLogger('artificial'),
            cfg=SimpleNamespace(use_test_score=False),lower_is_better=False)
        node=SimpleNamespace(id='artificial',exit_code=exit_code,_term_out=[],absorb_exec_result=lambda _:None)
        result={mcts.EXECUTION_OUTPUT:None,mcts.VALID_SOLUTION:valid}
        mcts.MCTS.parse_eval_result(solver,node,result)
        return node
    old=exercise(*fixtures[0][:4],False)
    assert old.is_buggy, 'old type failure must reproduce'
    for value,bug,exit_code,valid,wanted in fixtures:
        node=exercise(value,bug,exit_code,valid,True)
        assert bool(node.is_buggy)==wanted
        if not wanted:assert node.metric.value==.75
        else:assert node.metric.value is None
files=['solvers/mcts/mcts.py','core/solvers/llm_helpers/backends/lite_llm.py',
       'core/solvers/llm_helpers/backends/review_metric.py']
print(json.dumps(dict(artificial_cases=len(fixtures),passed=len(fixtures),old_failure_reproduced=True,
    api_calls=0,gpu_jobs=0,task_runs=0,source=str(a.source),
    hashes={f:hashlib.sha256((a.source/'src/dojo'/f).read_bytes()).hexdigest() for f in files})))
