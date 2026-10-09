import unittest
from collections import Counter
from width_contract import schedule,may_admit,WIDTHS


class WidthContractTests(unittest.TestCase):
    def test_full_latin_square_same_workload_order(self):
        rows=schedule()
        self.assertEqual(len(rows),36)
        self.assertEqual(Counter(r['arm'] for r in rows),{a:12 for a in WIDTHS})
        for repeat in range(3):
            groups=[[r['program'] for r in rows if r['arm']==a and r['repeat']==repeat] for a in WIDTHS]
            self.assertEqual(groups[0],groups[1]);self.assertEqual(groups[1],groups[2])
        for order in range(3):
            self.assertEqual({rows[(r*3+order)*4]['arm'] for r in range(3)},set(WIDTHS))

    def test_no_execution_until_every_common_startup_finishes(self):
        self.assertFalse(may_admit(0,[0,1,2,3],{0,1,2},set(),set(),4))

    def test_fifo_and_work_conserving_completion_not_fixed_chains(self):
        indices=[0,1,2,3];all_ready=set(indices)
        self.assertTrue(may_admit(0,indices,all_ready,set(),set(),2))
        self.assertFalse(may_admit(2,indices,all_ready,{0},set(),2))
        self.assertTrue(may_admit(1,indices,all_ready,{0},set(),2))
        self.assertFalse(may_admit(2,indices,all_ready,{0,1},set(),2))
        # Faster slot1 frees capacity for slot2, without waiting for slot0.
        self.assertTrue(may_admit(2,indices,all_ready,{0,1},{1},2))

    def test_bad_states_rejected(self):
        for a,c,w in (({0,1},set(),1),(set(),{0},2),({5},set(),4)):
            with self.assertRaises(ValueError):may_admit(0,[0,1,2,3],{0,1,2,3},a,c,w)


if __name__=='__main__':unittest.main()
