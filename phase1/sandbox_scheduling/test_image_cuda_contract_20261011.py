import ast,os,re,stat,types,unittest
from pathlib import Path
from image_cuda_contract_20261011 import valid_mask,mask_matches

U='GPU-11111111-2222-3333-4444-555555555555'
V='GPU-66666666-7777-8888-9999-aaaaaaaaaaaa'

class ContractTests(unittest.TestCase):
    def test_legacy_single_index(self):self.assertTrue(mask_matches('0',U))
    def test_exact_uuid(self):self.assertTrue(mask_matches(U,U))
    def test_other_uuid_rejected(self):self.assertFalse(mask_matches(U,V))
    def test_multiple_or_ambiguous_devices_rejected(self):
        for v in ('','1','0,1',U+','+V,None,'GPU-'+36*'x'):self.assertFalse(valid_mask(v))
    def test_selected_must_be_uuid(self):
        for v in ('0','',None):self.assertFalse(mask_matches('0',v))

class ActualResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path(__file__).with_name('forets_native_gpu_binding_20260911.py').read_text()
        tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='resolve_native')
        env=dict(os=os,re=re,stat=stat,mask_matches=mask_matches)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-native-resolver','exec'),env)
        cls.resolve=staticmethod(env['resolve_native'])
    def record(self,mask):
        return dict(device_count=1,cuda_visible_devices=mask,selected_uuid=U,pci_bus_id='0000:07:00.0',
                    driver_metadata_matches=[dict(bus_location='0000:07:00.0',device_minor='7')])
    def fake_stat(self,path):
        self.assertEqual(path,'/dev/nvidia7')
        return types.SimpleNamespace(st_mode=stat.S_IFCHR,st_rdev=os.makedev(195,7))
    def test_actual_resolver_accepts_index_and_verified_uuid(self):
        for mask in ('0',U):self.assertEqual(self.resolve(self.record(mask),device_stat=self.fake_stat),(7,U))
    def test_actual_resolver_rejects_wrong_uuid(self):
        with self.assertRaises(ValueError):self.resolve(self.record(V),device_stat=self.fake_stat)
    def test_actual_resolver_keeps_single_device_guard(self):
        r=self.record(U);r['device_count']=2
        with self.assertRaises(ValueError):self.resolve(r,device_stat=self.fake_stat)
    def test_actual_resolver_keeps_pci_guard(self):
        r=self.record(U);r['pci_bus_id']='0000:08:00.0'
        with self.assertRaises(ValueError):self.resolve(r,device_stat=self.fake_stat)
    def test_actual_resolver_keeps_device_node_guard(self):
        r=self.record(U)
        with self.assertRaises(ValueError):self.resolve(r,device_stat=lambda p:types.SimpleNamespace(st_mode=stat.S_IFCHR,st_rdev=os.makedev(195,8)))

if __name__=='__main__':unittest.main()
