"""Actual deployed runtime + SQLite ledger, only model/task outputs synthetic."""
import ast,asyncio,contextlib,copy,dataclasses,json,sqlite3,subprocess,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import forets_ready_runtime_patch_20260919 as build

REV='b7f8ab0f65dba9877ac3af35e3e770fc32546565'
BASE=Path(__file__).resolve().parents[1]
def source(path):return subprocess.check_output(['git','show',REV+':'+path],cwd=BASE).decode()
def namespace(text):
    value={};exec(compile(text,'pinned-real-source','exec'),value);return value
def original_sources():return {p:source(p) for p in build.EXPECTED}

@dataclasses.dataclass(eq=False)
class Node:
    id:str
    code:str='pass'
    ctime:float=1.
    plan:str=''
    operators_used:list=dataclasses.field(default_factory=lambda:['draft'])
    operators_metrics:list=dataclasses.field(default_factory=list)
    parents:list=dataclasses.field(default_factory=list)
    children:set=dataclasses.field(default_factory=set)
    metric:object=None
    is_buggy:object=None
    explore_count:int=0
    node_value:float=0.

class Journal:
    def __init__(self,nodes=()):self.nodes=list(nodes)
    def node_list(self):return [dict(id=n.id,code=n.code) for n in self.nodes]
    def append(self,node):self.nodes.append(node)

class Harness:
    def __init__(self,root,order,bugs=(True,True,True),limit=8,policy='critic_topk_random'):
        self.cfg=types.SimpleNamespace(num_children=3,selector_seed=6,selection_policy=policy,selection_coupling='independent_subset_v2',skip_redundant_critic=False,cheap_ranker='none',checkpoint_path=str(root),max_llm_call_retries=1,execution_timeout=30,step_limit=limit,chosen_batch_order=order)
        self.state=types.SimpleNamespace(current_step=0);self.task_name='synthetic';self.task_desc='synthetic';self.data_preview=''
        self.root=Node('root',code='');self.journal=Journal([self.root]);self.journal_for_unselected=Journal()
        self.global_min_q_val=0.;self.global_max_q_val=1.;self.critic_top_k=3;self.num_children_to_choose=2
        self.trace=[];self.produced=0;self.bugs=bugs
    @property
    def remaining_steps(self):return self.cfg.step_limit-self.state.current_step
    async def _draft(self,parent):
        i=self.produced;self.produced+=1;self.trace.append(('generate',i));return Node(str(i),code='code'+str(i))
    _improve=_draft
    def step_task(self,state,code):
        self.trace.append(('execute',code));return state,dict(execution_output=types.SimpleNamespace(exit_code=0,timed_out=False,exec_time=.001),code=code)
    def parse_eval_result(self,node,eval_result):
        node.is_buggy=self.bugs[int(node.id)] if node.id.isdigit() else False
        node.metric=types.SimpleNamespace(value=None if node.is_buggy else .8)
        self.trace.append(('analyze',node.code))
    def log_journal(self):self.trace.append(('journal',self.journal.nodes[-1].code))
    def _backprop_step(self,path,value_estimate):self.trace.append(('backprop',path[-1].code,value_estimate))
    def set_global_q_values(self,metric):self.trace.append(('global_q',metric))
    def debug_cycle(self,state,task,node):
        if self.remaining_steps<=0:return state,[],None
        self.trace.append(('debug',node.code));fixed=Node('fixed'+node.id,code='repair'+node.id,parents=[node])
        state,result=task.step_task(state,fixed.code);self.parse_eval_result(fixed,result)
        self.journal.append(fixed);self.state.current_step+=1;return state,[node,fixed],.8

class NoPaidGuard:
    def __init__(self,*args):pass
    def slot(self,*args):return contextlib.nullcontext()

def run(sources,order,local_reward=False,**kwargs):
    led=namespace(sources[build.LEDGER]);witness=namespace(source('src/dojo/solvers/fore_ts/execution_witness.py'))
    selector=namespace(source('src/dojo/solvers/fore_ts/selection.py'))
    tree=ast.parse(sources[build.RUNTIME]);tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
    env=dict(asyncio=asyncio,copy=copy,Path=Path,ExecutionWitness=witness['ExecutionWitness'],EXECUTION_OUTPUT='execution_output',BatchRequestGuard=NoPaidGuard,
             CandidateLedger=led['CandidateLedger'],LedgerError=led['LedgerError'],digest=led['digest'],POLICIES=selector['POLICIES'],choose_slots=selector['choose_slots'])
    with tempfile.TemporaryDirectory() as directory:
        solver=Harness(Path(directory),order,**kwargs)
        if local_reward:
            from forets_local_reward_transport_20260919 import validate_config
            solver.cfg.critic_max_attempts=1;solver.critic_host='127.0.0.1';solver.critic_port=8765
            env['validate_reward_config']=validate_config
            async def rank_nodes(s,nodes):s.trace.append(('critic',tuple(n.code for n in nodes)));return list(range(len(nodes)))
            env['rank_nodes']=rank_nodes
        async def rank_pool(task,codes,*args,**kw):solver.trace.append(('critic',tuple(codes)));return list(range(len(codes)))
        env['rank_pool']=rank_pool
        common=types.SimpleNamespace(initial=lambda *_:False,make_node=None,digest=None)
        refs=types.SimpleNamespace(reference_context=lambda *_ ,**kw:None)
        wall=types.SimpleNamespace(budget=lambda:None,checkpoint_incumbent=lambda s:None)
        with patch.dict('sys.modules',{'dojo.solvers.fore_ts.common_start':common,'dojo.solvers.fore_ts.reference_context':refs,'dojo.solvers.fore_ts.wallclock':wall}):
            exec(compile(tree,'actual-batch-runtime','exec'),env)
            env['expand_batch'](solver,[solver.root],{'solver_interpreter':types.SimpleNamespace(timeout=30)},solver,Node,lambda x:x,dict(order=order))
        file,=Path(directory).glob('forets-candidates-private/*.sqlite')
        with contextlib.closing(sqlite3.connect(file)) as db:snapshot=json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])
        return solver,snapshot

class ActualRuntimeOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=original_sources();cls.changed={p:b.decode() for p,b in build.patched_sources(cls.original).items()}
    def test_default_off_equivalent_across_bugs_and_step_budgets(self):
        for bugs in ((False,False,False),(True,True,True),(True,False,True)):
            for limit in (1,2,3,8):
                for policy in ('uniform_random','critic_topk_random'):
                    a,aa=run(self.original,'native',bugs=bugs,limit=limit,policy=policy);b,bb=run(self.changed,'native',bugs=bugs,limit=limit,policy=policy)
                    self.assertEqual(a.trace,b.trace);self.assertEqual(aa['selected'],bb['selected'])
                    self.assertEqual([c['state'] for c in aa['candidates']],[c['state'] for c in bb['candidates']])
    def test_same_generation_scores_selection_and_deferred_real_receipts(self):
        a,aa=run(self.original,'native');b,bb=run(self.changed,'ready_first')
        self.assertEqual(aa['selected'],bb['selected']);self.assertEqual(aa['pool_sha256'],bb['pool_sha256'])
        self.assertEqual([t for t in a.trace if t[0] in ('generate','critic')],[t for t in b.trace if t[0] in ('generate','critic')])
        self.assertEqual([c['intent']['role'] for c in aa['task_calls']],['candidate','debug','candidate','debug'])
        self.assertEqual([c['intent']['role'] for c in bb['task_calls']],['candidate','candidate','debug','debug'])
        self.assertTrue(all(c['state']=='returned' for c in bb['task_calls']));self.assertEqual(bb['phase'],'complete')
        self.assertEqual([c['slot'] for c in bb['task_calls']],bb['selected']+bb['selected'])
    def test_success_only_is_identical_when_enabled(self):
        a,_=run(self.original,'native',bugs=(False,False,False));b,_=run(self.changed,'ready_first',bugs=(False,False,False));self.assertEqual(a.trace,b.trace)
    def test_budget_keeps_ready_candidates_without_hidden_repair(self):
        b,bb=run(self.changed,'ready_first',limit=2)
        self.assertEqual([c['intent']['role'] for c in bb['task_calls']],['candidate','candidate'])
        self.assertTrue(all(bb['candidates'][i].get('debug_skipped_budget') for i in bb['selected']))
        self.assertEqual(b.state.current_step,2)
    def test_unselected_candidates_never_executed_or_attached(self):
        b,bb=run(self.changed,'ready_first')
        selected=set(bb['selected']);self.assertEqual(len(b.journal_for_unselected.nodes),1)
        for node in b.journal_for_unselected.nodes:
            self.assertNotIn(int(node.id),selected);self.assertFalse(node.parents);self.assertIsNone(node.metric)
    def test_unknown_order_fails_before_model_or_task(self):
        with self.assertRaises(RuntimeError):run(self.changed,'unknown')
    def test_unreviewed_source_and_existing_patch_rejected(self):
        broken=dict(self.original);broken[build.RUNTIME]+='\n'
        with self.assertRaises(ValueError):build.patched_sources(broken)
        with self.assertRaises(ValueError):build.patched_sources(self.changed)
    def test_real_config_is_default_off_and_rejects_unknown(self):
        klass=next(n for n in ast.parse(self.changed[build.CONFIG]).body if isinstance(n,ast.ClassDef))
        class Parent:
            def validate(self):pass
        env=dict(dataclass=dataclasses.dataclass,field=dataclasses.field,MISSING=None,MCTSSolverConfig=Parent)
        exec(compile(ast.Module(body=[klass],type_ignores=[]),'real-runtime-config','exec'),env)
        cfg=env['ForeTSSolverConfig']()
        self.assertEqual(cfg.chosen_batch_order,'native')
        for key,value in dict(selector_seed=6,selection_policy='critic_topk_random',num_children=3,critic_top_k=3,num_children_to_choose=2,critic_max_attempts=1,uct_c=1.).items():setattr(cfg,key,value)
        cfg.validate();cfg.chosen_batch_order='ready_first';cfg.validate()
        cfg.chosen_batch_order='unknown'
        with self.assertRaises(ValueError):cfg.validate()
    def test_ledger_prevents_repair_before_pending_ready_candidate(self):
        env=namespace(self.changed[build.LEDGER]);Ledger=env['CandidateLedger'];Error=env['LedgerError']
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(selection_policy='uniform_random',chosen_batch_order='ready_first')
            with Ledger(Path(directory)/'private'/'batch.sqlite',binding,2) as ledger:
                for i in range(2):
                    ledger.begin_generation(i);ledger.generated(i,dict(id=str(i),ctime=1.,code='pass',plan='',operators_used=['draft'],operators_metrics=[]))
                ledger.freeze_pool();ledger.select([0,1]);ledger.begin_execution(0)
                call=ledger.begin_task_call(0,dict(role='candidate'),4)
                ledger.finish_task_call(call,'returned',1,{},None);ledger.defer_debug(0)
                with self.assertRaises(Error):ledger.begin_deferred_debug(0)
                ledger.begin_execution(1)
                with self.assertRaises(Error):ledger.defer_debug(1)  # Missing return receipt.
                call=ledger.begin_task_call(1,dict(role='candidate'),4)
                ledger.finish_task_call(call,'returned',1,{},None);ledger.defer_debug(1)
                with self.assertRaises(Error):ledger.begin_deferred_debug(1)  # Preserve repair order.
                ledger.begin_deferred_debug(0)
                with self.assertRaises(Error):ledger.begin_deferred_debug(1)  # No overlap.
                call=ledger.begin_task_call(0,dict(role='debug'),4)
                ledger.finish_task_call(call,'returned',1,{},None);ledger.execution_completed(0)
                ledger.skip_deferred_debug_budget(1);ledger.finish()
                self.assertEqual(ledger.data['phase'],'complete')

if __name__=='__main__':unittest.main()
