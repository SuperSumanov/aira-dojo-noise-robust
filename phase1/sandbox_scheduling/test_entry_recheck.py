import unittest
from dataclasses import dataclass
from pathlib import Path
import entry_recheck as r
from lifecycle_pilot import sha


class RecheckTests(unittest.TestCase):
    def test_exactly_original_failed_targets_once(self):
        rows=r.schedule()
        self.assertEqual(len(rows),2)
        self.assertEqual([v['index'] for v in rows],[0,1])
        self.assertEqual([v['program'] for v in rows],[0,4])
        self.assertEqual([v['original_index'] for v in rows],[0,4])
        self.assertEqual({v['repeat'] for v in rows},{0})

    def test_unchanged_worker(self):
        self.assertEqual(sha(Path(__file__).with_name('throughput_pilot.py')),r.DONOR_PILOT)
        self.assertNotEqual(r.R,r.D)
        self.assertEqual(r.R.name,'scheduling-entry-20261008-v2')
        self.assertNotEqual(r.R.name,'scheduling-entry-20261007-v1')

    def test_frozen_legacy_result_has_no_phase(self):
        @dataclass
        class LegacyResult:
            term_out: list
            exec_time: float
            exit_code: int | None = None
            eval_return: object = None
            timed_out: bool = False
        result=LegacyResult(['ok'],1.5,0)
        with self.assertRaises(AttributeError):
            _=result.timeout_phase
        receipt=r.cell_receipt(result,0,10,12)
        self.assertEqual(receipt['exit_code'],0)
        self.assertEqual(receipt['exec_seconds'],1.5)
        self.assertIsNone(receipt['timeout_phase'])
        self.assertFalse(receipt['timeout_phase_available'])
        self.assertEqual(result.term_out,['ok'])

    def test_explicit_timeout_phase_is_preserved(self):
        from types import SimpleNamespace
        result=SimpleNamespace(exit_code=124,timed_out=True,exec_time=3.5,
                               timeout_phase='kernel_readiness')
        receipt=r.cell_receipt(result,0,10,14)
        self.assertEqual(receipt['timeout_phase'],'kernel_readiness')
        self.assertTrue(receipt['timeout_phase_available'])
        self.assertTrue(receipt['timed_out'])

    def test_missing_required_field_still_fails(self):
        from types import SimpleNamespace
        with self.assertRaises(AttributeError):
            r.cell_receipt(SimpleNamespace(exit_code=0,timed_out=False),0,10,12)


if __name__=='__main__':unittest.main()
