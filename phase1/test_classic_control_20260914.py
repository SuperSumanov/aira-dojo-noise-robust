import json
from pathlib import Path
import tempfile
import unittest
import classic_search_20260914 as c
import run_classic_control_20260914 as runner


class Tests(unittest.TestCase):
    def test_matrix(self):
        rows=runner.matrix()
        self.assertEqual(len(rows),8)
        self.assertEqual(len({(r['task'],r['seed']) for r in rows}),8)
        self.assertEqual({r['seed'] for r in rows},{42,43,44,45})

    def test_fixed_search_space(self):
        for seed in range(42,46):
            first=c.specifications(seed);second=c.specifications(seed)
            self.assertEqual(first,second);self.assertEqual(len(first),64)
            self.assertEqual({r['family'] for r in first},set(c.FAMILIES))
            self.assertEqual(first[0],c.specifications(0)[0])
        self.assertNotEqual(c.specifications(42)[1:],c.specifications(43)[1:])
        with self.assertRaises(ValueError):c.specifications(42,65)

    def test_metric_orientation_strict(self):
        self.assertTrue(c.better(.3,.4,'leaf-classification'))
        self.assertFalse(c.better(.4,.3,'leaf-classification'))
        self.assertTrue(c.better(.9,.8,'spaceship-titanic'))
        self.assertFalse(c.better(.8,.8,'spaceship-titanic'))

    def test_deadline_exact_boundary_rejected_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            a=c.publish(p,0,b'a',{},deadline_ns=10,clock=lambda:9)
            b=c.publish(p,1,b'b',{},deadline_ns=10,clock=lambda:10)
            self.assertTrue(a['eligible']);self.assertFalse(b['eligible'])
            self.assertEqual(a['sha256'],c.digest(b'a'))
            with self.assertRaises(FileExistsError):c.publish(p,0,b'x',{},deadline_ns=10,clock=lambda:9)

    def test_no_api_or_grader_in_search(self):
        text=Path(c.__file__).read_text()
        for s in ('requests.','httpx.','evaluate_submission','prepared/private','/test_labels','load_dotenv'):
            self.assertNotIn(s,text)
        self.assertIn('finally:',text);self.assertIn('start_new_session=True',text)


if __name__=='__main__':unittest.main()
