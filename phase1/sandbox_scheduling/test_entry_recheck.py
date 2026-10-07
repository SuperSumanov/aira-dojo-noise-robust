import unittest
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


if __name__=='__main__':unittest.main()
