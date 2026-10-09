import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import neural_width_trial as trial
import width_readout as report
from lifecycle_pilot import write,read,sha
from width_contract import schedule,WIDTHS


class WidthReadoutTests(unittest.TestCase):
    def fixture(self,root):
        plan={'schedule':schedule(),'source_commit':'a'*40,'allocation_seconds':5400}
        write(root/'plan.json',plan);write(root/'launch.json',{'job':'999'})
        write(root/'allocation.json',dict(job='999',gpu_uuid='gpu-fixture',affinity=list(range(6)),
            cpu_topology=[dict(logical_cpu=i,core=i,socket=0) for i in range(6)]))
        rows=[]
        for s in schedule():
            ep=root/f'episode-{s["index"]}';(ep/'work').mkdir(parents=True)
            base=100*s['block'];position=s['position'];width=WIDTHS[s['arm']]
            admit=base+2+(position//width)*3+position*.01
            write(ep/'started.json',dict(affinity=list(range(6))))
            write(ep/'native.json',dict(job='999',gpu_uuids=['gpu-fixture']))
            (ep/'worker.private.log').write_text(f'Kernel server is available at http://127.0.0.1:{40000+s["index"]}\n')
            write(ep/'prelude_ready.json',dict(time=base+1+position*.1))
            write(ep/'execution_admitted.json',dict(time=admit))
            write(ep/'candidate_started.json',dict(time=admit+.1))
            write(ep/'candidate_ended.json',dict(time=admit+1))
            # Synthetic CPU fixture only; not a real experiment result.
            (ep/'work/submission.csv').write_text('id,pred\na,0.25\nb,0.75\n')
            digest=sha(ep/'work/submission.csv')
            write(ep/'completed.json',dict(start=base,end=admit+1.5,complete=True,
                output={'sha256':digest},gpu_training={'steps':150 if s['program']==0 else 640}))
            write(ep/'closed.json',dict(returncode=0,end=admit+2))
            rows.append(dict(**s,status='complete',output_sha256=digest))
        for b in range(9):
            own=rows[b*4:b*4+4]
            write(root/f'block-{b}.json',dict(arm=own[0]['arm'],repeat=own[0]['repeat'],start=100*b,
                end=max(read(root/f'episode-{r["index"]}/closed.json')['end'] for r in own),telemetry_errors=[]))
            write(root/f'telemetry-{b}.json',[dict(apps=[],memory_mib=0)])
        write(root/'closed.json',dict(attempted=36,completed=36,controller_error=None))
        write(root/'runs.json',rows)
        return plan

    def analyze(self,root,plan):
        with patch.object(trial,'R',root),patch.object(trial,'check',return_value=plan), \
             patch.object(report.subprocess,'check_output',return_value='999|COMPLETED|900|cpu=6,gres/gpu=1|0:0\n'), \
             contextlib.redirect_stdout(io.StringIO()):report.main()
        return read(root/'readout-v1/summary.json')

    def test_full_three_arm_readout(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root=Path(tmp);plan=self.fixture(root);r=self.analyze(root,plan)
            self.assertTrue(r['complete_valid_comparison']);self.assertEqual(r['complete'],36)
            self.assertTrue(all(b['admission_verified'] for b in r['blocks']))
            self.assertEqual(len(r['ratios']['share2_over_share4']['paired']),3)

    def test_changed_output_does_not_pass_correctness(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root=Path(tmp);plan=self.fixture(root);ep=root/'episode-4'
            (ep/'work/submission.csv').write_text('id,pred\na,0.5\nb,0.75\n')
            # Rewrite synthetic fixture receipts, not experimental artifacts.
            import json
            done=read(ep/'completed.json');done['output']['sha256']=sha(ep/'work/submission.csv')
            (ep/'completed.json').write_text(json.dumps(done))
            rows=read(root/'runs.json');rows[4]['output_sha256']=done['output']['sha256']
            (root/'runs.json').write_text(json.dumps(rows))
            r=self.analyze(root,plan);self.assertFalse(r['complete_valid_comparison'])

    def test_bad_resource_identity_fails_gate(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root=Path(tmp);plan=self.fixture(root)
            import json
            native=read(root/'episode-4/native.json');native['gpu_uuids']=['wrong-gpu']
            (root/'episode-4/native.json').write_text(json.dumps(native))
            self.assertFalse(self.analyze(root,plan)['complete_valid_comparison'])


if __name__=='__main__':unittest.main()
