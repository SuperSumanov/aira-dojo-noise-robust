import unittest
from feedback_parent_overlap_diagnostic_20261012 import summarize


class OverlapTests(unittest.TestCase):
    def events(self):
        events=[]
        for i in range(2):
            events.append(dict(event='queued',request=dict(key=str(i),task='task',run=i)))
            events.append(dict(event='admitted',key=str(i),role='improve',parent='p',run=i,
                snapshot=dict(archive={'task':{'p':{'metric':.1}}})))
        for i in range(2):
            events.append(dict(event='parent_used',key=str(i),child=f'c{i}'))
            events.append(dict(event='round_complete',key=str(i)))
        return events

    def test_overlap_can_be_useful_without_imputed_counterfactual(self):
        c={(1,'c1'):[dict(score=.05,valid=True,exit_code=0,timed_out=False,elapsed_seconds=100)]}
        result=summarize(self.events(),c,{0:'task',1:'task'},{'task':-1})['task']
        self.assertEqual(result['overlapping_same_parent']['improves_incumbent_at_admission'],1)
        self.assertEqual(result['no_overlapping_same_parent']['direct_timely_valid'],0)

    def test_late_failed_and_ambiguous_are_not_credited(self):
        ok=dict(score=.05,valid=True,exit_code=0,timed_out=False,elapsed_seconds=100)
        for vals in ([dict(ok,elapsed_seconds=1021)],[dict(ok,exit_code=1)],[ok,ok]):
            result=summarize(self.events(),{(1,'c1'):vals},{0:'task',1:'task'},{'task':-1})['task']['overlapping_same_parent']
            self.assertEqual(result['direct_timely_valid'],0)
            self.assertIsNone(result['direct_best'])


if __name__=='__main__':unittest.main()
