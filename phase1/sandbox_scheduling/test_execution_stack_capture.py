import unittest
from unittest.mock import patch
import execution_stack_capture_20261011 as m

class Tests(unittest.TestCase):
    def test_matrix(self):
        rows=m.schedule();self.assertEqual(len(rows),10)
        self.assertEqual([x['block'] for x in rows],list(range(10)))
        self.assertTrue(all(x['width']==1 and x['program']==1 for x in rows))
    def test_candidate_source_is_not_modified(self):
        class Base:
            def execute_code(self,code):return code
        with patch.object(m.m,'e_observe_original',lambda b,ep:b,create=True):
            executor=m.stack_executor(Base,None)()
            self.assertEqual(executor.execute_code('PRELUDE'),'PRELUDE'+m.STACK)
            self.assertEqual(executor.execute_code('EXACT-CANDIDATE'),'EXACT-CANDIDATE')
            self.assertEqual(executor.execute_code('RECEIPT'),'RECEIPT')
    def test_gpu_error_not_zero_utilization(self):
        class Result:returncode=6;stderr='No devices were found';stdout=''
        with patch.object(m.subprocess,'run',return_value=Result()):
            row=m.gpu_snapshot('GPU-aaaa')
        self.assertFalse(row['query_ok']);self.assertNotIn('values',row)
    def test_scope_pinned_to_explicit_uuid(self):
        with self.assertRaises(AssertionError):m.gpu_snapshot('0')

if __name__=='__main__':unittest.main()
