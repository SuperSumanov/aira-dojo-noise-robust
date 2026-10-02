import contextlib, importlib.util, io, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
S=Path(__file__).resolve().parents[1]/'scripts/decision_diagnosis_readout_20261002.py'
spec=importlib.util.spec_from_file_location('diagnosis_reader',S)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def put(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj))

class ReaderTests(unittest.TestCase):
    def fixture(self,root,missing_initial=False):
        schedule=[]
        for t,task in enumerate(('random-acts-of-pizza','spooky-author-identification')):
            for seed in (1,2):
                for arm in 'AB':
                    i=len(schedule); entry=dict(index=i,start=t,task=task,seed=seed+10*t,arm=arm,wave=i//2)
                    schedule.append(entry); ep=root/f'episode-{i}'
                    put(ep/'closed.json',{'worker_deadline_reached':False})
                    put(root/f'configs/{i}.json',{})
                    lower=t==1; init=.4 if lower else .6; best=init
                    for step in range(3):
                        if missing_initial and i==1 and step==0: continue
                        check=arm=='B' and step==1
                        value=init if step==0 else (None if check else ((.39 if arm=='A' else .38) if lower else (.65 if arm=='A' else .66)))
                        if step==2 and arm=='A': value=.42 if lower else .59
                        if value is not None: best=(min if lower else max)(best,value)
                        put(ep/f'action-{step}/result.json',dict(step=step,kind='CHECK' if check else 'SOLUTION',
                            metric=value,valid=not check,successful_check=check,exec_seconds=1.,elapsed_seconds=2.+step,selected_metric=best))
        put(root/'plan.json',dict(schedule=schedule,run_seconds=900,base_commit='a'*40,max_calls=2,max_tokens_per_call=4096,
            files={'task_feedback_real_20261001.py':'b'*64}))
        put(root/'launch.json',{'job':'synthetic'})
        put(root/'all-closed.json',{}); put(root/'closed.json',{})

    def run_reader(self,missing=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); self.fixture(root,missing)
            with patch.object(m,'R',root),patch.object(m.subprocess,'check_output',return_value='synthetic|COMPLETED|1|gres/gpu=4|'),contextlib.redirect_stdout(io.StringIO()):
                m.analyze()
            return json.loads((root/'readout-v1/summary.json').read_text())

    def test_both_directions_and_incumbent(self):
        s=self.run_reader(); self.assertTrue(s['numerical_gate']); self.assertEqual(len(s['rows']),8)
        for task in s['tasks']:
            self.assertEqual(task['B_wins'],2); self.assertAlmostEqual(task['median_delta'],.01)
            self.assertEqual(task['sample_variance'],0)
        self.assertTrue(all(r['selected_step']==1 for r in s['rows'] if r['arm']=='A'))

    def test_missing_initial_not_imputed(self):
        s=self.run_reader(True); self.assertFalse(s['numerical_gate'])
        self.assertEqual(s['tasks'][0]['paired'],1); self.assertEqual(s['tasks'][0]['planned'],2)

    def test_unclosed_batch_not_read(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(m,'R',Path(folder)):
            with self.assertRaisesRegex(ValueError,'closure'): m.analyze()

if __name__=='__main__': unittest.main()
