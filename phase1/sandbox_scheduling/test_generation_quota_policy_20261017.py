import sys,types,unittest
from unittest.mock import patch
from generation_quota_policy_20261017 import choice,eligible_requests,metadata_audit,install

def r(key,task='a',role='improve',requested=0,run=0):
    return dict(key=key,task=task,role=role,requested=requested,run=run)

class QuotaTests(unittest.TestCase):
    def test_borrow_idle_slot(self):
        s=dict(active=[r('a'),r('b')],waiting=[r('c')])
        self.assertIsNone(choice(s,'partitioned'));self.assertEqual(choice(s,'pooled')['key'],'c')
    def test_identical_without_binding_quota(self):
        s=dict(active=[r('a')],waiting=[r('b'),r('c',task='b',requested=1)])
        self.assertEqual(choice(s,'partitioned'),choice(s,'pooled'))
    def test_same_global_priority(self):
        s=dict(active=[],waiting=[r('a',requested=0),r('b',task='b',role='analyze',requested=1)])
        for mode in ('partitioned','pooled'):self.assertEqual(choice(s,mode)['key'],'b')
    def test_global_capacity(self):
        s=dict(active=[r(str(i)) for i in range(4)],waiting=[r('x',task='b')])
        for mode in ('partitioned','pooled'):self.assertEqual(eligible_requests(s,mode),[])
    def test_global_winner_uses_its_own_task_parent(self):
        calls=[];module=types.SimpleNamespace(parent_choice=lambda s,t,a:(calls.append((t,a)) or 'parent-'+t))
        s=dict(active=[],waiting=[r('winner',task='b'),r('caller',task='a',requested=1)])
        with patch.dict(sys.modules,feedback_parent_policy_20261012=module):
            install('pooled')
            self.assertEqual(module.select_request(s,'a','greedy'),('winner','parent-b'))
        self.assertEqual(calls,[('b','greedy')])
    def test_invalid_mode_fails_closed(self):
        with self.assertRaises(ValueError):install('other')
        with self.assertRaises(ValueError):choice(dict(active=[],waiting=[]),'other')
    def test_partitioned_selects_eligible_other_task(self):
        s=dict(active=[r('a'),r('b')],waiting=[r('c'),r('d',task='b',requested=1)])
        self.assertEqual(choice(s,'partitioned')['key'],'d');self.assertEqual(choice(s,'pooled')['key'],'c')
    def test_full_audit(self):
        ev=[]
        for i in range(4):ev += [dict(event='queued',request=r(str(i))),dict(event='admitted',key=str(i))]
        ev += [dict(event='released',key=str(i)) for i in range(4)]
        self.assertEqual(metadata_audit(ev,'pooled')['borrowed_admissions'],2)
        with self.assertRaises(AssertionError):metadata_audit(ev,'partitioned')
    def test_no_stranded_request_or_illegal_priority(self):
        with self.assertRaises(AssertionError):metadata_audit([dict(event='queued',request=r('x'))],'pooled')
        ev=[dict(event='queued',request=r('a')),dict(event='queued',request=r('b',role='analyze')),dict(event='admitted',key='a')]
        with self.assertRaises(AssertionError):metadata_audit(ev,'pooled')
    def test_fixed_full_quality_gate(self):
        from generation_quota_readout_20261017 import quality,ORDER,TASKS
        rows=[dict(block=i//8,task=TASKS[i%2],score=(.02-(.002 if ORDER[i//8]=='pooled' else 0)) if i%2 else .99) for i in range(32)]
        self.assertTrue(quality(rows)[2])
        for row in rows[16:24]:
            if row['task']==TASKS[1]:row['score']=.021
        self.assertFalse(quality(rows)[2])
        with self.assertRaises(AssertionError):quality(rows[:-1])

if __name__=='__main__':unittest.main()
