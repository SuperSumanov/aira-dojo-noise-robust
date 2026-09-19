import hashlib,tempfile,unittest
from pathlib import Path
from run_comparison_frozen_reward_20260919 import infer,batch_script,ATTEMPT_SECONDS,PRIOR_SECONDS

class FrozenRewardDispatch(unittest.TestCase):
    def test_exclusive_step_resets_parent_mask_and_accounts_failed_start(self):
        script=batch_script(Path('/synthetic/root'))
        self.assertLess(script.index('unset CUDA_VISIBLE_DEVICES'),script.index('exec srun'))
        self.assertIn('--exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 --gres=gpu:1',script)
        self.assertEqual(ATTEMPT_SECONDS+PRIOR_SECONDS,1800)
        self.assertIn('/venvs/exp/bin/python',script)
        self.assertNotIn('/venvs/aira/bin/python',script)
        self.assertNotIn('ROOT',script)
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
