import ast,hashlib,os,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import forets_action_incumbent_patch_20260919 as build
from test_comparison_ready_runtime_20260919 import source,namespace,run,original_sources

def sources():return {p:source(p) for p in set(build.EXPECTED)|set(build.EXPECTED_EXTRA)}

class PerActionIncumbent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=build.build(sources())
    def test_only_debug_method_and_outer_call_changed_in_mcts(self):
        def methods(text):
            c=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
            return {n.name:ast.dump(n) for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        a,b=methods(source(build.MCTS)),methods(self.result[build.MCTS])
        self.assertEqual(set(a),set(b))
        self.assertEqual({k for k in a if a[k]!=b[k]},{'__call__','debug_cycle'})
    def test_exactly_one_per_action_hook_and_no_outer_batch_hook(self):
        runtime=self.result[build.RUNTIME].decode();mcts=self.result[build.MCTS].decode()
        self.assertEqual(runtime.count('checkpoint_incumbent(solver)'),1)
        self.assertEqual(mcts.count('checkpoint_incumbent(self)'),1)
        tree=ast.parse(mcts);c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
        outer=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='__call__')
        self.assertNotIn('checkpoint_incumbent',ast.unparse(outer))
    def test_finished_action_survives_later_incomplete_batch(self):
        wall=namespace(self.result[build.WALLCLOCK]);code='pass';digest=hashlib.sha256(code.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            env={'FORETS_SEARCH_START_NS':'1000000000','FORETS_SEARCH_SECONDS':'10','FORETS_INCUMBENT_DIR':d}
            with patch.dict(os.environ,env):
                node=types.SimpleNamespace(code=code,id='accepted-action')
                receipt=dict(code_sha256=digest,archive_dir='/synthetic/only',submission_sha256='a'*64,report_sha256='b'*64)
                wall['remember_submission'](node,{'_forets_submission_archive':receipt})
                solver=types.SimpleNamespace(journal=types.SimpleNamespace(get_best_node=lambda:node),state=types.SimpleNamespace(current_step=2))
                ticks=iter((2000000000,2000000001))
                wall['checkpoint_incumbent'](solver,clock_ns=lambda:next(ticks))
                # A subsequent long generation produces no callback and no eligible commit.
                solver.state.current_step=3
                self.assertIsNone(wall['checkpoint_incumbent'](solver,clock_ns=lambda:11000000000))
                saved=wall['read_incumbent'](Path(d),expected_start_ns=1000000000,expected_seconds=10)
                self.assertEqual(saved['node_id'],'accepted-action');self.assertEqual(saved['current_step'],2)
                self.assertEqual(saved['selection'],'original_journal_get_best_node_after_executed_analyzed_action')
    def test_no_record_written_when_budget_hook_is_disabled(self):
        wall=namespace(self.result[build.WALLCLOCK])
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(wall['checkpoint_incumbent'](None))
    def test_rejects_source_drift(self):
        inputs=sources();inputs[build.WALLCLOCK]+='\n'
        with self.assertRaises(ValueError):build.build(inputs)

if __name__=='__main__':unittest.main()
