"""Outcome-blind readout edge cases; no actual experiment data."""
import importlib.util,unittest,tempfile,json,hashlib
from unittest.mock import patch
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
    def test_default_still_requires_original_all_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'plan.json').write_text('{}')
            with patch.object(m,'ROOT',root),patch.object(m,'PLAN_SHA',m.sha(root/'plan.json')):
                with self.assertRaisesRegex(ValueError,'all-closed'):m.terminal_gate()
    def test_aborted_requires_exact_certificate_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'plan.json').write_text('{}');(root/'cert.json').write_text('{}')
            with patch.object(m,'ROOT',root),patch.object(m,'PLAN_SHA',m.sha(root/'plan.json')):
                with self.assertRaisesRegex(ValueError,'unbound'):m.terminal_gate(root/'cert.json',None)
                with self.assertRaisesRegex(ValueError,'unbound'):m.terminal_gate(root/'cert.json','0'*64)
    def test_aborted_artifact_drift_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'plan.json').write_text('{}');(root/'event.json').write_text('changed')
            h=m.sha(root/'plan.json')
            c=dict(status='INDEPENDENT_TERMINAL_VERIFIED_ORIGINAL_PRIMARY_FAILED',plan_sha256=h,original_primary_gate_passed=False,missing_original_closed=[10],stable_censuses=2,artifact_bindings={'event.json':'0'*64})
            (root/'cert.json').write_text(json.dumps(c))
            with patch.object(m,'ROOT',root),patch.object(m,'PLAN_SHA',h):
                with self.assertRaises(AssertionError):m.terminal_gate(root/'cert.json',m.sha(root/'cert.json'))
    def test_primary_status_cannot_be_forged_by_aborted_certificate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'plan.json').write_text('{}');h=m.sha(root/'plan.json')
            c=dict(status='INDEPENDENT_TERMINAL_VERIFIED_ORIGINAL_PRIMARY_FAILED',plan_sha256=h,original_primary_gate_passed=True)
            (root/'cert.json').write_text(json.dumps(c))
            with patch.object(m,'ROOT',root),patch.object(m,'PLAN_SHA',h):
                with self.assertRaises(AssertionError):m.terminal_gate(root/'cert.json',m.sha(root/'cert.json'))
if __name__=='__main__':unittest.main()
