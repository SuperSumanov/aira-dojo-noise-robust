import __future__,ast,asyncio,copy,subprocess,types,unittest
from pathlib import Path
from forets_ready_batch_patch_20260919 import patched_sources

BASE=Path(__file__).resolve().parent
SOLVER=(BASE/'fixtures/forets_production_be9335348b.py').read_text()

def source_config():
    return subprocess.check_output(['git','show','be9335348b:src/dojo/config_dataclasses/solver/fore_ts.py'],cwd=BASE.parent).decode()

def methods(text):
    klass=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='ForeTS')
    selected=[n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name in ('_expand_leaf_and_backprop','_execute_ready_chosen_batch')]
    ns=dict(asyncio=asyncio,random=types.SimpleNamespace(sample=lambda xs,n:list(xs[:n])),extract_code=lambda code:code)
    exec(compile(ast.Module(body=selected,type_ignores=[]),'actual-production-method','exec',flags=__future__.annotations.compiler_flag),ns)
    return {n.name:ns[n.name] for n in selected}

class Harness:
    def __init__(self,policy,buggy=(True,False),repair_metric=.7,step_limit=20):
        self.cfg=types.SimpleNamespace(num_children=2,step_limit=step_limit,chosen_batch_order=policy)
        self.remaining_steps=20;self.critic_top_k=2;self.num_children_to_choose=2
        self.state=types.SimpleNamespace(current_step=0);self.trace=[];self.journal=[];self.journal_for_unselected=[];self.produced=0
        self.buggy=buggy;self.repair_metric=repair_metric
        self.logger=types.SimpleNamespace(info=lambda *_:None,debug=lambda *_:None)
    async def _draft(self,parent):
        i=self.produced;self.produced+=1;self.trace.append(('draft',i))
        return types.SimpleNamespace(code=i,is_buggy=self.buggy[i],metric=types.SimpleNamespace(value=.8-i*.1)),2-i
    _improve=_draft
    def step_task(self,state,code):self.trace.append(('execute',code));return state,dict(code=code)
    def parse_eval_result(self,**kwargs):self.trace.append(('analyze',kwargs['node'].code))
    def log_journal(self):self.trace.append(('journal',self.journal[-1].code))
    def _backprop_step(self,path,value_estimate):self.trace.append(('backprop',path[-1].code,value_estimate))
    def set_global_q_values(self,metric):self.trace.append(('global_q',metric))
    def debug_cycle(self,state,task,node):
        self.trace.append(('repair',node.code));self.state.current_step+=1
        fixed=types.SimpleNamespace(code='fixed'+str(node.code));self.journal.append(fixed)
        return state,[node,fixed],self.repair_metric

def run(text,policy,**kwargs):
    solver=Harness(policy,**kwargs)
    for name,fn in methods(text).items():setattr(solver,name,types.MethodType(fn,solver))
    root=types.SimpleNamespace(parents=[])
    state=solver._expand_leaf_and_backprop([root],solver.state,solver)
    assert state is solver.state
    return solver

class ProductionOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch=patched_sources(source_config(),SOLVER)
        cls.changed=cls.patch['src/dojo/solvers/fore_ts/fore_ts.py'].decode()
    def test_disabled_matches_actual_original_including_failures(self):
        for buggy in ((False,False),(True,False),(False,True),(True,True)):
            for metric in (None,.7):
                for cap in (0,1,2,20):
                    original=run(SOLVER,'native',buggy=buggy,repair_metric=metric,step_limit=cap)
                    changed=run(self.changed,'native',buggy=buggy,repair_metric=metric,step_limit=cap)
                    self.assertEqual(original.trace,changed.trace);self.assertEqual(original.state.current_step,changed.state.current_step)
    def test_ready_executes_same_chosen_before_any_repair(self):
        solver=run(self.changed,'ready_first',buggy=(True,True))
        actions=[x for x in solver.trace if x[0] in ('execute','repair')]
        self.assertEqual(actions,[('execute',0),('execute',1),('repair',0),('repair',1)])
        self.assertEqual(solver.produced,2)
    def test_no_bug_is_identical_when_enabled(self):
        self.assertEqual(run(SOLVER,'native',buggy=(False,False)).trace,run(self.changed,'ready_first',buggy=(False,False)).trace)
    def test_budget_exhaustion_does_not_start_deferred_repair(self):
        solver=run(self.changed,'ready_first',buggy=(True,True),step_limit=1)
        self.assertEqual([x for x in solver.trace if x[0]=='repair'],[])
        self.assertEqual(solver.state.current_step,2)
    def test_unknown_policy_fails_before_generation(self):
        with self.assertRaises(ValueError):run(self.changed,'other')
    def test_exact_source_required_and_no_input_mutation(self):
        config=source_config();before=(config,SOLVER);patched_sources(config,SOLVER)
        self.assertEqual((config,SOLVER),before)
        with self.assertRaises(ValueError):patched_sources(config,SOLVER+'\n')
        for path,raw in self.patch.items():compile(raw,path,'exec')
    def test_only_expansion_and_new_helper_change(self):
        def definitions(text):
            cls=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='ForeTS')
            return {n.name:ast.dump(n) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        a,b=definitions(SOLVER),definitions(self.changed)
        self.assertEqual(set(b)-set(a),{'_execute_ready_chosen_batch'})
        for name in a:
            if name!='_expand_leaf_and_backprop':self.assertEqual(a[name],b[name])
    def test_real_config_default_and_validation_are_wired(self):
        from dataclasses import dataclass,field
        cls=next(n for n in ast.parse(self.patch['src/dojo/config_dataclasses/solver/fore_ts.py']).body if isinstance(n,ast.ClassDef))
        class Parent:
            def validate(self):pass
        namespace=dict(dataclass=dataclass,field=field,MISSING=None,MCTSSolverConfig=Parent)
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'real-forets-config','exec'),namespace)
        config=namespace['ForeTSSolverConfig']()
        self.assertEqual(config.chosen_batch_order,'native');config.validate()
        config.chosen_batch_order='ready_first';config.validate()
        config.chosen_batch_order='unknown'
        with self.assertRaises(ValueError):config.validate()

if __name__=='__main__':unittest.main()
