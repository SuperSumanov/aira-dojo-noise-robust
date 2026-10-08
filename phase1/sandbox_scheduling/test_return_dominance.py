import math
import unittest
from return_dominance import compare

class DominanceTests(unittest.TestCase):
    def test_count_dominance_not_program_dominance(self):
        r=compare({0:10,1:30},{0:15,1:5})
        self.assertTrue(r['count_dominates_all_deadlines'])
        self.assertFalse(r['every_program_no_later'])
        self.assertEqual(r['program_delay_seconds']['0'],5)

    def test_shorter_makespan_not_count_dominance(self):
        r=compare({0:10,1:30},{0:15,1:20})
        self.assertFalse(r['count_dominates_all_deadlines'])

    def test_missing_or_invalid_not_dropped(self):
        for a,b in (({0:1},{1:1}),({},{}),({0:math.nan},{0:1}),({0:-1},{0:1})):
            with self.assertRaises(ValueError):compare(a,b)

if __name__=='__main__':unittest.main()
