"""Production batch, all real configs, local fixed model; fake execution only."""
import copy,hashlib,json,logging,os,random,sqlite3,sys,tempfile,time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read,write,encode,sha
from build_class_gate_online_20260914 import order,normalize

def independent_selection(n,scores,seed,task,step):
    identity=dict(version='forets-common-priority-v1',seed=seed,task=task,step=step,purpose='selection_order')
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    slots=list(range(n));random.Random(key).shuffle(slots)
    eligible=set(range(n)) if scores is None else {i for i,s in enumerate(scores) if s==max(scores)}
    return [i for i in slots if i in eligible][:1]

def run(root):
    info=read(root/'artifact.json');prepared=read(root/'prepared.json')
    for name,h in info['source_files'].items():
        if sha((root/'source'/name).read_bytes())!=h:raise ValueError('source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')];logging.disable(logging.CRITICAL)
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
    from dojo.solvers.fore_ts.batch_runtime import expand_batch
    from dojo.solvers.fore_ts.selection import choose_slots
    from dojo.core.solvers.utils.response import extract_code
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.core.solvers.utils.metric import MetricValue
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    from dojo.core.interpreters.base import ExecutionResult
    from forets_e2e_package import common_config
    if [(r['block'],r['task'],r['seed'],r['arm']) for r in prepared['run_configs']]!=order():raise ValueError('matrix')
    normalized=[];records=[]
    for seed in range(20):
        for scores in (None,[0.,0.],[0.,1.],[1.,0.]):
            observed=choose_slots(2,1,1,'uniform_random' if scores is None else 'critic_topk_random',seed,'fixture',3,scores,coupling='common_priority_v1')
            if observed!=independent_selection(2,scores,seed,'fixture',3):raise ValueError('strict/tie selector mismatch')
    with tempfile.TemporaryDirectory(prefix='cheap-integration-',dir=root) as tmp:
        for r in prepared['run_configs']:
            raw=read(root/'configs'/(r['run_id']+'.json'),r['config_sha256']);typed=RunConfig.from_dict(raw);typed.validate()
            if typed.to_typed_dict()!=raw:raise ValueError('typed roundtrip')
            if INTERPRETER_MAP[type(typed.interpreter).__name__] is not FreshContainerInterpreter:raise ValueError('factory routing')
            normalized.append(normalize(raw,r['arm'],r['run_id'],root,common_config))
            cfg=copy.deepcopy(raw['solver']);cfg['checkpoint_path']=str(Path(tmp)/r['run_id'])
            if (cfg['time_limit_secs'],cfg['execution_timeout'],cfg['num_children'],cfg['critic_top_k'],cfg['num_children_to_choose'],cfg['edit_scope'])!=(600,300,2,1,1,'whole_program'):raise ValueError('compute contract')
            tree=MCTSNode(code='',parents=[]);journal=Journal();journal.append(tree)
            solver=NS(cfg=NS(**cfg),state=NS(current_step=1,running_time=0.),task_name=r['task'],task_desc='synthetic',data_preview=None,
                journal=journal,journal_for_unselected=Journal(),global_min_q_val=0.,global_max_q_val=1.,critic_top_k=1,num_children_to_choose=1,remaining_steps=63)
            count=dict(generation=0,execution=0)
            async def generate(*args):
                count['generation']+=1;code='print(1)' if count['generation']==1 else 'import math\nx = math.sqrt(4)\nprint(x)'
                return MCTSNode(code=code,parents=[],operators_metrics=[])
            def parse(node,eval_result):
                node.absorb_exec_result(eval_result[EXECUTION_OUTPUT]);node.is_buggy=False;node.metric=MetricValue(.5,maximize=False)
            def step(state,code):
                count['execution']+=1;result=ExecutionResult.get_empty();result.exit_code=0;result.timed_out=False;result.exec_time=.01
                return state,{EXECUTION_OUTPUT:result}
            solver._draft=solver._improve=generate;solver.parse_eval_result=parse;solver.log_journal=lambda:None
            solver._backprop_step=lambda *a,**kw:None;solver.set_global_q_values=lambda v:None
            now=time.monotonic_ns()
            with patch('dojo.solvers.fore_ts.wallclock.budget',return_value=(now-10**9,now+600*10**9,Path(tmp))),patch('dojo.solvers.fore_ts.batch_runtime.rank_pool',side_effect=AssertionError('network ranking forbidden')):
                state={'solver_interpreter':NS(timeout=300)}
                expand_batch(solver,[tree],state,NS(step_task=step),MCTSNode,extract_code,cfg)
                baseline=journal.nodes[-1]
                expand_batch(solver,[tree,baseline],state,NS(step_task=step),MCTSNode,extract_code,cfg)
            if count!=dict(generation=2,execution=2) or len(baseline.children)!=1 or len(solver.journal_for_unselected.nodes)!=1:raise ValueError('actual execution count')
            ck=Path(cfg['checkpoint_path'])
            with closing(sqlite3.connect((ck/'forets-candidates-private/batch-2.sqlite').as_uri()+'?mode=ro',uri=True)) as db:value=json.loads(db.execute('select payload from snapshot').fetchone()[0])
            scores=None if r['arm']=='uniform' else [c['score'] for c in value['candidates']]
            expected=independent_selection(2,scores,r['seed'],r['task'],2)
            if value['selected']!=expected:raise ValueError('production replay')
            calls=value['task_calls'];node=value['candidates'][expected[0]]['node']
            if len(calls)!=1 or calls[0]['intent']['code_sha256']!=sha(extract_code(node['code']).encode()):raise ValueError('delivered code identity')
            receipts=list((ck/'forets-cheap-ranker-private').glob('*.json'))
            if len(receipts)!=int(r['arm']!='uniform'):raise ValueError('cheap scorer request count')
            if r['arm'] in ('learned_validity','class_gate'):
                receipt=read(receipts[0])
                expected_scores=receipt['raw_probabilities'] if r['arm']=='learned_validity' else [float(p>.5) for p in receipt['raw_probabilities']]
                if receipt['scores']!=expected_scores:raise ValueError('production category mapping')
            records.append(dict(run_id=r['run_id'],counts=count,selected=expected,real_model_used=r['arm'] in ('learned_validity','class_gate')))
    if any(normalized[i]!=normalized[i+j] for i in (0,4) for j in (1,2,3)):raise ValueError('extra triple config change')
    result=dict(status='PASSED_ACTUAL_CLASS_GATE_BATCH',source_tree=info['source_tree'],rows=records,config_quadruples=2,tie_cases=80,api_calls=0,gpu_dispatches=0,script_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(sha256=write(root/'cheap-integration.json',encode(result)),**result)))
if __name__=='__main__':run(Path(sys.argv[1]))
