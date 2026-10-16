import unittest
from clock_parent_reference_20261016 import reference


class References(unittest.TestCase):
    def setUp(self):
        self.p = dict(source_episode=4, code_sha256='child', task='task')
        self.events = [dict(event='admitted', key='4:0', role='improve', parent='parent', run=4, time=1,
            snapshot=dict(archive={'task': {'parent': dict(metric=.5, order=0)}}, sign={'task': 1})),
            dict(event='parent_used', key='4:0', parent='parent', child='child', run=4, time=2)]

    def test_exact(self):
        r = reference(self.events, self.p)
        self.assertTrue(r['identified'])
        self.assertEqual(r['parent_score'], .5)

    def test_duplicate_not_chosen(self):
        self.assertFalse(reference(self.events + [self.events[-1]], self.p)['identified'])

    def test_missing_not_imputed(self):
        self.assertFalse(reference([], self.p)['identified'])

    def test_mismatch_fails(self):
        self.events[0]['parent'] = 'wrong'
        with self.assertRaises(AssertionError):
            reference(self.events, self.p)


if __name__ == '__main__':
    unittest.main()
