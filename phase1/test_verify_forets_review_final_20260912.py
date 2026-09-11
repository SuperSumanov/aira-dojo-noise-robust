from copy import deepcopy
import unittest
from verify_forets_review_final_20260912 import check_selection


class FinalTests(unittest.TestCase):
    def fixture(self):
        return ({'data':{'selected_node_id':'a','score':0.0}},
            [{'id':'a','exit_code':0,'is_buggy':False,'metric_info':{
                'competition_id':'leaf-classification','valid_submission':1.0,
                'submission_exists':1.0,'is_lower_better':1.0,'score':0.0}}])

    def test_legitimate_zero_is_not_missing(self):
        event,nodes=self.fixture();self.assertEqual(check_selection(event,nodes,'leaf-classification'),0)

    def test_selected_grade_not_last_grade(self):
        event,nodes=self.fixture();second=deepcopy(nodes[0]);second['id']='b';second['metric_info']['score']=2.0
        self.assertEqual(check_selection(event,nodes+[second],'leaf-classification'),0)

    def test_reject_wrong_score_task_node_or_status(self):
        for field,value in [('score',0.2),('competition_id','spaceship-titanic'),('valid_submission',0),('is_lower_better',0)]:
            event,nodes=self.fixture();nodes[0]['metric_info'][field]=value
            with self.assertRaises(ValueError):check_selection(event,nodes,'leaf-classification')
        event,nodes=self.fixture();nodes[0]['is_buggy']=True
        with self.assertRaises(ValueError):check_selection(event,nodes,'leaf-classification')
        event,nodes=self.fixture()
        with self.assertRaises(ValueError):check_selection(event,nodes+deepcopy(nodes),'leaf-classification')


if __name__=='__main__':unittest.main()
