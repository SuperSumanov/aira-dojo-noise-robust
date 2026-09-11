import ast
import hashlib
from pathlib import Path
import tarfile
import unittest
from forets_successor_budget_20260912 import terms, patch, patch_catalog


class SuccessorBudgetTests(unittest.TestCase):
    def facts(self,**changes):
        f=dict(accounted=1200000000,settled=500000000,calls=90,unknown=1,authorization='a'*64,seed=12)
        return dict(f,**changes)

    def test_plus_carries_unknown_and_does_not_reset_total(self):
        a=terms('qwen/qwen3-coder-plus',**self.facts())
        self.assertEqual(a['total'],9200000000)
        self.assertEqual(a['predecessor_accounted'],1200000000)
        self.assertEqual(a['predecessor_unresolved'],1)
        self.assertEqual(a['reservation'],2600000000)
        self.assertGreater(a['run_limit'],2*a['reservation'])

    def test_cumulative_ceiling_includes_all_prior_charges(self):
        a=terms('qwen/qwen3-coder-plus',**self.facts(accounted=3000000000))
        self.assertEqual(a['total'],10000000000)
        self.assertEqual(a['incremental_cap'],7000000000)
        self.assertEqual(a['accounted_cny_ceiling'],'88.0')

    def test_flash_keeps_same_reservation_and_scope(self):
        a=terms('qwen/qwen3-coder-flash',**self.facts())
        self.assertEqual((a['reservation'],a['run_limit'],a['incremental_cap']),(700000000,1500000000,2000000000))

    def test_no_room_or_invalid_facts_rejected(self):
        for f in (self.facts(accounted=8000000000),self.facts(settled=1500000000),
                  self.facts(seed=11),self.facts(unknown=True)):
            with self.assertRaises(ValueError):terms('qwen/qwen3-coder-plus',**f)

    def test_patch_actual_published_source_without_activating_ledger(self):
        capsule=Path(__file__).parent/'releases/forets-review-20260912/release-code-capsule.tar.gz'
        self.assertEqual(hashlib.sha256(capsule.read_bytes()).hexdigest(),
                         '2a33f870ac88b1bf2a2902d7bde7900a18aba8b1c61feb737761bbeb3d3d1f3b')
        with tarfile.open(capsule) as archive:
            source=archive.extractfile('code/forets_paid_budget_20260911.py').read().decode()
        for model in ('qwen/qwen3-coder-flash','qwen/qwen3-coder-plus'):
            changed,auth=patch(source,model,**self.facts())
            namespace={}
            exec(compile(changed,'<pure successor budget>','exec'),namespace)
            self.assertEqual(namespace['MODEL'],model)
            self.assertEqual(namespace['AUTH']['model'],model)
            self.assertEqual(namespace['RESERVE'],auth['reservation'])
            self.assertEqual(namespace['AUTH']['provider'],namespace['PROVIDER'])
            self.assertFalse(namespace['PROVIDER']['allow_fallbacks'])
            self.assertEqual(namespace['AUTH']['total'],auth['total'])
            self.assertEqual(namespace['AUTH']['predecessor_unresolved'],1)
            with self.assertRaisesRegex(RuntimeError,'exact cumulative ledger handover'):
                namespace['initialize'](None,[])

    def test_actual_catalog_still_checks_provider_capabilities_and_prices(self):
        capsule=Path(__file__).parent/'releases/forets-review-20260912/release-code-capsule.tar.gz'
        with tarfile.open(capsule) as archive:
            source=archive.extractfile('code/forets_paid_route_20260911.py').read().decode()
        tree=ast.parse(patch_catalog(source))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='catalog_valid')
        namespace=dict(MODEL='qwen/qwen3-coder-plus',AUTH={'provider':{'max_price':{'prompt':2.4375,'completion':9.75}}})
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<catalog function>','exec'),namespace)
        endpoint=dict(tag='alibaba',context_length=1000000,max_completion_tokens=65536,
            supported_parameters=['tools','tool_choice'],supports_tool_choice={'function':True},
            pricing={'prompt':'0.00000065','completion':'0.00000325','overrides':[
                {'min_prompt_tokens':128000,'prompt':'0.00000195','completion':'0.00000975','input_cache_write':'0.0000024375'}]})
        result=namespace['catalog_valid']({'data':{'endpoints':[endpoint]}})
        self.assertTrue(result['price_bound_verified'])
        endpoint['pricing']['overrides'][0]['completion']='0.00000976'
        with self.assertRaisesRegex(ValueError,'price changed'):
            namespace['catalog_valid']({'data':{'endpoints':[endpoint]}})


if __name__=='__main__':unittest.main()
