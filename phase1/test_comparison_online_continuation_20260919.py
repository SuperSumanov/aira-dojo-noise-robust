import copy,json,random,unittest
from pathlib import Path
import run_comparison_online_continuation_20260919 as m

class ProtocolTests(unittest.TestCase):
    def test_matrix_and_cost(self):
        p=json.loads(Path(m.__file__).with_name(m.PLAN).read_text())
        self.assertEqual(p['gpus']*p['whole_allocation_seconds']/3600,p['gpu_hours_cap'])
        self.assertEqual(p['episode_seconds'],m.EPISODE)
        self.assertEqual(p['maximum_debug_depth'],20)
        self.assertGreaterEqual(m.CAP,1500+2*m.EPISODE+100)
    def test_selection_uses_only_fixed_independent_rng(self):
        rows=[dict(node=str(i),role='cache',index=i) for i in range(4)]
        state=random.getstate();a=m.select_cache(rows,1)
        self.assertEqual(state,random.getstate())
        self.assertEqual(a,m.select_cache(list(reversed(rows)),1))
        b=copy.deepcopy(rows)
        for i,r in enumerate(b):r['score']=999-i
        self.assertEqual(a['node'],m.select_cache(b,1)['node'])
    def test_duplicate_fails(self):
        with self.assertRaises(ValueError):m.select_cache([dict(node='x',role='cache',index=i) for i in range(4)],1)
    def test_operator_only_route_seed_and_bounds_change(self):
        case=dict(seed=1,operator={'llm':{}},analysis_operator={'llm':{}},analysis_sampling={'temperature':0,'top_p':1})
        a=m.operator(case,'debug',0,1,1900);b=m.operator(case,'debug',1,1,1900)
        self.assertEqual(a['llm']['generation_kwargs'],b['llm']['generation_kwargs'])
        self.assertEqual(a['llm']['generation_kwargs']['seed'],100101)
        c=m.operator(case,'analyze',1,0,12)
        self.assertEqual(c['llm']['generation_kwargs']['bounded_request_timeout_seconds'],12)
        self.assertEqual(c['llm']['generation_kwargs']['temperature'],0)
        self.assertEqual(c['llm']['generation_kwargs']['seed'],300001)

if __name__=='__main__':unittest.main()
