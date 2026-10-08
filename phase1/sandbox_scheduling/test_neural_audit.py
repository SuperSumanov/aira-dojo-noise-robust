import unittest
from audit_neural_result import intervals_summary, compare


class AuditTests(unittest.TestCase):
    def test_overlap_includes_empty_startup(self):
        self.assertEqual(intervals_summary([(2,5),(4,8)],0,10),dict(union=6,overlap=1,outside=4))

    def test_empty_and_adjacent(self):
        self.assertEqual(intervals_summary([],0,10),dict(union=0,overlap=0,outside=10))
        self.assertEqual(intervals_summary([(1,3),(3,5)],0,6),dict(union=4,overlap=0,outside=2))

    def test_bad_interval_rejected(self):
        for span in ((-1,2),(3,2),(2,11)):
            with self.assertRaises(ValueError):
                intervals_summary([span],0,10)

    def test_difference_and_identity(self):
        a=(['id','x'],{'a':(1.,),'b':(2.,)})
        b=(['id','x'],{'b':(3.,),'a':(1.,)})
        self.assertEqual(compare(a,b),dict(max_abs=1.,values=2,different_values=1))
        with self.assertRaises(ValueError):
            compare(a,(['id','x'],{'a':(1.,)}))

    def test_width_cannot_be_truncated_by_zip(self):
        with self.assertRaises(ValueError):
            compare((['id','x'],{'a':(1.,2.)}),(['id','x'],{'a':(1.,)}))


if __name__=='__main__':
    unittest.main()
