from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pipeline_trial as p
from lifecycle_pilot import write,read


class PipelineTests(unittest.TestCase):
    def test_matrix_and_fifo(self):
        rows=p.schedule()
        self.assertEqual([r['index'] for r in rows],list(range(36)))
        self.assertEqual(Counter((r['program'],r['arm']) for r in rows),Counter({(i,a):3 for i in p.PROGRAMS for a in p.ARMS}))
        for rep in range(3):
            orders=[[r['program'] for r in rows if r['repeat']==rep and r['arm']==arm] for arm in p.ARMS]
            self.assertTrue(all(o==orders[0] for o in orders))

    def test_dependency_stays_inside_block(self):
        for r in p.schedule():
            previous=p.predecessor(r)
            if previous is not None:
                self.assertEqual(previous//4,r['index']//4)
                self.assertEqual(previous,r['index']-1)
            else:self.assertTrue(r['arm']!='pipeline' or r['position']==0)

    def test_successful_predecessor_and_failure(self):
        row=p.schedule()[5]
        self.assertEqual(row['arm'],'pipeline')
        for rc in (0,1):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp,patch.object(p,'R',Path(tmp)):
                prior=p.R/'episode-4';prior.mkdir();write(prior/'closed.json',dict(returncode=rc));(prior/'closed.ready').touch()
                ep=p.R/'episode-5';ep.mkdir()
                if rc:
                    with self.assertRaises(ValueError):p.wait_turn(row,ep)
                    self.assertFalse((ep/'execution_admitted.json').exists())
                else:
                    p.wait_turn(row,ep)
                    self.assertLessEqual(read(ep/'prelude_ready.json')['time'],read(ep/'execution_admitted.json')['time'])

    def test_serial_has_no_predecessor_wait(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p.wait_turn(p.schedule()[1],Path(tmp))
            self.assertTrue((Path(tmp)/'execution_admitted.json').exists())

    def test_partial_closed_json_without_marker_not_read(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp,patch.object(p,'R',Path(tmp)):
            prior=p.R/'episode-4';prior.mkdir();(prior/'closed.json').write_text('{')
            ep=p.R/'episode-5';ep.mkdir()
            with patch.object(p.time,'time',side_effect=[0,181]):
                with self.assertRaises(TimeoutError):p.wait_turn(p.schedule()[5],ep)


if __name__=='__main__':unittest.main()
