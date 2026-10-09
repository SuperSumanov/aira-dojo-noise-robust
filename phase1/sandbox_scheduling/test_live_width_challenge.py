import json
from pathlib import Path
import subprocess
import sys
import unittest
from live_admission import AdmissionState
from live_readout import summarize
import test_live_readout as prior_tests


class LiveWidthTests(unittest.TestCase):
    def test_four_permits_still_fifo_and_bounded(self):
        state=AdmissionState(4)
        for i in range(5):state.request(str(i))
        self.assertFalse(state.admit('1'))
        for i in range(4):self.assertTrue(state.admit(str(i)))
        self.assertFalse(state.admit('4'))
        state.finish('0',cleanup_verified=True)
        self.assertTrue(state.admit('4'))

    def test_named_two_four_readout_preserves_strict_gate(self):
        rows,blocks=prior_tests.ReadoutTests().fixture()
        for r in rows:r['arm']={'pipeline':'share2','share2':'share4'}[r['arm']]
        result=summarize(rows,blocks,('share2','share4'))
        self.assertEqual(result['paired_pool_valid_return_differences'],[4,4])
        self.assertTrue(result['exploratory_go'])
        rows[0]['complete']=False
        self.assertFalse(summarize(rows,blocks,('share2','share4'))['exploratory_go'])

    def test_new_matrix_seeds_and_actual_entry(self):
        code='''import json
import live_width_challenge as e
t=e.trial
assert t.entry_module() is e
print(json.dumps(dict(root=str(t.R),limits=t.ADMISSION_LIMITS,rows=t.schedule(),
    cap=t.CAP,fixed=t.FIXED_BLOCK_SECONDS,gate=t.GENERATOR_ELIGIBILITY_GATE,
    entry_host=callable(e.host),files=t.FILES)))
'''
        r=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).parent,
            capture_output=True,text=True,check=True)
        v=json.loads(r.stdout)
        self.assertEqual(v['limits'],{'share2':2,'share4':4})
        self.assertTrue(v['root'].endswith('scheduling-live-width-20261009-v1'))
        self.assertEqual([v['rows'][i]['arm'] for i in (0,4,8,12)],['share2','share4','share4','share2'])
        self.assertEqual(v['rows'][0]['seed'],144901)
        self.assertEqual(v['rows'][8]['seed'],145001)
        self.assertEqual((v['cap'],v['fixed'],v['gate']),(5400,1320,False))
        self.assertTrue(v['entry_host']);self.assertEqual(len(v['files']),len(set(v['files'])))

    def test_prerequisite_gate_does_not_select_positive_effects(self):
        code='''from unittest.mock import patch
import live_width_challenge as e
live=e.trial.B/'scheduling-live-search-20261009-v7'
neural=e.trial.B/'scheduling-neural-width-20261009-v1'
a=dict(plan_sha256='86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774',
    closed_sha256='a'*64,complete=16,structural_audit=True,controller_error=None,
    feedback_throughput_signal=False,exploratory_go=False)
b=dict(plan_sha256='b'*64,closed_sha256='c'*64,complete=36,complete_valid_comparison=True,
    source_commit='4a19588cb24cea8ed1d1b91f563d4ed06a68f4af')
def read(path):return a if path.parent.parent==live else b
def sha(path):
    value=a if live in path.parents else b
    return value['plan_sha256'] if path.name=='plan.json' else value['closed_sha256']
with patch.object(e,'read',side_effect=read),patch.object(e,'sha',side_effect=sha):
    e.prerequisites()
    assert len(e.trial.PREREQUISITE_RECEIPTS)==2
    b['complete_valid_comparison']=False
    try:e.prerequisites()
    except ValueError:pass
    else:raise AssertionError('bad correctness passed')
    b['complete_valid_comparison']=True;a['complete']=15
    try:e.prerequisites()
    except ValueError:pass
    else:raise AssertionError('incomplete live batch passed')
print('passed')
'''
        r=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).parent,
            capture_output=True,text=True,check=True)
        self.assertEqual(r.stdout.strip(),'passed')


if __name__=='__main__':unittest.main()
