import copy
import itertools
import unittest
from readout_comparison_reuse_20260919 import compare
from verify_comparison_reuse_results_20260919 import enumerate_paths, verify


def fixture(debug,cache):
    rows=[];groups=[]
    for seed in (1,2):
        for i,(role,value) in enumerate([('prefix',None),('debug',debug)]+[('cache',v) for v in cache]):
            rows.append(dict(seed=seed,index=(seed-1)*6+i,node=f'{seed}-{i}',role=role,valid=value is not None,
                             score=value,independent_score=value,wall_seconds=i*7+3.5))
        group=[r for r in rows if r['seed']==seed]
        groups.append(dict(seed=seed,prefix_matches=True,**compare(group,True)))
    return dict(role='exploratory_continuation_action_bank_not_live_e2e',rows=rows,groups=groups,
                api_calls=0,allocated_gpus=6,allocation_seconds=600,gpu_hours=1,
                valid=sum(r['valid'] for r in rows),no_valid_output=sum(not r['valid'] for r in rows),unknown=0)


class VerifierTests(unittest.TestCase):
    def test_exhaustive_quality_and_validity_patterns(self):
        for debug in (None,.1,.2,.3):
            for cache in itertools.product((None,.1,.2,.3),repeat=4):
                self.assertEqual(verify(fixture(debug,cache))['status'],'PASS')

    def test_reject_oracle_replacement(self):
        s=fixture(.2,[.1,.3,None,None]);s['groups'][0]['symbolic_cache_first_then_debug']['terminal_quality_vs_debug']={'wins':1,'ties':3,'losses':0}
        with self.assertRaises(AssertionError):verify(s)

    def test_reject_negative_unknown(self):
        s=fixture(None,[None]*4);s['rows'][2]['valid']=None
        with self.assertRaises(AssertionError):verify(s)

    def test_reject_cost_change(self):
        s=fixture(.2,[.1,.3,None,None]);s['groups'][0]['symbolic_cache_first_then_debug']['expected_latency_intercept_seconds']+=1
        with self.assertRaises(AssertionError):verify(s)

    def test_one_uniform_cache_not_four_executions(self):
        s=fixture(.2,[.1,.3,None,None]);e=enumerate_paths(s['rows'][:6])
        self.assertEqual([p['executions'] for p in e['paths']],[1,1,2,2])


if __name__=='__main__':unittest.main()
