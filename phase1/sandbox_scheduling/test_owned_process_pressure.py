import unittest
from unittest.mock import patch
import owned_process_pressure as p

class Fake:
    def __init__(self,data):self.data=data
    def __truediv__(self,name):return self.data[name]
class Text:
    def __init__(self,*texts):self.texts=list(texts)
    def read_text(self):return self.texts.pop(0) if len(self.texts)>1 else self.texts[0]

def stat(pid=10,start=100):
    f=['S','1']+['0']*17+[str(start)]
    return str(pid)+' (private (name)) '+' '.join(f)

STATUS='Uid:\t7 7 7 7\nPPid:\t1\nState:\tS (sleeping)\nThreads:\t3\nVmSize:\t1024 kB\nNSpid:\t10 1\n'

class Tests(unittest.TestCase):
    def test_limit_names_not_error_messages(self):
        value=p.parse_limits('Max processes             1024                 9000                 processes\nMax address space         unlimited            unlimited            bytes\n')
        self.assertEqual(value,{'RLIMIT_NPROC':[1024,9000],'RLIMIT_AS':['unlimited','unlimited']})
        self.assertEqual(p.parse_limits('OpenBLAS RLIMIT_NPROC 1024 current'),{})
    def test_status_numeric_only_and_missing_not_zero(self):
        value=p.numeric_status(STATUS)
        self.assertEqual(value['namespace_pids'],[10,1]);self.assertIsNone(value['VmRSS_kib'])
        self.assertEqual(value['VmSize_kib'],1024)
    def test_stat_comm_not_exported(self):
        self.assertEqual(p.stat_identity(stat()),dict(pid=10,ppid=1,start_ticks=100))
    def test_descendants_excludes_other_same_uid_job(self):
        rows={10:dict(ppid=1),20:dict(ppid=10),30:dict(ppid=20),40:dict(ppid=1)}
        self.assertEqual(p.descendants(rows,10),{10,20,30})
    def test_uid_mismatch_rejected_before_limits(self):
        d=Fake(dict(stat=Text(stat()),status=Text(STATUS)))
        with self.assertRaises(PermissionError):p.process_record(d,8)
    def test_pid_reuse_rejected(self):
        d=Fake(dict(stat=Text(stat(),stat(start=101)),status=Text(STATUS),limits=Text('')))
        with self.assertRaises(ProcessLookupError):p.process_record(d,7)
if __name__=='__main__':unittest.main()
