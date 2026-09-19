import hashlib,tempfile,unittest
from pathlib import Path
from run_comparison_frozen_reward_20260919 import infer

class FrozenRewardDispatch(unittest.TestCase):
    def test_fixed_code_and_task_only_reach_scorer(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'code.py';raw=b'pass\n';p.write_bytes(raw)
            row=dict(task='synthetic',seed=1,slot=0,node='n',code_path=str(p),code_sha256=hashlib.sha256(raw).hexdigest())
            calls=[]
            def score(task,code):calls.append((task,code));return .25
            output=list(infer([row],score))
            self.assertEqual(calls,[('synthetic','pass\n')]);self.assertEqual(output[0]['reward'],.25)
            self.assertNotIn('code_path',output[0]);self.assertNotIn('score',output[0])
    def test_modified_code_never_reaches_model(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'code.py';p.write_text('pass')
            with self.assertRaises(ValueError):list(infer([dict(code_path=str(p),code_sha256='a'*64)],lambda *_:self.fail('should not infer')))
    def test_nonfinite_is_not_ranked(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'code.py';p.write_bytes(b'pass')
            row=dict(code_path=str(p),code_sha256=hashlib.sha256(b'pass').hexdigest(),task='synthetic')
            with self.assertRaises(ValueError):list(infer([row],lambda *_:float('nan')))

if __name__=='__main__':unittest.main()
