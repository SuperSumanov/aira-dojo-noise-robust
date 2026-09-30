import unittest
from parser_rejection_chains_0930 import analyze


def fixture():
    rows=[];events=[]
    for segment, step, parent, rejected, operator in [(1,1,0,False,'draft'),(1,2,1,True,'improve'),(1,3,2,True,'debug'),(1,4,2,True,'debug'),(1,5,4,False,'debug'),(2,1,0,True,'debug')]:
        rows.append(dict(run_digest='a',segment=segment,step=step,parent_step=parent,generic_feedback_exact=rejected,operator=operator,task='t',arm='r',seed=1))
        events.append(dict(run_digest='a',segment=segment,step=step,parent_steps=[parent],operator=operator,timestamp=f'2026-09-01T00:00:0{step}',exec_seconds=0 if rejected else 1,exit_code=0))
    return {'rows':rows},events


class ChainTests(unittest.TestCase):
    def test_branches_are_one_component_and_segment_reset_is_separate(self):
        r=analyze(*fixture())
        self.assertEqual(r['counts']['rejection_components'],2)
        self.assertEqual(r['counts']['parser_rejections'],4)
        self.assertEqual(r['counts']['internal_parent_edges'],2)
        self.assertEqual(r['counts']['recorded_nonrejected_children'],1)
        self.assertEqual(r['components'][0]['first_to_last_logged_rejection_seconds'],2)
    def test_order_independent(self):
        c,e=fixture();first=analyze(c,e);c['rows'].reverse();e.reverse()
        self.assertEqual(analyze(c,e),first)
    def test_fake_exit_code_is_not_treated_as_execution_success(self):
        result=analyze(*fixture())
        self.assertEqual(result['strata'][0]['parser_rejections'],4)
    def test_duplicate_event_fails(self):
        c,e=fixture();e.append(e[0])
        with self.assertRaises(AssertionError):analyze(c,e)
    def test_parent_mismatch_fails(self):
        c,e=fixture();e[1]['parent_steps']=[0]
        with self.assertRaises(AssertionError):analyze(c,e)
    def test_score_fields_not_accessed(self):
        class NoOutcome(dict):
            def __getitem__(self,key):
                if key in ('score','metric','fitness'):raise AssertionError('outcome accessed')
                return super().__getitem__(key)
        c,e=fixture();analyze(c,[NoOutcome(x) for x in e])


if __name__=='__main__':unittest.main()
