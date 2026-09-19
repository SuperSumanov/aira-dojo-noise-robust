import copy,unittest
from readout_comparison_unrunnable_20260919 import build

class UnrunnableTests(unittest.TestCase):
    def fixture(self):
        rows=[dict(seed=s,request_seed=600+s,generation_seconds=700.0,run='run'+str(s),
                   generation_status='truncated',runnable=False) for s in (1,2)]
        generated=[dict(seed=s,request_seed=600+s,generation_seconds=700.0,source_run='run'+str(s),
                        status='truncated',finish_reason='length') for s in (1,2)]
        return dict(gpus=0,rows=rows,generation_job='14134',generation_allocation_seconds=2021),dict(rows=generated),['14134','COMPLETED','2021','gpu28','gres/gpu=2']
    def test_no_code_remains_unknown_with_real_cost(self):
        p,g,a=self.fixture();out=build(p,g,a)
        self.assertIsNone(out['job']);self.assertEqual(out['unknown'],2)
        self.assertEqual(out['no_valid_output'],0);self.assertEqual(out['execution_gpu_hours'],0)
        self.assertEqual(out['generation_gpu_hours'],2021*2/3600)
        self.assertTrue(all(row['valid'] is None for row in out['rows']))
    def test_runnable_cannot_be_closed_without_execution(self):
        p,g,a=self.fixture();p['rows'][0]['runnable']=True
        with self.assertRaises(ValueError):build(p,g,a)
    def test_prefix_swap_rejected(self):
        p,g,a=self.fixture();g['rows'][0]['source_run']='another'
        with self.assertRaises(ValueError):build(p,g,a)
    def test_running_or_wrong_hardware_rejected(self):
        p,g,a=self.fixture()
        for index,value in ((1,'RUNNING'),(3,'projgpu39'),(4,'gres/gpu=1'),(2,'2022')):
            changed=copy.deepcopy(a);changed[index]=value
            with self.assertRaises(ValueError):build(p,g,changed)
    def test_false_truncation_rejected(self):
        p,g,a=self.fixture();g['rows'][1]['finish_reason']='stop'
        with self.assertRaises(ValueError):build(p,g,a)

if __name__=='__main__':unittest.main()
