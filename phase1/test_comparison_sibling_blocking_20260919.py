import copy,unittest
from analyze_selected_sibling_blocking_20260919 import analyze

def fixture():
    runs=[dict(run='r',arm='forets-1',journal_present=True,stratum='task/config',seed=1)]
    nodes=[];metadata=[]
    for step,kind,parents,buggy,created in ((1,'draft',[0],True,1),(2,'debug',[1],True,3),(3,'draft',[0],False,2)):
        n=dict(run='r',id=str(step),step=step,parents=parents,operators_used=[kind,'analysis'],group='executed',is_buggy=buggy,creation_time=created,exec_time=2.,score=None if buggy else .8)
        nodes.append(n);metadata.append(dict(run='r',node=str(step),operators=n['operators_used'],group='executed',numeric_operator_fields={'.0.usage.latency':5.,'.1.usage.latency':1.}))
    return runs,nodes,metadata

class BlockingTests(unittest.TestCase):
    def test_delayed_ready_sibling(self):
        r=analyze(*fixture());self.assertEqual(r['positive_opportunity_runs'],1);self.assertEqual(r['rows'][0]['logged_serial_components_seconds'],8);self.assertTrue(r['rows'][0]['ready_second_sibling'])
    def test_successful_repair_is_not_failed_chain(self):
        r,n,m=fixture();n[1]['is_buggy']=False
        self.assertEqual(analyze(r,n,m)['positive_opportunity_runs'],0)
    def test_second_failure_retained_not_positive(self):
        r,n,m=fixture();n[-1]['is_buggy']=True;n[-1]['score']=None
        v=analyze(r,n,m);self.assertEqual(v['physical_runs'],1);self.assertEqual(v['positive_opportunity_runs'],0)
    def test_duplicate_or_invalid_lineage_fails(self):
        r,n,m=fixture()
        with self.assertRaises(ValueError):analyze(r,n+n[:1],m)
        n[1]['parents']=[999]
        with self.assertRaises(ValueError):analyze(r,n,m)
    def test_missing_cost_is_not_zero(self):
        r,n,m=fixture();m[1]['numeric_operator_fields'].pop('.1.usage.latency')
        with self.assertRaises(ValueError):analyze(r,n,m)

if __name__=='__main__':unittest.main()
