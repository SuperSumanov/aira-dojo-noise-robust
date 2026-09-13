import unittest
import scope_preservation_effects_20260914 as e


def fixture():
    rows=[]
    for t in e.TASKS:
        for s in e.SEEDS:
            for index,a in enumerate(e.ARMS):
                score=.5+(-1 if t==e.TASKS[0] else 1)*index*.1
                rows.append(dict(task=t,seed=s,arm=a,technical_eligible=True,
                    action_valid=True,action_score=score,iteration_valid=True,iteration_score=score,api_cost_usd=.01*index))
    return rows


class Tests(unittest.TestCase):
    def test_all_contrasts_and_both_endpoints(self):
        out=e.effects(fixture());self.assertEqual(len(out['pairs']),24);self.assertEqual(len(out['groups']),12)
        for g in out['groups']:self.assertEqual((g['wins'],g['losses']),(2,0))
    def test_missing_arm_only_affects_its_contrasts(self):
        rows=fixture();rows[1]['technical_eligible']=False
        out=e.effects(rows)
        self.assertEqual(sum(p['quality_comparable'] for p in out['pairs']),20)
        self.assertTrue(all(p['quality_comparable'] for p in out['pairs'] if p['control']=='whole_program' and p['treatment']=='model_module'))
    def test_secondary_not_used_for_primary(self):
        rows=fixture()
        for r in rows:r['iteration_score']=1-r['action_score']
        out=e.effects(rows)
        self.assertTrue(all(g['wins']==2 for g in out['groups'] if g['endpoint']=='action'))
        self.assertTrue(all(g['losses']==2 for g in out['groups'] if g['endpoint']=='iteration'))
    def test_full_denominator_and_validity(self):
        with self.assertRaises(ValueError):e.effects(fixture()[:-1])
        rows=fixture();rows[0]['action_valid']=False
        with self.assertRaises(ValueError):e.effects(rows)


if __name__=='__main__':unittest.main()
