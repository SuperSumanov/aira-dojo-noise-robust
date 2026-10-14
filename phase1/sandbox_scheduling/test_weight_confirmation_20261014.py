import json
from pathlib import Path
import tempfile
import unittest
from weight_confirmation_readout_20261014 import quality,TASKS,summarize


class ConfirmationTests(unittest.TestCase):
    def scores(self):
        return {(r,a,t):(.9 if t==TASKS[0] else .02 if a=='old_medium' else .018)
            for r in (0,1) for a in ('old_medium','new_medium') for t in TASKS}
    def test_both_repeats(self):
        contrasts,passed=quality(self.scores());self.assertTrue(passed);self.assertEqual(len(contrasts),4)
    def test_no_positive_repeat_rescue(self):
        s=self.scores();s[1,'new_medium',TASKS[1]]=.021;self.assertFalse(quality(s)[1])
    def test_no_aerial_loss_rescue(self):
        s=self.scores();s[1,'new_medium',TASKS[0]]=.89;self.assertFalse(quality(s)[1])
    def test_small_gain_fails(self):
        s=self.scores();s[0,'new_medium',TASKS[1]]=.0195;self.assertFalse(quality(s)[1])
    def test_schedule(self):
        import weight_confirmation_trial_20261014 as trial
        rows=trial.schedule();self.assertEqual(len(rows),32)
        self.assertEqual([rows[b*8]['arm'] for b in range(4)],['old_medium','new_medium','new_medium','old_medium'])
        for r in rows:
            peers=[s for s in rows if s['seed']==r['seed']]
            self.assertEqual(len(peers),2);self.assertEqual({s['arm'] for s in peers},{'old_medium','new_medium'})
            self.assertEqual({s['repeat'] for s in peers},{r['repeat']})
    def test_runtime_gate_missing_or_bad_rejected(self):
        from weight_confirmation_trial_20261014 import input_passed
        ref=dict(first_prompt_sha256='a'*64,preview_sha256='b'*64)
        with tempfile.TemporaryDirectory() as d:
            ep=Path(d);self.assertFalse(input_passed(ep,ref))
            events=[dict(event='fixed_public_preview_loaded',sha256='b'*64),
                dict(event='first_request_input_gate',sha256='a'*64,expected_sha256='a'*64,passed=True)]
            (ep/'input-gate.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            self.assertTrue(input_passed(ep,ref))
            events[-1]['passed']=False
            (ep/'input-gate.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            self.assertFalse(input_passed(ep,ref))
    def test_no_history_pooled_into_repeats(self):
        from weight_confirmation_trial_20261014 import schedule
        rows=[dict(r,score=.7+r['block']*.01) for r in schedule()]
        pools=summarize(rows);self.assertEqual(len(pools),8)
        self.assertEqual([p['n'] for p in pools],[4]*8)
        self.assertAlmostEqual(pools[0]['best'],.7);self.assertAlmostEqual(pools[-1]['best'],.73)

if __name__=='__main__':unittest.main()
