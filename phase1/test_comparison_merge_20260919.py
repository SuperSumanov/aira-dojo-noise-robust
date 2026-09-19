import copy,unittest
from merge_comparison_pool_20260919 import merge


class MergeTest(unittest.TestCase):
    def data(self):
        rows=[dict(index=i,seed=i//6+1,slot=i%6,task='leaf',run='r'+str(i//6),node=str(i),original_selected=i%6<2,
                   raw_code_sha256=str(i),code_sha256=str(i),status='returned',valid=False,score=None) for i in range(18)]
        first=dict(job='1',allocation_state='COMPLETED',allocation_seconds=6,allocated_gpus=6,gpu_hours=.01,
                   prepared_sha256='a',api_calls=0,rows=copy.deepcopy(rows))
        second=dict(first,job='2',prepared_sha256='b',rows=copy.deepcopy(rows))
        for i in range(18):
            ignored=second['rows'][i] if i<12 else first['rows'][i]
            ignored.update(status='not_started',valid=None)
        return first,second

    def test_keeps_fixed_seeds(self):
        result=merge(*self.data())
        self.assertEqual([r['replay_job'] for r in result['rows']],['1']*12+['2']*6)
        self.assertEqual(result['program_failure'],18);self.assertEqual(result['unknown'],0)

    def test_rejects_duplicate_attempt(self):
        a,b=self.data();a['rows'][12]['status']='infrastructure_unknown'
        with self.assertRaises(ValueError):merge(a,b)

    def test_rejects_identity_drift(self):
        a,b=self.data();b['rows'][12]['code_sha256']='changed'
        with self.assertRaises(ValueError):merge(a,b)

    def test_preserves_unknown(self):
        a,b=self.data();b['rows'][12].update(status='infrastructure_unknown',valid=None)
        result=merge(a,b)
        self.assertEqual(result['unknown'],1);self.assertEqual(result['pools'][2]['status'],'UNKNOWN_NO_EFFECT_CLAIM')

if __name__=='__main__':unittest.main()
