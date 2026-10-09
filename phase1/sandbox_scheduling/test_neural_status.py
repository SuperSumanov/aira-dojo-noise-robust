import unittest
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch
from neural_status import main
from neural_status import validated_completion

class CompletionTests(unittest.TestCase):
 def test_completed_success(self):
  self.assertTrue(validated_completion({'complete':True,'error_type':None,'output':{'sha256':'present'}},{'returncode':0}))
 def test_deadline_escaped_finally_is_not_success(self):
  self.assertFalse(validated_completion({'complete':True,'error_type':None},{'returncode':1}))
 def test_not_closed_is_not_success(self):
  self.assertFalse(validated_completion({'complete':True,'error_type':None,'output':{'x':1}},{}))
 def test_missing_output_is_not_success(self):
  self.assertFalse(validated_completion({'complete':True,'error_type':None},{'returncode':0}))
 def test_nonzero_exit_is_not_success(self):
  self.assertFalse(validated_completion({'complete':True,'error_type':None,'output':{'x':1}},{'returncode':1}))
 def test_reverse_monitor_preserves_full_schedule_without_preparing(self):
  with tempfile.TemporaryDirectory(prefix='status-fixture-',dir=Path(__file__).resolve().parent) as tmp:
   root=Path(tmp)
   (root/'launch.json').write_text('{"job":"synthetic"}')
   (root/'plan.json').write_text('{}')
   for i in range(6): (root/f'block-{i}.json').write_text('{}')
   rows=[{'index':i,'arm':'share2' if i//2 in (0,3,4) else 'pipeline'} for i in range(12)]
   stub=types.SimpleNamespace(old=types.SimpleNamespace(e=types.SimpleNamespace(R=root),reverse_schedule=lambda:rows))
   output=io.StringIO()
   with patch.dict(sys.modules,{'neural_reverse_independent_20261010':stub}),contextlib.redirect_stdout(output):
    main('reverse-independent')
   observed=json.loads(output.getvalue())
   self.assertEqual(observed['blocks_complete'],6)
   self.assertEqual([r['index'] for r in observed['rows']],[36]+list(range(12)))
   self.assertEqual([r['arm'] for r in observed['rows'][1:]],[r['arm'] for r in rows])
   self.assertTrue(all(not r['started'] for r in observed['rows']))

if __name__=='__main__':unittest.main()
