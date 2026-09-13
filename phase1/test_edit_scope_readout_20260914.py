"""Frozen-reader arithmetic tests before any new outcome is opened."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE/'releases/forets-edit-scope-tools-20260914'))
import readout_edit_scope_20260914 as r


def fixture():
    return [dict(task=t,seed=s,arm=a,technical_eligible=True,action_valid=True,iteration_valid=True,
        action_score=.5,iteration_score=.5,api_cost_usd=.01) for t in r.TASKS for s in r.SEEDS for a in r.ARMS]


class Tests(unittest.TestCase):
    def test_all_ties_and_groups(self):
        out=r.paired_effects(fixture())
        self.assertEqual(len(out['pairs']),16)
        self.assertTrue(all(g['quality_comparable']==4 and g['ties']==4 for g in out['groups']))

    def test_orientation(self):
        rows=fixture()
        for row in rows:
            if row['arm']=='model_module':
                row['action_score']=.4 if row['task']=='leaf-classification' else .6
        out=r.paired_effects(rows)
        self.assertTrue(all(p['module_oriented_gain']>0 for p in out['pairs'] if p['endpoint']=='action'))

    def test_missing_not_zero_or_quality_loss(self):
        rows=fixture();rows[0].update(technical_eligible=False,action_valid=False,action_score=None)
        pairs=r.paired_effects(rows)['pairs']
        affected=[p for p in pairs if p['task']==rows[0]['task'] and p['seed']==rows[0]['seed']]
        self.assertTrue(all(p['module_oriented_gain'] is None for p in affected))

    def test_no_dropped_or_duplicate_slots(self):
        for rows in (fixture()[:-1],fixture()[:-1]+[fixture()[0]]):
            with self.assertRaises(ValueError):r.paired_effects(rows)

    def test_hour_conversion_unchanged(self):
        source=(HERE/'releases/forets-edit-scope-tools-20260914/readout_edit_scope_core_20260914.py').read_text()
        self.assertIn('allocation_gpu_hours=seconds/3600',source)
        self.assertNotIn('31200',source)


if __name__=='__main__':unittest.main()
