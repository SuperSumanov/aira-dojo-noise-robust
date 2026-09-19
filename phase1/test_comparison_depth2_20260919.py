import copy, unittest
from unittest.mock import patch
from test_comparison_reuse_verifier_20260919 import fixture
from analyze_comparison_depth2_20260919 import analyze
import run_comparison_live_debug_execute_20260919 as execution
import run_comparison_depth2_execute_20260919 as depth

def inputs():
    banks=fixture(None,[.1,.2,.3,None]);banks['job']='A+B'
    first=dict(role='fresh_native_debug_draws_not_live_e2e',job='C',generation_job='D',total_gpu_hours=1,rows=[])
    second=dict(role='fresh_native_debug_draws_not_live_e2e',job='E',generation_job='F',total_gpu_hours=2,rows=[])
    for seed in (1,2):
        rows=[r for r in banks['rows'] if r['seed']==seed]
        for r in rows:r['run']=str(seed)
        common=dict(seed=seed,run=str(seed),generation_seconds=100,wall_seconds=20,valid=False,score=None)
        first['rows'].append(dict(common,request_seed=500+seed))
        second['rows'].append(dict(common,request_seed=600+seed))
    return banks,first,second

class DepthTests(unittest.TestCase):
    def test_earlier_failed_work_not_free(self):
        b,a,c=inputs();out=analyze(b,a,c)
        self.assertEqual(out['groups'][0]['fixed_trace_latency_diagnostic']['debug_chain_seconds'],240)
        self.assertEqual(out['generation_and_execution_gpu_hours'],3)
    def test_new_success_can_defeat_cache(self):
        b,a,c=inputs();c['rows'][0].update(valid=True,score=0.00001)
        out=analyze(b,a,c)['groups'][0]
        self.assertEqual(out['single_cache_vs_depth2']['losses'],4)
        self.assertEqual(out['single_cache_vs_depth2']['wins'],0)
    def test_unknown_is_not_failure_or_gain(self):
        b,a,c=inputs();c['rows'][1]['valid']=None
        self.assertEqual(analyze(b,a,c)['groups'][1],dict(seed=2,status='UNKNOWN_NO_EFFECT_CLAIM'))
    def test_rejects_continuing_already_successful_first(self):
        b,a,c=inputs();a['rows'][0].update(valid=True,score=.1)
        with self.assertRaises(ValueError):analyze(b,a,c)
    def test_no_best_response_replacement(self):
        b,a,c=inputs();c['rows'][0]['request_seed']=999
        with self.assertRaisesRegex(ValueError,'matrix'):analyze(b,a,c)
    def test_same_run_required(self):
        b,a,c=inputs();c['rows'][0]['run']='different'
        with self.assertRaisesRegex(ValueError,'prefix'):analyze(b,a,c)
    def test_nonfinite_cost_rejected(self):
        b,a,c=inputs();a['rows'][0]['generation_seconds']=float('nan')
        with self.assertRaises(ValueError):analyze(b,a,c)
    def test_depth_execution_is_explicitly_pinned(self):
        names=('GEN','GEN_PREPARED','ROOT_PREFIX','REQUEST_SEEDS','SCRIPT','READER','CONTEXT_MODULE','EXTRA_FILES')
        with patch.multiple(execution,**{n:getattr(execution,n) for n in names}):
            depth.configure()
            self.assertEqual(execution.REQUEST_SEEDS,[601,602])
            self.assertEqual(execution.GEN.name,'comparison-depth2-debug-20260919-ffunn8gg')
            self.assertIn('run_comparison_live_debug_execute_20260919.py',execution.EXTRA_FILES)

if __name__=='__main__':unittest.main()
