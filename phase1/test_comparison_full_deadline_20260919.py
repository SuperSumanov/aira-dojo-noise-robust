import asyncio,unittest
from unittest.mock import patch
from comparison_full_deadline_policy_20260919 import transform
import run_comparison_online_continuation_20260919 as driver

METHOD='''async def _query_once_bounded(self, request_kwargs, local_generator):
    deadline_limit = 1200 if local_generator else 300
    kwargs = request_kwargs.copy()
    return deadline_limit, kwargs
'''

class FullDeadline(unittest.TestCase):
    def test_local_removes_cap_and_remote_is_unchanged(self):
        namespace={};exec(transform(METHOD),namespace)
        function=namespace['_query_once_bounded'];original={'max_tokens':32768,'temperature':.6}
        self.assertEqual(asyncio.run(function(None,original,True)),(2100,{'temperature':.6}))
        self.assertEqual(asyncio.run(function(None,original,False)),(300,original))
        self.assertEqual(original['max_tokens'],32768)
    def test_ambiguous_source_fails(self):
        for text in (METHOD.replace('1200','1199'),METHOD+METHOD):
            with self.assertRaises(ValueError):transform(text)
    def test_both_operators_get_remaining_time(self):
        case=dict(seed=1,operator={'llm':{}},analysis_operator={'llm':{}},analysis_sampling={})
        with patch.object(driver,'FULL_DEADLINE',True):
            for kind in ('debug','analyze'):
                for remaining in (23,1500,2090):
                    kw=driver.operator(case,kind,0,1,remaining)['llm']['generation_kwargs']
                    self.assertEqual(kw['bounded_request_timeout_seconds'],remaining)
                    self.assertEqual(kw['bounded_max_attempts'],1)
    def test_old_default_is_not_changed(self):
        case=dict(seed=1,operator={'llm':{}},analysis_operator={'llm':{}},analysis_sampling={})
        with patch.object(driver,'FULL_DEADLINE',False):
            self.assertEqual(driver.operator(case,'debug',0,1,1900)['llm']['generation_kwargs']['bounded_request_timeout_seconds'],1200)

if __name__=='__main__':unittest.main()
