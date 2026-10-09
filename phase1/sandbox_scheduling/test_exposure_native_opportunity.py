import hashlib
import unittest
from exposure_native_opportunity import diagnose


def pair(step,role,code,score,bug=False,parent=None):
    return (dict(step=step,operators_used=[role],code=code,metric=None if bug else score,
                 metric_maximize=True,is_buggy=bug,exit_code=0,parents=[] if parent is None else [parent]),
            dict(code_sha256=hashlib.sha256(code.encode()).hexdigest(),valid=score is not None,
                 score=score,elapsed_seconds=step*10))


class NativeOpportunityTests(unittest.TestCase):
    def test_rejected_score_is_not_native_incumbent(self):
        pairs=[pair(1,'draft','a',.9,True),pair(2,'draft','b',.5),pair(3,'improve','c',.6,parent=2)]
        r=diagnose(*zip(*pairs),1,lambda x:x)
        self.assertEqual(r['counts']['external_valid_rejected_exit_zero'],1)
        self.assertEqual(r['counts']['strict_native_incumbent_improvements'],1)
        self.assertEqual(r['counts']['accepted_improves_beating_all_external_history'],0)
    def test_better_than_weak_parent_is_not_new_record(self):
        pairs=[pair(1,'draft','a',.8),pair(2,'draft','b',.5),pair(3,'improve','c',.6,parent=2)]
        r=diagnose(*zip(*pairs),1,lambda x:x)
        self.assertEqual(r['counts']['better_than_parent'],1)
        self.assertEqual(r['counts']['strict_native_incumbent_improvements'],0)
    def test_native_extraction_not_raw_text(self):
        n,c=pair(1,'draft','',None,True);n['code']='invalid generated text'
        r=diagnose([n],[c],1,lambda x:'')
        self.assertEqual(r['counts']['matched'],1)
        self.assertEqual(r['counts']['empty_executed_code'],1)
    def test_accepted_metric_mismatch_refused(self):
        n,c=pair(1,'draft','a',.5);n['metric']=.7
        with self.assertRaises(ValueError):diagnose([n],[c],1,lambda x:x)
    def test_order_and_count_refused(self):
        n,c=pair(1,'draft','a',.5)
        with self.assertRaises(ValueError):diagnose([n],[c,c],1,lambda x:x)
    def test_minimization(self):
        pairs=[pair(1,'draft','a',.7),pair(2,'improve','b',.6,parent=1)]
        for n,c in pairs:n['metric_maximize']=False
        r=diagnose(*zip(*pairs),-1,lambda x:x)
        self.assertEqual(r['counts']['strict_native_incumbent_improvements'],1)


if __name__=='__main__':unittest.main()
