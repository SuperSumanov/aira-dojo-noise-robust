import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run_comparison_reuse_20260919 as driver
from readout_comparison_reuse_20260919 import compare


def bank(debug, values):
    return [dict(role=role,valid=value is not None,score=value,wall_seconds=10.0)
            for role,value in [('prefix',None),('debug',debug)]+[('cache',x) for x in values]]


class ReuseTests(unittest.TestCase):
    def test_no_oracle_single_cache(self):
        r=compare(bank(None,[.2,.4,.6,None]),True)
        self.assertEqual(r['cache_valid_probability'],.75)
        self.assertEqual(r['one_action_cache_vs_debug'],dict(wins=3,ties=1,losses=0,alternatives=4))
        self.assertEqual(r['symbolic_cache_first_then_debug']['terminal_valid_probability'],.75)
    def test_cache_failure_falls_back_not_quality_oracle(self):
        r=compare(bank(.3,[.1,.6,None,None]),True)
        self.assertEqual(r['symbolic_cache_first_then_debug']['terminal_quality_vs_debug'],dict(wins=1,ties=2,losses=1))
    def test_empty_cache_never_saves_time(self):
        r=compare(bank(.3,[None]*4),True)['symbolic_cache_first_then_debug']
        self.assertIsNone(r['strict_latency_gain_if_generation_seconds_greater_than'])
        self.assertEqual(r['expected_latency_intercept_seconds'],20)
        self.assertEqual(r['terminal_valid_probability'],1)
    def test_threshold_substitution(self):
        r=compare(bank(.4,[.2,None,None,None]),True)['symbolic_cache_first_then_debug']
        threshold=r['strict_latency_gain_if_generation_seconds_greater_than']
        self.assertEqual(threshold,30)
        self.assertAlmostEqual(r['expected_latency_intercept_seconds']+r['expected_latency_generation_coefficient']*threshold,10+threshold)
    def test_prefix_mismatch_no_effect(self):
        self.assertEqual(compare(bank(None,[.1]*4),False)['status'],'PREFIX_NOT_REPRODUCED_NO_CONTINUATION_EFFECT')
    def test_unknown_is_not_failure(self):
        rows=bank(None,[.1]*4);rows[-1]['valid']=None
        self.assertEqual(compare(rows,True)['status'],'UNKNOWN_NO_EFFECT_CLAIM')
    def test_selector_uses_execution_indices_not_id_parents(self):
        nodes=[]
        for seed,run in driver.RUNS.items():
            for step,parents,op,group in [(0,[],'','executed'),(1,[0],'draft','executed'),(2,[1],'debug','executed')]+[(i,[0],'draft','unselected') for i in range(3,7)]:
                nodes.append(dict(run=run,step=step,parents=parents,operators_used=[op],group=group,
                                  creation_time=step,id=f'{seed}-{step}',code_sha256='f'*64))
        rows=driver.select_rows(nodes)
        self.assertEqual(len(rows),12);self.assertEqual(rows[1]['node'],'1-2')
        nodes[2]['parents']=[2]
        with self.assertRaises(ValueError):driver.select_rows(nodes)
    def test_two_groups_scheduled_once(self):
        p=dict(allocation_seconds=9000,rows=[dict(index=i,seed=i//6+1) for i in range(12)])
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as temp,patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer,\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',return_value=0),patch.object(driver.subprocess,'Popen',return_value=process) as popen:
            driver.coordinate(Path(temp))
            self.assertEqual([int(c.args[0][-1]) for c in popen.call_args_list],list(range(12)))
            self.assertEqual(writer.call_args.args[1]['attempted_seeds'],[1,2])
    def test_whole_group_deferred_no_shortening(self):
        p=dict(allocation_seconds=9000,rows=[])
        with tempfile.TemporaryDirectory() as temp,patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer,\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',side_effect=[0,1500,1500]),patch.object(driver.subprocess,'Popen') as popen:
            driver.coordinate(Path(temp));popen.assert_not_called()
            self.assertEqual(writer.call_args.args[1]['unstarted_seeds'],[1,2])

    def test_explicit_completion_executes_only_original_unstarted_seed(self):
        p=dict(allocation_seconds=7800,schedule=[2],rows=[dict(index=i,seed=i//6+1) for i in range(12)])
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as temp,patch.dict(driver.os.environ,SLURM_JOB_ID='124'),\
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'job':'124'}),patch.object(driver,'write') as writer,\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',return_value=0),patch.object(driver.subprocess,'Popen',return_value=process) as popen:
            driver.coordinate(Path(temp))
            self.assertEqual([int(c.args[0][-1]) for c in popen.call_args_list],list(range(6,12)))
            self.assertEqual(writer.call_args.args[1]['attempted_seeds'],[2])


if __name__=='__main__':unittest.main()
