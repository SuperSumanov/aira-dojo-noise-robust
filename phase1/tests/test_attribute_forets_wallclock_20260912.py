from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attribute_forets_wallclock_20260912 import task_partition, fee_partition


class AttributionTests(unittest.TestCase):
    def pool(self):
        return dict(schema=4, binding=dict(step=1), phase='executing',
                    llm_requests=[dict(state='returned'), dict(state='started')],
                    task_calls=[dict(call_id=0, intent=dict(role='candidate'), state='returned', task_wall_ns=2_000_000_000)])

    def test_measured_partition_not_critic_latency(self):
        result = task_partition([self.pool()], 10.)
        self.assertEqual(result['closed_task_call_seconds'], 2.)
        self.assertEqual(result['remainder_seconds'], 8.)
        self.assertEqual(result['remainder_kind'], 'non_task')
        self.assertEqual(result['closed_task_call_fraction'], .2)
        self.assertNotIn('ranking_latency_seconds', result)

    def test_unfinished_time_not_silently_other_work(self):
        pool = self.pool()
        pool['task_calls'].append(dict(call_id=1, intent=dict(role='debug'), state='started', task_wall_ns=None))
        result = task_partition([pool], 10.)
        self.assertEqual(result['remainder_kind'], 'non_task_plus_unfinished_task')
        self.assertEqual(result['unfinished_task_calls'], 1)

    def test_overlapping_or_duplicate_timings_fail(self):
        with self.assertRaises(ValueError):
            task_partition([self.pool()], 1.)
        with self.assertRaises(ValueError):
            task_partition([self.pool(), self.pool()], 10.)
        pool = self.pool()
        pool['task_calls'][0]['task_wall_ns'] = None
        with self.assertRaises(ValueError):
            task_partition([pool], 10.)

    def test_multiple_unfinished_tasks_are_impossible(self):
        first = self.pool()
        first['task_calls'][0].update(state='started', task_wall_ns=None)
        second = deepcopy(first)
        second['binding']['step'] = 2
        with self.assertRaises(ValueError):
            task_partition([first, second], 10.)

    def test_costs_exact_and_unknown_not_zero_charge(self):
        result = fee_partition('run', [('run-context-pool-1-order-0', 12, 12, 'settled'),
                                      ('other-id', None, 700, 'unresolved')])
        self.assertEqual(result['ranking']['settled_nano_usd'], 12)
        self.assertEqual(result['other']['unresolved'], 1)
        self.assertEqual(result['other']['responsibility_nano_usd'], 700)
        with self.assertRaises(ValueError):
            fee_partition('run', [('a', 12, 13, 'settled')])
        with self.assertRaises(ValueError):
            fee_partition('run', [('a', 0, 0, 'settled'), ('a', 0, 0, 'settled')])


if __name__ == '__main__':
    unittest.main()
