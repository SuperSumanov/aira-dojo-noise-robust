import collections,inspect,unittest
import joint_two_node_20261011 as d
import joint_two_node_readout_20261011 as v

class Tests(unittest.TestCase):
    def test_fixed_14_same_families_and_two_plus_four_placement(self):
        rows=d.schedule();self.assertEqual(len(rows),14)
        self.assertEqual(collections.Counter(r['program'] for r in rows),{0:7,1:7})
        for b in (2,3):self.assertEqual(collections.Counter(r['node'] for r in rows if r['block']==b),{'gpu3':2,'gpu27':4})
    def test_srun_scope_is_single_explicit_node(self):
        source=d.controller_source(inspect.getsource(d.r.controller))
        self.assertIn("'--nodelist='+row['node']",source);self.assertIn("'--nodes=1'",source)
        self.assertIn('complete!=14',source);compile(source,'controller','exec')
        compile(d.allocation_source(inspect.getsource(d.r.allocation)),'allocation','exec')
    def test_cores_qualified_by_node_and_overlap_rejected(self):
        def cpu(node,start,n):return [dict(node=node,socket=0,core=x,logical_cpu=x) for x in range(start,start+n)]
        service=dict(uuids=['a','b'],step='s')
        workers=[dict(gpu_uuids=['c'],cpu_topology=cpu('gpu27',0,4),job='j',step='w')]
        self.assertEqual(v.placed(service,cpu('gpu3',0,8),workers,'j')['physical_cores'],12)
        self.assertEqual(d.placement(service,cpu('gpu3',0,8),workers,'j')['physical_cores'],12)
        workers[0]['cpu_topology']=cpu('gpu3',0,4)
        with self.assertRaises(AssertionError):v.placed(service,cpu('gpu3',0,8),workers,'j')

if __name__=='__main__':unittest.main()
