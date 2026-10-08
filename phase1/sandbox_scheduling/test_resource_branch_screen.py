import unittest
import resource_branch_screen as s


class ScreenTests(unittest.TestCase):
    def test_logging_only_is_not_branch(self):
        self.assertEqual(s.inspect('import time\nt=time.time()\nprint(time.time()-t)'),[])

    def test_clock_alias_and_derived_condition(self):
        rows=s.inspect('from time import perf_counter as pc\ndef train():\n t=pc()\n elapsed=pc()-t\n while elapsed<100:\n  break')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['sources'],['clock'])
        self.assertTrue(rows[0]['has_break'])

    def test_memory_tuple_propagation(self):
        rows=s.inspect('import torch\nfree,total=torch.cuda.mem_get_info()\nb=16 if free<100 else 32')
        self.assertEqual(rows[0]['sources'],['torch.cuda.mem_get_info'])

    def test_different_function_variable_is_not_tainted(self):
        self.assertEqual(s.inspect('import time\ndef a():\n t=time.time()\ndef b(t):\n if t>10:\n  return 1'),[])

    def test_availability_not_mislabeled_as_memory(self):
        rows=s.inspect('import torch\nif torch.cuda.is_available():\n x=1')
        self.assertEqual(rows[0]['sources'],['torch.cuda.is_available'])


if __name__=='__main__':unittest.main()
