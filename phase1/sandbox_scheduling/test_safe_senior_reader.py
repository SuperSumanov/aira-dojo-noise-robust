"""Regression for the trusted stream reader, using synthetic text only.

Run locally; this does not read the senior report or any credential.
The helper remains in the operational checkout, outside experimental runtime.
"""
import contextlib
import io
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

HELPER=Path(__file__).with_name('safe_senior_reader.py')


class Capture(io.StringIO):
    def reconfigure(self,**kwargs):pass


class ReaderRegression(unittest.TestCase):
    def test_query_assignment_spellings(self):
        value='synthetic'+'-fixture-not-a-credential'
        cases=[f'https://example.invalid/view?{key}={value}&page=2'
            for key in ('accessToken','access_token','access-token','token','apiKey','%61ccessToken')]
        cases += [f'accessToken%3D{value}',f'Authorization: Bearer {value}',f'apiKey = "{value}"']
        for source in cases:
            out=Capture();err=Capture()
            with self.subTest(source=source.split('=')[0]),patch.object(sys,'argv',['reader','fixture','fixture.md']),\
                patch('subprocess.check_output',return_value=source.encode()),\
                contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                runpy.run_path(str(HELPER),run_name='__main__')
            self.assertNotIn(value,out.getvalue())
            self.assertIn('[REDACTED]',out.getvalue())
            self.assertIn('REDACTION_COUNTS=',err.getvalue())
    def test_normal_text_retained(self):
        source='Six programs; no credentials.'
        out=Capture();err=Capture()
        with patch.object(sys,'argv',['reader','fixture','fixture.md']),\
            patch('subprocess.check_output',return_value=source.encode()),\
            contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            runpy.run_path(str(HELPER),run_name='__main__')
        self.assertEqual(out.getvalue(),source)


if __name__=='__main__':unittest.main()
