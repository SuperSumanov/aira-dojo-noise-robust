"""Catch the actual production-vs-integration adapter receipt distinction."""
import ast,types,unittest
from pathlib import Path
source=Path(__file__).parent.parent/'src/dojo/core/interpreters/fresh_container.py'
tree=ast.parse(source.read_text());tree.body=[n for n in tree.body if not(isinstance(n,ast.ImportFrom) and n.module=='dojo.core.interpreters.base') and not(isinstance(n,ast.ClassDef) and n.name=='FreshContainerInterpreter')]
module=types.ModuleType('receipt_helpers');exec(compile(tree,'<helpers>','exec'),module.__dict__)
class Tests(unittest.TestCase):
    def test_production_exact_child_receipt(self):
        p=Path('/root/worker.attempt-1.json')
        self.assertEqual(module.native_binding_path(p,123,{'FORETS_NATIVE_RELEASE':'release.json'}),p.with_name(p.name+'.native-binding-123.json'))
    def test_integration_fixed_receipt(self):
        p=Path('/root/identity-0.json')
        for key in ('FORETS_CURRENT_POOL_ROOT','FORETS_NATIVE_INTEGRATION_ROOT'):
            self.assertEqual(module.native_binding_path(p,123,{key:'/root'}),p.with_suffix('.native-binding.json'))
    def test_no_silent_mode_or_pid(self):
        for pid in (0,1,True,'123'):
            with self.assertRaises(ValueError):module.native_binding_path('/root/a.json',pid,{'FORETS_NATIVE_RELEASE':'a'})
        with self.assertRaises(module.ProcessInfrastructureError):module.native_binding_path('/root/a.json',123,{})
    def test_production_matches_real_adapter_source(self):
        adapter=Path(__file__).with_name('forets_native_gpu_binding_20260911.py').read_text()
        self.assertIn("receipt.with_name(receipt.name+f'.native-binding-{os.getpid()}.json')",adapter)
        self.assertIn('binding.name in prior_names',source.read_text())
if __name__=='__main__':unittest.main()
