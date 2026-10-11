import unittest
from pathlib import Path
import image_deadline_replication_20261012 as t
from image_deadline_replication_readout_20261012 import summarize,TASKS


class ReplicationTests(unittest.TestCase):
    def rows(self):
        return [dict(r,started=True,complete=True,valid=True,score=.8 if r['task']==TASKS[0] else .05,valid_returns=1,first_generation_failed=False) for r in t.schedule()]

    def test_matrix_budget(self):
        rows=t.schedule();self.assertEqual(len(rows),32);self.assertEqual(len({r['seed'] for r in rows}),16)
        self.assertEqual([rows[i]['arm'] for i in (0,8,16,24)],list(t.ORDER));self.assertEqual(t.CAP*6/3600,10.2)
        self.assertEqual((t.RUN,t.SLOT),(900,1500));self.assertTrue(all(r['seed'] not in range(212001,212009) for r in rows))
        for a in rows:
            b=[r for r in rows if r['seed']==a['seed'] and r['arm']!=a['arm']];self.assertEqual(len(b),1)
            for field in ('task','lane','repeat'):self.assertEqual(a[field],b[0][field])

    def test_driver(self):
        raw=Path(t.__file__).with_name('image_live_2plus4_20261011.py').read_text()
        # Donor's frozen driver has900s workers and only two pools.
        prior=t.donor.patch_driver(raw);result=t.patch_driver(prior);compile(result,'driver','exec')
        self.assertIn('for block in range(4):',result);self.assertIn('dict(configs=32,paired_equal=16,no_kernel=True',result)
        self.assertIn("'timeout=990'",result);self.assertIn('service GPU drift',result)
        with self.assertRaises(ValueError):t.patch_driver(result)

    def test_physical_lane(self):
        devices=['a','b','c','d']
        self.assertEqual([t.resolve_lane(devices,g) for g in ['c','a','d','b']],[2,0,3,1])
        with self.assertRaises(AssertionError):t.resolve_lane(devices,'other')
        with self.assertRaises(AssertionError):t.resolve_lane(['a']*4,'a')

    def test_tie_fails(self):
        x=summarize(self.rows());self.assertFalse(x['quality_signal_before_structure']);self.assertEqual(x['complete_run_quality_pairs'],16)

    def test_repeated_quality_pass(self):
        rows=self.rows()
        for r in rows:
            if r['arm']=='deadline600' and r['task']==TASKS[1]:r['score']-=.002
        x=summarize(rows);self.assertTrue(x['quality_signal_before_structure']);self.assertEqual(x['complete_pool_task_contrasts'],4)
        self.assertAlmostEqual(x['pool_delta_by_task'][TASKS[1]]['median'],.002)

    def test_coverage_only_fails(self):
        rows=self.rows()
        for r in rows:
            if r['arm']=='deadline240' and r['task']==TASKS[1]:r.update(complete=False,valid=False,score=None,valid_returns=0,first_generation_failed=True)
        x=summarize(rows);self.assertFalse(x['quality_signal_before_structure']);self.assertEqual(x['complete_pool_task_contrasts'],2)
        self.assertTrue(all(p['oriented_delta'] is None for p in x['pool_task_contrasts'] if p['task']==TASKS[1]))

    def test_one_repeat_not_enough(self):
        rows=self.rows()
        for r in rows:
            if r['arm']=='deadline600' and r['repeat']==0:r['score']+=.01 if r['task']==TASKS[0] else -.01
        self.assertFalse(summarize(rows)['quality_signal_before_structure'])

    def test_cross_task_regression_fails(self):
        rows=self.rows()
        for r in rows:
            if r['arm']=='deadline600':r['score']+=.01
        self.assertFalse(summarize(rows)['quality_signal_before_structure'])

    def test_missing_or_failed_score_not_selected(self):
        rows=self.rows();rows[8].update(complete=False,score=1.0)
        x=summarize(rows);p=next(p for p in x['pool_task_contrasts'] if p['repeat']==0 and p['task']==TASKS[0])
        self.assertEqual(p['best_native_endpoint']['deadline600'],.8);self.assertFalse(x['no_task_repeat_endpoint_loss'])

    def test_unstarted_cannot_win(self):
        rows=self.rows()
        for r in rows:
            if r['arm']=='deadline600' and r['task']==TASKS[0]:r['score']+=.01
        rows[0]['started']=False;self.assertFalse(summarize(rows)['quality_signal_before_structure'])

    def test_reject_duplicate(self):
        rows=self.rows();rows[-1]=dict(rows[0])
        with self.assertRaises(AssertionError):summarize(rows)


if __name__=='__main__':unittest.main()
