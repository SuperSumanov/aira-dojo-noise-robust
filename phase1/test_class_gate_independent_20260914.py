"""Synthetic cross-check, no access to live results."""
import random,unittest
from readout_class_gate_20260914 import comparisons,secondary_contrasts
from verify_class_gate_e2e_20260914 import verify_effects,verify_secondary
from test_readout_class_gate_20260914 import rows
class Independent(unittest.TestCase):
    def test_synthetic_states(self):
        rng=random.Random(20260914)
        for _ in range(2000):
            rr=rows()
            for r in rr:
                r['technical_eligible']=rng.random()>.05
                for e in ('action','iteration'):
                    r[e+'_valid']=rng.random()>.15
                    r[e+'_score']=rng.choice([.3,.4,.5,.6]) if r[e+'_valid'] else None
            main=comparisons(rr);pairs,gate=verify_effects(rr)
            self.assertEqual(main['pairs'],pairs);self.assertEqual(main['investment_gate'],gate)
            verify_secondary(rr,secondary_contrasts(rr))
    def test_no_cross_task_cancellation(self):
        rr=rows()
        for r in rr:
            if r['arm']=='class_gate':r['action_score']=.1
        self.assertFalse(verify_effects(rr)[1])
    def test_missing_seed_rejected(self):
        rr=rows();rr.pop()
        with self.assertRaises(ValueError):verify_effects(rr)
if __name__=='__main__':unittest.main()
