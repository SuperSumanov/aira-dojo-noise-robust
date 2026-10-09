import unittest
from live_pool_quality import summarize


def fixture():
    rows=[]
    for rep in (0,1):
        for arm in ('pipeline','share2'):
            for task in ('random-acts-of-pizza','spooky-author-identification'):
                for slot in (0,1):
                    rows.append(dict(index=len(rows),repeat=rep,arm=arm,task=task,
                        native_valid=True,native_score=.7 if slot==0 else (.5 if arm=='pipeline' else .6),
                        native_score_verified=True,complete=True))
    return rows


class PoolQualityTests(unittest.TestCase):
    def test_mean_gain_not_pool_best_gain(self):
        result=summarize(fixture())
        pizza=[r for r in result if r['task']=='random-acts-of-pizza']
        self.assertEqual([r['paired_oriented_best_difference'] for r in pizza],[0.,0.])
    def test_lower_is_better(self):
        result=[r for r in summarize(fixture()) if r['task']=='spooky-author-identification']
        for r in result:self.assertAlmostEqual(r['paired_oriented_best_difference'],-.1)
    def test_missing_not_imputed(self):
        rows=fixture();rows[0].update(complete=False)
        r=summarize(rows)[0]
        self.assertEqual(r['complete_valid_per_arm']['pipeline'],1)
        self.assertIsNone(r['paired_oriented_best_difference'])
    def test_bad_endpoint_rejected(self):
        for edit in (dict(native_score=float('nan')),dict(native_score_verified=False)):
            rows=fixture();rows[0].update(edit)
            with self.assertRaises(ValueError):summarize(rows)
    def test_denominator_and_group_rejected(self):
        with self.assertRaises(ValueError):summarize(fixture()[:-1])
        rows=fixture();rows[0]['task']='unknown'
        with self.assertRaises(ValueError):summarize(rows)


if __name__=='__main__':unittest.main()
