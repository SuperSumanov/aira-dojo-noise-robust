"""Small synthetic checks only; none represent measured experiment results."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from forets_paid_measurements_20260912 import read_batch, reduce_payload


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.bind = dict(task='leaf-classification', arm='uniform_random', step=1)
        call = dict(call_id=0, intent=dict(role='candidate', code='DO_NOT_EXPORT'), state='returned',
            task_wall_ns=2_000_000_000, execution_metadata=dict(exit_code_reported=0,
                timed_out_reported=False, exec_time_reported_seconds=1.5))
        self.payload = dict(schema=4, binding=dict(task=self.bind['task'], selection_policy=self.bind['arm'], step=1),
            phase='complete', candidates=[dict(node={'code':'DO_NOT_EXPORT'}, score=.99)], task_calls=[call])

    def test_count_and_no_private_payload(self):
        result = reduce_payload(self.payload, **self.bind)
        self.assertEqual(result['interpreter_exit_zero_calls'], 1)
        self.assertEqual(result['task_wall_seconds_observed'], 2)
        self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))
        self.assertNotIn('score', json.dumps(result))

    def test_timeout_debug_and_unresolved(self):
        c = copy.deepcopy(self.payload['task_calls'][0])
        c.update(call_id=1)
        c['intent']['role'] = 'debug'
        c['execution_metadata'].update(exit_code_reported=None, timed_out_reported=True)
        self.payload['task_calls'].append(c)
        c = copy.deepcopy(c)
        c.update(call_id=2, state='started', task_wall_ns=None, execution_metadata=None)
        self.payload['task_calls'].append(c)
        result = reduce_payload(self.payload, **self.bind)
        self.assertEqual(result['debug_task_calls'], 2)
        self.assertEqual(result['interpreter_timeout_calls'], 1)
        self.assertEqual(result['unresolved_task_calls'], 1)
        self.assertEqual(result['interpreter_exit_zero_calls'], 1)

    def test_wrong_task_or_arm_rejected(self):
        for field in ('task', 'arm', 'step'):
            binding = dict(self.bind, **{field:'wrong'})
            with self.assertRaises(ValueError):
                reduce_payload(self.payload, **binding)

    def test_invalid_time_rejected(self):
        self.payload['task_calls'][0]['task_wall_ns'] = True
        with self.assertRaises(ValueError):
            reduce_payload(self.payload, **self.bind)

    def test_readonly_database_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'batch-1.sqlite'
            raw = json.dumps(self.payload)
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE snapshot (id INTEGER, payload TEXT, sha256 TEXT)')
            db.execute('INSERT INTO snapshot VALUES (1,?,?)', (raw, hashlib.sha256(raw.encode()).hexdigest()))
            db.commit(); db.close()
            before = path.read_bytes()
            self.assertEqual(read_batch(path, **self.bind)['total_task_calls'], 1)
            self.assertEqual(before, path.read_bytes())
            db = sqlite3.connect(path)
            db.execute('UPDATE snapshot SET sha256=?', ('0'*64,))
            db.commit(); db.close()
            with self.assertRaises(ValueError):
                read_batch(path, **self.bind)


if __name__ == '__main__':
    unittest.main()
