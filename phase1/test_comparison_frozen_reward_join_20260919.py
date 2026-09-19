import unittest
from readout_comparison_frozen_reward_20260919 import join_rows

def fixture():
    prepared=[dict(task='synthetic',seed=i//6,run='r'+str(i//6),slot=i%6,node=str(i),code_sha256='a'*64,source_prepared_sha256='b'*64) for i in range(30)]
    predictions=[r|dict(reward=float(i),inference_seconds=.1) for i,r in enumerate(prepared)]
    labels=[r|dict(status='returned',valid=False,score=None,independent_score=None,original_selected=False,exit_code=1,timed_out=False) for r in prepared]
    return prepared,predictions,labels

class FrozenJoin(unittest.TestCase):
    def test_all_failed_complete_preserved(self):
        values=fixture();out=join_rows(*values);self.assertEqual(len(out),30);self.assertTrue(all(r['valid'] is False for r in out))
    def test_wrong_code_fails(self):
        values=fixture();values[1][0]['code_sha256']='c'*64
        with self.assertRaises(ValueError):join_rows(*values)
    def test_unknown_not_filtered(self):
        values=fixture();values[2][0]['status']='not_started'
        with self.assertRaises(ValueError):join_rows(*values)
    def test_missing_or_duplicate_fails(self):
        values=fixture();values[1][1]=values[1][0]
        with self.assertRaises(ValueError):join_rows(*values)

if __name__=='__main__':unittest.main()
