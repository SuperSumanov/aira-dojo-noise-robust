import hashlib
import unittest
from live_exposure_readout import match_roles,qualify


class ReadoutTests(unittest.TestCase):
    def test_repeated_code_is_chronological(self):
        code='pass';pin=hashlib.sha256(code.encode()).hexdigest()
        nodes=[{'operators_used':[r],'code':code} for r in ('draft','improve')]
        c=[dict(code_sha256=pin,elapsed_seconds=t,valid=v) for t,v in ((20,True),(30,False))]
        r=match_roles(nodes,c)
        self.assertEqual(r['completed_valid_improves'],0)
        self.assertEqual([v['role'] for v in r['matched']],['draft','improve'])
    def test_missing_not_invented(self):
        r=match_roles([{'operators_used':['improve'],'code':'pass'}],[])
        self.assertEqual(r['unmatched_recorded_nodes'],1);self.assertEqual(r['completed_valid_improves'],0)
    def test_both_tasks_and_all4(self):
        rows=[dict(task=t,complete=True,unmatched_recorded_nodes=0,completed_valid_improves=1) for t in ('a','b','a','b')]
        self.assertTrue(qualify(rows,True)[0]);self.assertFalse(qualify(rows[:3],True)[0])
        rows[0]['complete']=False;self.assertFalse(qualify(rows,True)[0])
    def test_one_task_not_enough(self):
        rows=[dict(task=t,complete=True,unmatched_recorded_nodes=0,completed_valid_improves=int(t=='a')) for t in ('a','b','a','b')]
        self.assertFalse(qualify(rows,True)[0]);self.assertFalse(qualify(rows,False)[0])


if __name__=='__main__':unittest.main()
