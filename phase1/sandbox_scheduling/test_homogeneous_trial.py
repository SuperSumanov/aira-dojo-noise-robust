from collections import Counter
import unittest
from homogeneous_trial import schedule


class HomogeneousTests(unittest.TestCase):
    def test_denominator_and_replica_balance(self):
        rows=schedule()
        self.assertEqual([r['index'] for r in rows],list(range(24)))
        self.assertEqual(Counter((r['program'],r['arm'],r['replica']) for r in rows),
                         Counter({(p,a,k):3 for p in (0,1) for a in ('serial','share2') for k in (0,1)}))

    def test_block_is_one_program_two_replicas(self):
        rows=schedule()
        for i in range(0,24,2):
            a,b=rows[i:i+2]
            self.assertEqual((a['program'],a['arm'],a['repeat']),(b['program'],b['arm'],b['repeat']))
            self.assertEqual((a['replica'],b['replica']),(0,1))

    def test_serial_qualification_precedes_sharing_for_each_task(self):
        rows=schedule()
        for program in (0,1):
            first=[r for r in rows if r['program']==program][:2]
            self.assertTrue(all(r['repeat']==0 and r['arm']=='serial' for r in first))

    def test_both_task_and_arm_order_reversed_in_middle_restart(self):
        rows=schedule()
        self.assertEqual([rows[i]['program'] for i in (0,8,16)],[0,1,0])
        self.assertEqual([rows[i]['arm'] for i in (0,8,16)],['serial','share2','serial'])


if __name__=='__main__':unittest.main()
