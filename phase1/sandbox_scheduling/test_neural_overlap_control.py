from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import neural_overlap_control as c
from lifecycle_pilot import read,write


class OverlapTests(unittest.TestCase):
    def test_fixed_matrix_and_order(self):
        rows=c.schedule()
        self.assertEqual([r['index'] for r in rows],list(range(12)))
        self.assertEqual(Counter((r['program'],r['arm']) for r in rows),
                         Counter({(p,a):3 for p in (0,1) for a in ('pipeline','share2')}))
        for rep in range(3):
            self.assertEqual([r['program'] for r in rows if r['repeat']==rep and r['arm']=='pipeline'],
                             [r['program'] for r in rows if r['repeat']==rep and r['arm']=='share2'])
        for row in rows:
            prev=c.predecessor(row)
            if prev is not None:self.assertEqual(prev//2,row['index']//2)

    def test_timestamp_is_after_barrier(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp,patch.object(c,'R',Path(tmp)):
            prior=c.R/'episode-0';prior.mkdir()
            write(prior/'closed.json',dict(returncode=0,end=9))
            (prior/'closed.ready').touch()
            ep=c.R/'episode-1';ep.mkdir()
            with patch.object(c.time,'time',side_effect=[10,11,12]):
                c.boundary_write(ep/'candidate_started.json',dict(time=1))
            self.assertEqual(read(ep/'prelude_ready.json')['time'],10)
            self.assertEqual(read(ep/'execution_admitted.json')['time'],11)
            self.assertEqual(read(ep/'candidate_started.json')['time'],12)

    def test_partial_or_failed_predecessor_does_not_admit(self):
        for partial in (True,False):
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp,patch.object(c,'R',Path(tmp)):
                prior=c.R/'episode-0';prior.mkdir();ep=c.R/'episode-1';ep.mkdir()
                if partial:
                    (prior/'closed.json').write_text('{')
                    with patch.object(c.time,'time',side_effect=[0,451]),self.assertRaises(TimeoutError):
                        c.wait_turn(c.schedule()[1],ep)
                else:
                    write(prior/'closed.json',dict(returncode=1));(prior/'closed.ready').touch()
                    with self.assertRaises(ValueError):c.wait_turn(c.schedule()[1],ep)
                self.assertFalse((ep/'execution_admitted.json').exists())

    def test_marker_after_closed_json_and_no_warmup_gate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp,patch.object(c,'R',Path(tmp)):
            ep=c.R/'episode-36';ep.mkdir()
            c.boundary_write(ep/'candidate_started.json',dict(time=1))
            self.assertFalse((ep/'execution_admitted.json').exists())
            c.boundary_write(ep/'closed.json',dict(returncode=0))
            self.assertTrue((ep/'closed.ready').exists())
            self.assertEqual(read(ep/'closed.json')['returncode'],0)
            c.boundary_write(c.R/'closed.json',dict(completed=12))
            self.assertFalse((c.R/'closed.ready').exists())

    def test_scope_without_runtime(self):
        rfields={k:getattr(c.r,k) for k in ('R','NAME','NODE','CAP','JOBNAME','FIXTURE_BUILDER','PLAN_MUTATOR','EXTRA_FILES','QUESTION')}
        nfields={k:getattr(c.n,k) for k in ('schedule','write')}
        try:
            with patch.object(c.r,'configure',side_effect=AssertionError('must not load runtime')):c.set_scope()
            self.assertEqual(c.r.CAP,2700)
            plan={};c.mutate_plan(plan)
            self.assertEqual(plan['schedule'],c.schedule())
            self.assertEqual(plan['reference_policy'],'pipeline')
            self.assertTrue(plan['queue_wait_is_inside_unchanged_worker_deadline'])
            self.assertEqual(plan['worker_hard_seconds'],550)
        finally:
            for k,v in rfields.items():setattr(c.r,k,v)
            for k,v in nfields.items():setattr(c.n,k,v)


if __name__=='__main__':unittest.main()
