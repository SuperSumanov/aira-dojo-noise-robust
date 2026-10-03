"""Synthetic readout edge cases; no experiment files or scores are loaded."""
import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).parents[1]/'scripts/opportunity_information_readout_20261003.py'
spec = importlib.util.spec_from_file_location('information_readout_tested', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def fixture():
    return [dict(task=t, seed=s, arm=a, initial=.5, initial_sha256=f'{t}-{s}',
                 closed=True, gain=g, improved_candidates=int(g>0))
            for t in ('auc_task', 'loss_task') for s in (1,2)
            for a,g in (('A',0.),('B',.1),('C',.2))]

class ReadoutTests(unittest.TestCase):
    def test_qualified(self):
        pairs, stats, gate = m.compare(fixture())
        self.assertTrue(gate); self.assertEqual(len(pairs), 4)
        self.assertTrue(all(abs(p['C_minus_B']-.1)<1e-12 for p in pairs))

    def test_missing_initial_is_unknown(self):
        r=fixture(); r[0]['initial']=None; r[0]['gain']=None
        pairs,_,gate=m.compare(r)
        self.assertFalse(gate); self.assertFalse(pairs[0]['comparable'])
        self.assertIsNone(pairs[0]['B_minus_A'])

    def test_same_score_different_prediction_is_incomparable(self):
        r=fixture(); r[1]['initial_sha256']='different'
        self.assertFalse(m.compare(r)[0][0]['comparable'])
        self.assertFalse(m.compare(r)[2])

    def test_same_hash_different_score_is_incomparable(self):
        r=fixture(); r[1]['initial']=.51
        self.assertFalse(m.compare(r)[0][0]['comparable'])

    def test_unclosed_is_incomparable(self):
        r=fixture(); r[1]['closed']=False
        self.assertFalse(m.compare(r)[2])

    def test_one_bad_seed_rejects_positive_median(self):
        r=fixture(); r[0]['gain']=.2; r[4]['gain']=.9
        self.assertFalse(m.compare(r)[2])

    def test_no_new_valid_improvement_rejects_gate(self):
        r=fixture()
        for x in r:
            if x['arm']=='B': x['improved_candidates']=0
        self.assertFalse(m.compare(r)[2])

    def test_keep_parent_failure_after_valid_initial(self):
        r=fixture()
        for x in r:
            if x['arm']=='B': x['gain']=0.; x['improved_candidates']=0
        pairs,_,gate=m.compare(r)
        self.assertTrue(all(p['comparable'] for p in pairs)); self.assertFalse(gate)
        self.assertTrue(all(p['B_minus_A']==0 for p in pairs))

if __name__=='__main__': unittest.main()
