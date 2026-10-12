import unittest
from feedback_effort_policy_20261012 import thinking,normalize,ARMS,ORDER
class Tests(unittest.TestCase):
    def test_exact_matrix(self):
        self.assertEqual([[thinking(a,r) for r in ('improve','debug','analyze')] for a in ARMS],
                         [[True,True,True],[False,False,True],[False,True,True]])
    def test_order_reverses(self):self.assertEqual(ORDER[3:],tuple(reversed(ORDER[:3])))
    def test_reject_unknown(self):
        with self.assertRaises(ValueError):thinking('unknown','improve')
        with self.assertRaises(ValueError):thinking('medium','unknown')
    def test_normalize_only_mode(self):
        def fixture(flag):return {'solver':{'operators':{'improve':{'llm':{'generation_kwargs':dict(seed=17,max_tokens=8192,reasoning_effort='medium' if flag else 'none',extra_body={'chat_template_kwargs':{'enable_thinking':flag}})}}}}}
        a=fixture(True);b=fixture(False)
        self.assertEqual(normalize(a),normalize(b));self.assertTrue(a['solver']['operators']['improve']['llm']['generation_kwargs']['extra_body']['chat_template_kwargs']['enable_thinking'])
        b['solver']['operators']['improve']['llm']['generation_kwargs']['seed']=19
        self.assertNotEqual(normalize(a),normalize(b))
    def test_quality_gate_needs_both_references_both_repeats(self):
        from feedback_effort_readout_20261012 import quality,TASKS
        scores={(b,t):(.999 if t==TASKS[0] else (.015 if ORDER[b]=='feedback_think' else .020)) for b in range(6) for t in TASKS}
        self.assertTrue(quality(scores)[1])
        scores[4,TASKS[1]]=.014
        self.assertFalse(quality(scores)[1])
if __name__=='__main__':unittest.main()
