"""Outcome-blind readout edge cases; no actual experiment data."""
import importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'scripts/task_feedback_evidence_edit_readout_20261002.py'
sp=importlib.util.spec_from_file_location('readout',P);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Cases(unittest.TestCase):
    def test_completed(self):self.assertEqual(m.finish_classification({'status':'completed'},{'worker_deadline_reached':False},False),'completed')
    def test_attested_deadline(self):self.assertEqual(m.finish_classification(None,{'worker_deadline_reached':True},False),'budget_exhausted')
    def test_exception_not_overwritten(self):self.assertEqual(m.finish_classification(None,{'worker_deadline_reached':True},True),'unknown')
    def test_no_attestation(self):self.assertEqual(m.finish_classification(None,{},False),'unknown')
    def test_false_deadline(self):self.assertEqual(m.finish_classification(None,{'worker_deadline_reached':False},False),'unknown')
    def test_explicit_unknown(self):self.assertEqual(m.finish_classification({'status':'unknown'},{'worker_deadline_reached':True},False),'unknown')
    def test_stats_keep_missing(self):
        v=m.stats([0,None,2]);self.assertEqual(v['values'],[0,None,2]);self.assertEqual(v['n'],2);self.assertEqual(v['median'],1);self.assertEqual(v['sample_variance'],2)
if __name__=='__main__':unittest.main()
