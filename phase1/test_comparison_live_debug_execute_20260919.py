import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run_comparison_live_debug_execute_20260919 as driver


class ExecutionTests(unittest.TestCase):
    def coordinate(self,rows):
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as folder,patch.object(driver,'check',return_value=dict(rows=rows)),\
             patch.object(driver,'source_check'),patch.object(driver,'read',return_value={'job':'123'}),\
             patch.object(driver,'write'),patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),patch.object(driver.subprocess,'Popen',return_value=process) as call:
            driver.coordinate(Path(folder));return call.call_args_list
    def test_two_draws_executed_once_each(self):
        calls=self.coordinate([dict(index=i,runnable=True) for i in range(2)])
        self.assertEqual([int(c.args[0][-1]) for c in calls],[0,1])
        for c in calls:
            self.assertIn('--gres=gpu:1',c.args[0]);self.assertIn('--cpus-per-task=6',c.args[0]);self.assertIn('--time=02:04:00',c.args[0])
    def test_failed_generation_not_replaced(self):
        calls=self.coordinate([dict(index=0,runnable=False),dict(index=1,runnable=True)])
        self.assertEqual([int(c.args[0][-1]) for c in calls],[1])
    def test_no_zero_gpu_submission(self):
        with patch.object(driver,'check',return_value=dict(gpus=0)),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'status':'PASS','prepared_sha256':'x'}),\
             patch.object(driver,'sha',return_value='x'),patch.object(Path,'read_bytes',return_value=b'x'),\
             patch.object(driver.subprocess,'run') as submit:
            with self.assertRaisesRegex(ValueError,'no runnable'):driver.submit(Path('unused'))
            submit.assert_not_called()
    def test_worker_rejects_unrunnable(self):
        with patch.object(driver,'check',return_value=dict(commit='x',rows=[dict(runnable=False)])),\
             patch.object(driver,'setup'),patch.object(driver,'one') as execute:
            with self.assertRaises(ValueError):driver.execute(Path('unused'),0)
            execute.assert_not_called()
    def test_worker_must_be_native_step(self):
        with patch.object(driver,'check',return_value=dict(commit='x',rows=[dict(runnable=True)])),\
             patch.object(driver,'setup'),patch.dict(driver.os.environ,SLURM_STEP_ID='batch'),patch.object(driver,'one') as execute:
            with self.assertRaises(ValueError):driver.execute(Path('unused'),0)
            execute.assert_not_called()
    def test_worker_preserves_code_identity_row(self):
        row=dict(index=0,runnable=True,code_sha256='x',request_seed=501)
        with patch.object(driver,'check',return_value=dict(commit='x',rows=[row])),patch.object(driver,'setup'),\
             patch.object(driver,'read',return_value={'job':'123'}),patch.dict(driver.os.environ,SLURM_STEP_ID='0',SLURM_JOB_ID='123'),\
             patch.object(driver,'one') as execute:
            driver.execute(Path('unused'),0);execute.assert_called_once_with(Path('unused'),row)

if __name__=='__main__':unittest.main()
