import unittest
from live_twochild_alignment import align, safe_excess, closed_rows

A, B, C = ('a'*64, 'b'*64, 'c'*64)


class AlignmentTests(unittest.TestCase):
    def test_separate_primary_table(self):
        rows=[dict(index=i) for i in range(16)]
        self.assertEqual(closed_rows(dict(assigned=16),rows),rows)
    def test_reject_summary_as_rows_and_duplicates(self):
        with self.assertRaises(ValueError):closed_rows(dict(assigned=16),dict(assigned=16))
        with self.assertRaises(ValueError):closed_rows(dict(assigned=16),[dict(index=0)]*16)
    def test_exact_repeated_hashes(self):
        self.assertEqual(align([A,A],[A,A])['status'],'exact_sequence')
    def test_unique_suffix_and_interior(self):
        self.assertEqual(align([A,B],[A,B,C])['possible_unrecorded_positions'],[2])
        self.assertEqual(align([A,C],[A,B,C])['possible_unrecorded_positions'],[1])
    def test_ambiguous_not_greedy(self):
        value=align([A],[A,A])
        self.assertEqual(value['status'],'ambiguous_excess_return')
        self.assertEqual(value['possible_unrecorded_positions'],[0,1])
    def test_unknown_difference_stays_unknown(self):
        for left,right in (([A],[B]),([A],[A,B,C]),([A,B],[A,A,C])):
            self.assertEqual(align(left,right)['status'],'unresolved_mismatch')
    def test_event_summary_not_semantic_claim(self):
        cs=[dict(elapsed_seconds=40,valid=False)]
        events=[dict(event='generation_started',elapsed=41),dict(event='generation_returned',elapsed=80,success=False),
                dict(event='generation_returned',elapsed=110,success=True)]
        row=safe_excess(cs,events,[0],100)[0]
        self.assertFalse(row['externally_valid'])
        self.assertEqual(row['later_failed_generation_returns'],1)
        self.assertEqual(row['later_successful_generation_returns'],0)
        self.assertEqual(row['later_candidate_operations'],0)
    def test_reject_bad_metadata(self):
        with self.assertRaises(ValueError):align(['raw content'],[A])
        with self.assertRaises(ValueError):safe_excess([dict(elapsed_seconds=float('nan'),valid=True)],[],[0],100)


if __name__ == '__main__':unittest.main()
