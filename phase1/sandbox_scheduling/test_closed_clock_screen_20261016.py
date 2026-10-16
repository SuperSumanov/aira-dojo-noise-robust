import unittest
from closed_clock_screen_20261016 import screen

class ClockTests(unittest.TestCase):
    def test_fixed_epochs(self):
        self.assertEqual(screen("for epoch in range(10):\n    train()")['clock_exit_guards'],0)
    def test_elapsed_break(self):
        s=screen("import time\nt=time.time()\nfor epoch in range(20):\n    if time.time()-t>300: break")
        self.assertEqual(s['clock_exit_guards'],1)
    def test_derived_deadline(self):
        s=screen("from time import monotonic as now\nend=now()+30\nremaining=end-now()\nwhile remaining>0:\n    remaining=end-now()")
        self.assertEqual(s['clock_exit_guards'],1)
    def test_only_logging(self):
        self.assertEqual(screen("import time\nif time.time()>1:\n    print('log')")['clock_exit_guards'],0)
    def test_import_alias(self):
        self.assertEqual(screen("import time as t\ndef train():\n    if t.perf_counter()>4: return")['clock_exit_guards'],1)
    def test_parse_failure(self):
        self.assertFalse(screen("for ???")['parsed'])

if __name__=='__main__':unittest.main()
