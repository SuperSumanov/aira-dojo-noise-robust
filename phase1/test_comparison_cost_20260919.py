import copy
import unittest
from analyze_comparison_cost_20260919 import analyze


class CostTest(unittest.TestCase):
    def data(self):
        runs=[dict(run='r',stratum='leaf',arm='forets',seed=1,journal_present=True)]
        nodes=[dict(run='r',id=str(i),group='executed' if i<2 else 'unselected',
                    operators_used=['draft'],parents=[0],exec_time=i+1,code_chars=1) for i in range(6)]
        metadata=[dict(run='r',node=n['id'],group=n['group'],operators=['draft'],
                       numeric_operator_fields={'.0.usage.latency':10+int(n['id']),'.0.usage.cost':0}) for n in nodes]
        return runs,nodes,metadata

    def test_parallel_not_sum(self):
        result=analyze(*self.data())['root_pools'][0]
        self.assertEqual(result['longest_request_seconds'],15)
        self.assertEqual(result['selected_execution_sum_seconds'],3)
        self.assertEqual(result['longest_generation_over_selected_execution'],5)

    def test_duplicates(self):
        runs,nodes,meta=self.data();meta.append(copy.deepcopy(meta[0]))
        with self.assertRaises(ValueError):analyze(runs,nodes,meta)

    def test_missing_identity(self):
        runs,nodes,meta=self.data()
        with self.assertRaises(ValueError):analyze(runs,nodes,meta[:-1])

    def test_missing_latency(self):
        runs,nodes,meta=self.data();meta[0]['numeric_operator_fields']={}
        with self.assertRaises(ValueError):analyze(runs,nodes,meta)

    def test_zero_execution(self):
        runs,nodes,meta=self.data()
        for n in nodes:n['exec_time']=0
        self.assertIsNone(analyze(runs,nodes,meta)['root_pools'][0]['longest_generation_over_selected_execution'])

    def test_missing_run_not_silently_dropped(self):
        runs,nodes,meta=self.data();runs.append(dict(run='missing',stratum='leaf',arm='mcts',seed=2,journal_present=False))
        result=analyze(runs,nodes,meta)
        self.assertEqual(result['runs'][1]['requests'],0)
        self.assertFalse(result['runs'][1]['journal_present'])

if __name__=='__main__':unittest.main()
