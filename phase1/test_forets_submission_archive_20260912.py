import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from forets_submission_archive_20260912 import archive_submission, patch_evaluator, snapshot_submission


class ArchiveTests(unittest.TestCase):
    def test_exact_bytes_and_repeated_identical_submissions_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); path=base/'submission.csv'; raw=b'id,p\r\n1,0.25\r\n'
            path.write_bytes(raw); report={'score':0.25,'created_at':'artificial'}
            for _ in range(2):
                receipt=archive_submission(path,snapshot_submission(path),report,base/'escrow')
                self.assertEqual(receipt['submission_sha256'],hashlib.sha256(raw).hexdigest())
            leaves=list((base/'escrow').iterdir());self.assertEqual(len(leaves),2)
            for leaf in leaves:
                self.assertEqual((leaf/'submission.csv').read_bytes(),raw)
                self.assertEqual(json.loads((leaf/'report.json').read_text()),report)
                self.assertTrue((leaf/'complete.json').is_file())
            self.assertEqual(path.read_bytes(),raw)

    def test_changed_input_fails_without_creating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);path=base/'submission.csv';path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed during grading'):
                archive_submission(path,b'original',{},base/'escrow')
            self.assertFalse((base/'escrow').exists())

    def test_invalid_report_fails_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);path=base/'submission.csv';path.write_bytes(b'data')
            with self.assertRaises(ValueError):
                archive_submission(path,b'data',{'score':float('nan')},base/'escrow')
            self.assertFalse((base/'escrow').exists())

    def test_patch_fails_closed_and_does_not_repeat(self):
        source=('import pandas as pd\n'
                '    if submission_exists:\n        submission_df = read_csv(submission_path)\n'
                '    results_output_dir.mkdir(exist_ok=True)\n')
        patched=patch_evaluator(source)
        self.assertIn('submission_raw = snapshot_submission',patched)
        with self.assertRaises(ValueError):patch_evaluator(patched)
        with self.assertRaises(ValueError):patch_evaluator('unrelated')


if __name__=='__main__':unittest.main()
