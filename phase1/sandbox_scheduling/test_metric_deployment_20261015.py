import json
from pathlib import Path
import tempfile
import unittest
from metric_deployment_readout_20261015 import quality,TASKS,ARMS,summarize


class MetricDeploymentTests(unittest.TestCase):
    def scores(self):
        return {(r,a,t):(.9 if t==TASKS[0] else .018 if a=='new_medium' else .020)
                for r in (0,1) for a in ARMS for t in TASKS}
    def test_all_comparisons(self):
        contrasts,passed=quality(self.scores());self.assertTrue(passed);self.assertEqual(len(contrasts),8)
    def test_strong_fast_cannot_be_ignored(self):
        s=self.scores();s[0,'old_fast',TASKS[1]]=.017;self.assertFalse(quality(s)[1])
    def test_no_repeat_rescue(self):
        s=self.scores();s[1,'new_medium',TASKS[1]]=.021;self.assertFalse(quality(s)[1])
    def test_aerial_regression_fails(self):
        s=self.scores();s[1,'new_medium',TASKS[0]]=.89;self.assertFalse(quality(s)[1])
    def test_small_gain_fails(self):
        s=self.scores();s[0,'new_medium',TASKS[1]]=.0195;self.assertFalse(quality(s)[1])
    def test_schedule(self):
        from metric_deployment_trial_20261015 import schedule,CAP
        rows=schedule();self.assertEqual(len(rows),48);self.assertEqual(CAP*6/3600,22.5)
        self.assertEqual([rows[b*8]['arm'] for b in range(6)],['old_fast','old_medium','new_medium','new_medium','old_medium','old_fast'])
        for r in rows:
            peers=[s for s in rows if s['seed']==r['seed']]
            self.assertEqual(len(peers),3);self.assertEqual({s['arm'] for s in peers},set(ARMS))
            self.assertEqual({s['task'] for s in peers},{r['task']});self.assertEqual({s['repeat'] for s in peers},{r['repeat']})
    def test_runtime_gate(self):
        from metric_deployment_trial_20261015 import input_passed
        ref=dict(first_prompt_sha256='a'*64,preview_sha256='b'*64)
        with tempfile.TemporaryDirectory() as d:
            ep=Path(d);self.assertFalse(input_passed(ep,ref))
            events=[dict(event='fixed_public_preview_loaded',sha256='b'*64),dict(event='first_request_input_gate',sha256='a'*64,expected_sha256='a'*64,passed=True)]
            (ep/'input-gate.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            self.assertTrue(input_passed(ep,ref));events[-1]['passed']=False
            (ep/'input-gate.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            self.assertFalse(input_passed(ep,ref))
    def test_pool_separation(self):
        from metric_deployment_trial_20261015 import schedule
        rows=[dict(r,score=.7+r['block']*.01) for r in schedule()]
        pools=summarize(rows);self.assertEqual(len(pools),12)
        self.assertEqual([p['n'] for p in pools],[4]*12)
        self.assertEqual([p['repeat'] for p in pools],[0]*6+[1]*6)
        self.assertAlmostEqual(pools[0]['best'],.7);self.assertAlmostEqual(pools[-1]['best'],.75)


if __name__=='__main__':unittest.main()
