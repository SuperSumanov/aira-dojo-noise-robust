import copy,unittest
from pathlib import Path
import image_generation_deadline_20261011 as t
from image_deadline_readout_20261011 import summarize


class DeadlineTests(unittest.TestCase):
    def test_matrix(self):
        rows=t.schedule();self.assertEqual(len(rows),16)
        self.assertEqual({r['seed'] for r in rows},set(range(212001,212009)))
        for a,b in zip(rows[:8],rows[8:]):
            for field in ('task','seed','lane','slot'):self.assertEqual(a[field],b[field])
        self.assertEqual([rows[i]['arm'] for i in (0,8)],['deadline600','deadline240'])

    def test_budget(self):
        self.assertEqual(t.CAP*6/3600,5.2)
        self.assertEqual(t.RUN,900);self.assertEqual(t.SLOT,1500)
        self.assertGreaterEqual(t.CAP,2*t.SLOT+60)

    def test_patch_driver(self):
        raw=Path(t.__file__).with_name('image_live_2plus4_20261011.py').read_text()
        patched=t.patch_driver(raw);compile(patched,'driver','exec')
        self.assertIn("TIME_LIMIT='15 minutes',TIME_LIMIT_SECS='900'",patched)
        self.assertIn('for block in range(2):',patched)
        self.assertIn('dict(planned=16,attempted_blocks=attempted',patched)
        self.assertIn("limit=1 if rows[0]['arm']=='fifo1' else 2",patched)
        with self.assertRaises(ValueError):t.patch_driver(patched)

    def test_timeout_patch(self):
        raw="assert 0 < timeout_seconds <= 300\nraise ValueError('bounded request timeout must be in (0, 300] seconds')\n"
        new=t.patch_timeout_guard(raw);compile(new,'timeout','exec')
        self.assertIn('<= 600',new);self.assertNotIn('300',new)
        with self.assertRaises(ValueError):t.patch_timeout_guard(new)

    def rows(self):
        return [dict(row,started=True,complete=True,valid=True,score=.8 if row['task']==t.c.trial.TASKS[0] else .2,
            first_generation_failed=False,valid_returns=1) for row in t.schedule()]

    def test_no_signal_from_equal(self):
        result=summarize(self.rows());self.assertFalse(result['screen_positive_before_structure'])
        self.assertEqual(len(result['pairs']),8)

    def test_coverage_signal_not_quality_claim(self):
        rows=self.rows()
        rows[8].update(complete=False,valid=False,score=None,first_generation_failed=True,valid_returns=0)
        result=summarize(rows);self.assertTrue(result['screen_positive_before_structure'])
        self.assertEqual(result['assigned'],16);self.assertIsNone(result['pairs'][0]['oriented_delta'])
        self.assertEqual(result['pairs'][0]['endpoint_coverage_delta'],1)

    def test_unstarted_is_not_failed_control(self):
        rows=self.rows();rows[8].update(started=False,complete=False,valid=False,score=None,first_generation_failed=True,valid_returns=0)
        result=summarize(rows);self.assertFalse(result['screen_positive_before_structure'])
        self.assertIsNone(result['pairs'][0]['endpoint_coverage_delta'])

    def test_task_regression_rejects(self):
        rows=self.rows()
        for i in (8,10):rows[i].update(complete=False,valid=False,score=None,first_generation_failed=True,valid_returns=0)
        rows[1].update(valid=False,score=None,valid_returns=0)
        self.assertFalse(summarize(rows)['screen_positive_before_structure'])

    def test_score_orientation(self):
        rows=self.rows();rows[0]['score']+=.02;rows[1]['score']-=.02
        result=summarize(rows)
        for pair in result['pairs'][:2]:self.assertAlmostEqual(pair['oriented_delta'],.02)


if __name__=='__main__':unittest.main()
