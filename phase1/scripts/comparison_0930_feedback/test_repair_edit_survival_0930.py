import unittest
from repair_edit_survival_0930 import fingerprint,comparison,analyze
from independent_raw_comparison_0930 import BAD,KEY

def node(step,op,code,parents,valid=False):
    return {'step':step,'operators_used':[op] if op else [],'code':code,'parents':parents,
        'metric_info/valid_submission':valid,'metric_info/score':.5 if valid else None}

class Tests(unittest.TestCase):
    def test_comment_invariance(self):
        self.assertEqual(fingerprint('x=f(a=1)')['normalized'],fingerprint('# explanation\nx = f(a = 1)')['normalized'])
    def test_exact_reversion(self):
        p=fingerprint('x=f()');o=fingerprint('x=g()')
        r=comparison(p,o,p)
        self.assertTrue(r['exact_ast_revert_to_parent']);self.assertEqual(r['retained_call_targets'],0)
    def test_repair_without_target_loss(self):
        r=comparison(fingerprint('x=f()'),fingerprint('x=g(wrong=1)'),fingerprint('x=g(correct=1)'))
        self.assertEqual(r['novel_call_targets'],1);self.assertEqual(r['retained_call_targets'],1)
        self.assertEqual(r['retained_calls'],0) # parameter changes are not goal loss
    def test_absent_novelty_not_failure(self):
        p=fingerprint('x=f()');r=comparison(p,p,p)
        self.assertEqual(r['novel_call_targets'],0)
    def test_callee_rename_is_not_semantic_proof(self):
        p=fingerprint('x=f()');o=fingerprint('from m import g\nx=g()');r=fingerprint('from m import g as h\nx=h()')
        self.assertEqual(comparison(p,o,r)['retained_call_targets'],0)
    def test_first_graded_and_last_distinct(self):
        ns=[node(0,None,'',[]),node(1,'Draft','x=f()',[0],True),node(2,'Improve','x=g(wrong=1)',[1]),
            node(3,'Debug','x=g(right=1)',[2],True),node(4,'Debug','x=f()',[3],True)]
        rr,ss=analyze(ns,'r','t','a',1)
        self.assertEqual(ss['improve_debug_origins'],1)
        self.assertEqual({r['endpoint']:r['endpoint_step'] for r in rr},{'last_logged_debug':4,'first_finite_grade_debug':3})
    def test_restart_not_merge(self):
        ns=[node(0,None,'',[]),node(1,'Draft','x=f()',[0],True),node(2,'Improve','x=g()',[1]),node(3,'Debug','x=g()',[2],True)]
        rr,ss=analyze(ns+ns,'r','t','a',1)
        self.assertEqual(ss['improve_debug_origins'],2);self.assertEqual(len(rr),4)
    def test_parse_failure_retained(self):
        ns=[node(0,None,'',[]),node(1,'Draft','x=f()',[0],True),node(2,'Improve','x = (',[1]),node(3,'Debug','x=g()',[2],True)]
        rr,ss=analyze(ns,'r','t','a',1)
        self.assertEqual(ss['parse_failures'],1);self.assertFalse(rr[0]['usable_ast'])
    def test_real_prefix_and_embedded_task(self):
        self.assertIsNotNone(BAD.search(b'"sk-'+b'A'*24+b'"'))
        self.assertIsNone(BAD.search(b'"task-'+b'A'*24+b'"'))
        self.assertIsNotNone(KEY.search(b'"api_key":"'+b'A'*24+b'"'))

if __name__=='__main__':unittest.main()
