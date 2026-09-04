"""Dispatch-only source equality: this does not revalidate the scientific intake."""
from pathlib import Path
import subprocess
import unittest

from phase1.scripts.foreground_intake_session_20260905 import validate_derivation, INSERT, REL


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.original = subprocess.check_output(['git', '-C', str(self.root), 'show',
            'b20dd2682d609c0236c138c08797678cf31a2fc0:'+REL])
        self.derived = (self.root/REL).read_bytes().replace(b'\r\n', b'\n')

    def test_only_dispatch_inserted(self):
        validate_derivation(self.original, self.derived)

    def test_runner_change_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'derived_body_changed'):
            validate_derivation(self.original, self.derived.replace(b'--minimum-age-seconds 21600',
                                                                    b'--minimum-age-seconds 1'))

    def test_missing_dispatch_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'derived_body_changed'):
            validate_derivation(self.original, self.derived.replace(INSERT, b''))

    def test_original_drift_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'original_monitor_drift'):
            validate_derivation(self.original+b'\n', self.derived)


if __name__ == '__main__':
    unittest.main()
