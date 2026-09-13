from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from inspect_reference_parent_distance_20260913 import scores,tokens


class DistanceTests(unittest.TestCase):
    def test_comments_whitespace_ignored(self):
        self.assertEqual(tokens('x=1\n'),tokens('# foo\nx = 1\n'))
        self.assertEqual(scores('x=1\n',['# foo\nx = 1\n'])[0],[0.])
    def test_names_and_literals_retained(self):
        self.assertGreater(scores('x=1\n',['y=2\n'])[0][0],0)
    def test_malformed_preserved(self):
        distance,malformed=scores('x=1\n',['x=(\n'])
        self.assertEqual(distance,[1.]);self.assertEqual(malformed,[True])


if __name__=='__main__':unittest.main()
