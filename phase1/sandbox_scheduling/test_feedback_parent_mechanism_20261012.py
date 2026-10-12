import copy
import unittest
from feedback_parent_mechanism_20261012 import analyze_events


ROWS = [dict(index=0, task='T'), dict(index=1, task='T')]


def fixture():
    def req(key, role='improve'):
        return dict(key=key, run=0, task='T', role=role, requested=0)
    def ev(t, event, **kw):
        return dict(time=t, event=event, run=0, **kw)
    return [ev(0,'warm_start',code_sha256='warm'),
            ev(1,'queued',request=req('a')),
            ev(2,'admitted',key='a',parent='warm',alternatives={'pending_ucb':'warm'}),
            ev(3,'released',key='a'), ev(4,'queued',request=req('b')),
            ev(5,'feedback_wait',key='b'),
            ev(8,'round_complete',key='a',valid=True,code_sha256='new'),
            ev(9,'admitted',key='b',parent='new',alternatives={'pending_ucb':'warm'}),
            ev(10,'released',key='b'),
            ev(12,'round_complete',key='b',valid=True,code_sha256='third')]


class MechanismTests(unittest.TestCase):
    def test_real_idle_interval_not_only_logged_wait(self):
        out=analyze_events(fixture(),ROWS,'feedback_gate')
        self.assertEqual(out['mandatory_wait_task_seconds'],{'T':4.})
        self.assertEqual(out['withheld_generation_permit_seconds'],{'T':4.})
        self.assertEqual(out['completed_nonwarm_parent'],1)
        self.assertEqual(out['chosen_parent_differs_from_pending_ucb'],1)

    def test_debug_eligibility_is_not_forced_idle(self):
        es=fixture()+[dict(time=6,event='queued',run=0,request=dict(key='d',run=0,task='T',role='debug',requested=6)),
                      dict(time=7,event='cancelled',key='d',run=0)]
        self.assertEqual(analyze_events(es,ROWS,'feedback_gate')['mandatory_wait_task_seconds'],{'T':3.})

    def test_no_gpu_idle_or_counterfactual_claim_for_reference(self):
        out=analyze_events(fixture(),ROWS,'pending_ucb')
        self.assertEqual(out['mandatory_wait_task_seconds'],{'T':0.})

    def test_pending_overlap_caught(self):
        es=fixture();es[7]['time']=7.;es[7]['parent']='warm';es[7]['alternatives']={'pending_ucb':'warm'}
        with self.assertRaises(AssertionError):analyze_events(es,ROWS,'feedback_gate')
        self.assertEqual(analyze_events(es,ROWS,'pending_ucb')['same_parent_pending_admissions'],1)

    def test_unknown_event_fails_closed(self):
        es=fixture()+[dict(time=13,event='future_event',run=0)]
        with self.assertRaises(ValueError):analyze_events(es,ROWS,'feedback_gate')

    def test_inputs_unchanged(self):
        es=fixture();before=copy.deepcopy(es)
        analyze_events(es,ROWS,'feedback_gate')
        self.assertEqual(es,before)


if __name__ == '__main__':unittest.main()
