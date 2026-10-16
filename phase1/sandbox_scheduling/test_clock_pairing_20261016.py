import unittest
from clock_pairing_20261016 import groups,schedule,require_ready,InfrastructureReadinessError,CAP,BLOCK


class PairingTests(unittest.TestCase):
    def test_full_denominator(self):
        self.assertEqual(sorted(i for b in range(4) for g in groups(b) for i in g),list(range(16)))

    def test_same_program_multiset_and_disjoint_cpu_port(self):
        for b in range(4):
            self.assertEqual(sorted(i%4 for g in groups(b) for i in g),[0,1,2,3])
            for x,y in groups(b):self.assertNotEqual(x%2,y%2)

    def test_intervention_is_task_matching_only(self):
        for b in range(4):
            for x,y in groups(b):self.assertEqual((x%4)//2==(y%4)//2,b in (0,3))

    def test_reverse_order(self):
        self.assertEqual([[x%4 for x in g] for g in groups(3)],[[3,2],[1,0]])
        self.assertEqual([[x%4 for x in g] for g in groups(2)],[[1,2],[3,0]])

    def test_fixed_reservations(self):
        self.assertEqual([r['mode'] for r in schedule()[::4]],['within','cross','cross','within'])
        self.assertLessEqual(4*BLOCK+120,CAP)

    def test_readiness_fatal_not_candidate_timeout(self):
        with self.assertRaises(InfrastructureReadinessError):require_ready(lambda:False)
        with self.assertRaises(InfrastructureReadinessError):require_ready(lambda:None)
        self.assertIs(require_ready(lambda:True),True)

    def test_quality_gate_and_missing_denominator(self):
        from clock_pairing_readout_20261016 import quality
        rows=[dict(r,complete=True,valid=True,score=(.8 if r['program']<2 else .02)-(.002 if r['program']>=2 and r['mode']=='cross' else 0)) for r in schedule()]
        self.assertTrue(quality(rows)[2])
        rows[0]['valid']=False
        self.assertFalse(quality(rows)[2])
        self.assertFalse(quality(rows)[0][0]['complete'])

    def test_one_repeat_cannot_rescue_gate(self):
        from clock_pairing_readout_20261016 import quality
        rows=[dict(r,complete=True,valid=True,score=(.8 if r['program']<2 else .02)-(.002 if r['program']>=2 and r['block']==1 else 0)) for r in schedule()]
        self.assertFalse(quality(rows)[2])


if __name__=='__main__':unittest.main()
