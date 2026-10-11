import copy,inspect,unittest
import joint_four_readout_20261011 as r

class Tests(unittest.TestCase):
    def test_exact_adaptation_preserves_seed_and_tolerance(self):
        text=r.adapt(inspect.getsource(r.v.verify))
        self.assertIn("p['source_seed'] == 42",text)
        self.assertIn('diff<=1e-5',text)
        self.assertIn('len(comparisons)==20',text)
        self.assertIn('unstarted=10-',text)
        compile(text,'adapted','exec')
        with self.assertRaises(AssertionError):r.adapt(text)
    def test_gate_rejects_incomplete_coverage_wrong_placement_steps_and_error(self):
        rows=[dict(complete=True) for _ in range(10)]
        result=dict(full_capacity_gate=True,blocks=[dict(gpus=g,physical_cores=c) for g,c in [(3,12),(3,12),(6,24),(6,24)]])
        args=[rows,result,True,True,{k:0 for k in r.FLAGS},True,True]
        self.assertTrue(r.extra_gate(*args))
        for index in (2,3,5,6):
            bad=copy.deepcopy(args);bad[index]=False;self.assertFalse(r.extra_gate(*bad))
        bad=copy.deepcopy(args);bad[0][9]['complete']=False;self.assertFalse(r.extra_gate(*bad))
        bad=copy.deepcopy(args);bad[1]['blocks'][2]['gpus']=5;self.assertFalse(r.extra_gate(*bad))
        bad=copy.deepcopy(args);bad[4][r.FLAGS[0]]=1;self.assertFalse(r.extra_gate(*bad))
if __name__=='__main__':unittest.main()
