import unittest
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

if __name__=='__main__':unittest.main()
