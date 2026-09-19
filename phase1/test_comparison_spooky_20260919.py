"""Synthetic CPU tests, not scoring any real labels."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import pandas as pd
import readout_comparison_spooky_pool_20260919 as reader
import run_comparison_spooky_pool_20260919 as driver


class SpookyTest(unittest.TestCase):
    def fixtures(self):
        y=pd.DataFrame(dict(id=['b','a'],EAP=[1,0],HPL=[0,1],MWS=[0,0]))
        p=pd.DataFrame(dict(id=['a','b'],MWS=[.1,.2],HPL=[.8,.1],EAP=[.1,.7]))
        return p,y
    def test_probability_alignment(self):
        p,y=self.fixtures()
        self.assertAlmostEqual(reader.numerical('spooky-author-identification',p,y),-(math.log(.8)+math.log(.7))/2)
    def test_duplicate_ids_fail(self):
        p,y=self.fixtures();p['id']=['a','a']
        with self.assertRaises(ValueError):reader.numerical('spooky-author-identification',p,y)
    def test_bad_probabilities_fail(self):
        p,y=self.fixtures();p.loc[0,'EAP']=float('nan')
        with self.assertRaises(ValueError):reader.numerical('spooky-author-identification',p,y)
    def test_wrong_columns_fail(self):
        p,y=self.fixtures();p=p.rename(columns={'MWS':'unknown'})
        with self.assertRaises(ValueError):reader.numerical('spooky-author-identification',p,y)
    def test_all_three_scheduled_once(self):
        p=dict(allocation_seconds=9000,rows=[dict(index=i,seed=i//6+1) for i in range(18)])
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as temp,patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer,\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',return_value=0),patch.object(driver.subprocess,'Popen',return_value=process) as popen:
            driver.coordinate(Path(temp))
            self.assertEqual([int(c.args[0][-1]) for c in popen.call_args_list],list(range(18)))
            self.assertEqual(writer.call_args.args[1]['attempted_seeds'],[1,2,3])
    def test_too_little_time_never_shrinks_program(self):
        p=dict(allocation_seconds=9000,rows=[])
        with tempfile.TemporaryDirectory() as temp,patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver,'prepared',return_value=p),patch.object(driver,'source_check'),\
             patch.object(driver,'read',return_value={'job':'123'}),patch.object(driver,'write') as writer,\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',side_effect=[0,1500,1500,1500]),patch.object(driver.subprocess,'Popen') as popen:
            driver.coordinate(Path(temp));popen.assert_not_called()
            self.assertEqual(writer.call_args.args[1]['unstarted_seeds'],[1,2,3])
    def test_remainder_not_implicitly_allowed(self):
        with self.assertRaises(ValueError):driver.prepare('a'*40,Path('/unused'))


if __name__=='__main__':unittest.main()
