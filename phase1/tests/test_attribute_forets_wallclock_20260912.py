from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attribute_forets_wallclock_20260912 import task_partition, fee_partition, completion_receipt


class AttributionTests(unittest.TestCase):
    def test_recovery_requires_preserved_unread_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            original = dict(job='13156', status='failed_closed', readout_called=False)
            raw = json.dumps(original).encode()
            (root/'closeout-finished.json').write_bytes(raw)
            (root/'recovery-readout-finished.json').write_text(json.dumps(dict(job='13156', status='verified')))
            intent = dict(job='13156', mode='first_readout_after_accounting_connection_failure',
                          original_failure_sha256=hashlib.sha256(raw).hexdigest())
            (root/'recovery-readout-intent.json').write_text(json.dumps(intent))
            self.assertEqual(completion_receipt(root, 'recovery-readout-finished.json')['status'], 'verified')
            self.assertEqual((root/'closeout-finished.json').read_bytes(), raw)
            original['readout_called'] = True
            raw = json.dumps(original).encode()
            (root/'closeout-finished.json').write_bytes(raw)
            intent['original_failure_sha256'] = hashlib.sha256(raw).hexdigest()
            (root/'recovery-readout-intent.json').write_text(json.dumps(intent))
            with self.assertRaises(ValueError):
                completion_receipt(root, 'recovery-readout-finished.json')

    def test_receipt_cannot_bypass_failure_or_use_arbitrary_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root/'closeout-finished.json').write_text(json.dumps(dict(status='failed_closed')))
            with self.assertRaises(ValueError):
                completion_receipt(root, 'closeout-finished.json')
            with self.assertRaises(ValueError):
                completion_receipt(root, '../other.json')

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
