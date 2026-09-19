import os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run_comparison_pool_20260919 as driver


class RemainderTest(unittest.TestCase):
    def test_only_original_third_scheduled(self):
        p=dict(only_seed=3,allocation_seconds=7800,rows=[dict(index=i,seed=i//6+1) for i in range(18)])
        proc=Mock();proc.wait.return_value=0
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,SLURM_JOB_ID='123'), \
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'), \
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer, \
             patch.object(driver.socket,'gethostname',return_value='gpu28'), \
             patch.object(driver.time,'monotonic',side_effect=[0,0]), \
             patch.object(driver.subprocess,'Popen',return_value=proc) as popen:
            driver.coordinate(Path(directory))
            self.assertEqual(popen.call_count,6)
            self.assertEqual([int(c.args[0][-1]) for c in popen.call_args_list],list(range(12,18)))
            final=writer.call_args.args[1]
            self.assertEqual(final['attempted_seeds'],[3]);self.assertEqual(final['unstarted_seeds'],[])

    def test_remaining_time_gate_still_applies(self):
        p=dict(only_seed=3,allocation_seconds=7800,rows=[])
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,SLURM_JOB_ID='123'), \
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'), \
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer, \
             patch.object(driver.socket,'gethostname',return_value='gpu28'), \
             patch.object(driver.time,'monotonic',side_effect=[0,250]), \
             patch.object(driver.subprocess,'Popen') as popen:
            driver.coordinate(Path(directory));popen.assert_not_called()
            self.assertEqual(writer.call_args.args[1]['unstarted_seeds'],[3])

if __name__=='__main__':unittest.main()
